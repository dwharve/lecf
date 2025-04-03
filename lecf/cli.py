"""Command-line interface for the LECF package."""

import argparse
import importlib
import os
import sys
import time
from typing import Optional

import schedule

# Import will be done dynamically
from lecf.core import BaseManager
from lecf.utils import config, logger, setup_logging

# Define available managers
AVAILABLE_MANAGERS = {
    "certificate": ("lecf.managers.certificate", "CertificateManager"),
    "ddns": ("lecf.managers.ddns", "DdnsManager"),
}


def initialize_manager(manager_key: str) -> BaseManager:
    """
    Dynamically import and initialize a manager class.

    Args:
        manager_key: The key of the manager to initialize

    Returns:
        An initialized manager instance

    Raises:
        ValueError: If the manager is not found
    """
    if manager_key not in AVAILABLE_MANAGERS:
        raise ValueError(f"Unknown manager: {manager_key}")

    module_name, class_name = AVAILABLE_MANAGERS[manager_key]

    try:
        module = importlib.import_module(module_name)
        manager_class = getattr(module, class_name)
        return manager_class()
    except Exception as e:
        logger.error(
            f"Failed to initialize {manager_key} manager",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        raise


def schedule_managers(run_once: bool = False) -> None:
    """
    Initialize and schedule all managers in a single process.

    Args:
        run_once: If True, only set up scheduling but don't enter the infinite loop.
                 This is primarily used for testing.
    """
    logger.info("Starting all services with centralized scheduling")

    # Initialize all available managers
    managers = {}
    for manager_key in AVAILABLE_MANAGERS:
        try:
            managers[manager_key] = initialize_manager(manager_key)
            logger.info(f"Initialized {manager_key} manager")
        except Exception as e:
            logger.error(
                f"Failed to initialize {manager_key} manager, service will be unavailable",
                extra={"error": str(e)},
            )

    if not managers:
        logger.error("No services could be initialized, exiting")
        sys.exit(1)

    # Schedule all managers
    for key, manager in managers.items():
        # Run initial cycle
        try:
            logger.info(f"Running initial {key} cycle")
            manager.run()
        except Exception as e:
            logger.error(f"Error during initial {key} cycle", extra={"error": str(e)})

        # Schedule periodic runs
        interval, unit = manager.get_schedule_info()
        logger.info(f"Scheduling {key} service to run every {interval} {unit}")

        # Configure schedule based on interval unit
        if unit == "minutes":
            schedule.every(interval).minutes.do(manager.run)
        elif unit == "hours":
            schedule.every(interval).hours.do(manager.run)
        elif unit == "days":
            schedule.every(interval).days.do(manager.run)
        else:
            logger.warning(f"Unknown interval unit {unit} for {key}, defaulting to hours")
            schedule.every(interval).hours.do(manager.run)

    # Log next scheduled runs for all services
    pending_jobs = schedule.get_jobs()
    for job in pending_jobs:
        logger.info(f"Next run for job: {job.next_run}")

    # Early return for tests
    if run_once:
        logger.debug("Running in test mode, skipping scheduler loop")
        return

    # Run the scheduler loop
    logger.info("Starting scheduler loop")
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Error in scheduler loop", extra={"error": str(e)})
            time.sleep(5)  # Sleep for a bit to avoid spamming logs


def initialize_cloudflare_credentials():
    """Initialize Cloudflare credentials by running the setup script."""
    from lecf.scripts.setup_cloudflare import setup_cloudflare_credentials

    try:
        setup_cloudflare_credentials()
    except Exception as e:
        logger.error(f"Failed to initialize Cloudflare credentials", extra={"error": str(e)})
        sys.exit(1)


def load_configuration(config_path: Optional[str] = None):
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to configuration file. If None, search in standard locations.
    """
    try:
        loaded_config = config.load_yaml_config(config_path)
        logger.info("Configuration loaded successfully")

        # Apply logging config if present
        if "logging" in loaded_config and "level" in loaded_config["logging"]:
            log_level = loaded_config["logging"]["level"]
            os.environ["LOG_LEVEL"] = log_level
            logger.setLevel(log_level)
            logger.info(f"Log level set to {log_level}")

        # Apply logging file if specified
        if "logging" in loaded_config and "file" in loaded_config["logging"]:
            log_file = loaded_config["logging"]["file"]
            os.environ["LOG_FILE"] = log_file

            # Re-setup logging to apply file handler
            setup_logging("main")
            logger.info(f"Log file set to {log_file}")

    except FileNotFoundError:
        logger.warning("Configuration file not found, using environment variables only")
    except Exception as e:
        logger.error(f"Error loading configuration", extra={"error": str(e)})


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Let's Encrypt Certificate Manager with Cloudflare DNS"
    )
    parser.add_argument(
        "--service",
        "-s",
        choices=["all"] + list(AVAILABLE_MANAGERS.keys()),
        default="all",
        help="Service to run (default: all)",
    )
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")
    parser.add_argument("--config", "-c", help="Path to configuration file")
    return parser.parse_args()


def main():
    """Main entrypoint function."""
    args = parse_args()

    # Configure logging
    if args.debug:
        os.environ["LOG_LEVEL"] = "DEBUG"

    # Ensure we have a clean logger for main process
    setup_logging("main")

    # Load configuration from YAML
    load_configuration(args.config)

    # Initialize Cloudflare credentials
    initialize_cloudflare_credentials()

    # Schedule and run all managers
    schedule_managers(run_once=False)  # Explicit parameter for clarity


if __name__ == "__main__":
    main()
