import sys
import time
import schedule
from datetime import datetime
from typing import List, Dict, Type
import importlib

# Import shared modules
from utils import logger, setup_logging
from base_manager import BaseManager

# Define available managers
AVAILABLE_MANAGERS = {
    'certificate': ('certificate_manager', 'CertificateManager'),
    'ddns': ('ddns_manager', 'DdnsManager')
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
        logger.error(f"Failed to initialize {manager_key} manager", 
                   extra={'error': str(e), 'error_type': type(e).__name__})
        raise

def schedule_managers() -> None:
    """
    Initialize and schedule all managers in a single process.
    """
    logger.info("Starting all services with centralized scheduling")
    
    # Initialize all available managers
    managers = {}
    for manager_key in AVAILABLE_MANAGERS:
        try:
            managers[manager_key] = initialize_manager(manager_key)
            logger.info(f"Initialized {manager_key} manager")
        except Exception as e:
            logger.error(f"Failed to initialize {manager_key} manager, service will be unavailable", 
                       extra={'error': str(e)})
    
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
            logger.error(f"Error during initial {key} cycle", 
                       extra={'error': str(e)})
        
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
    if pending_jobs:
        for job in pending_jobs:
            logger.info(f"Next scheduled run: {job.next_run.isoformat() if job.next_run else 'Unknown'}")
    
    # Keep the scheduler running
    try:
        logger.info("Scheduler running. Press Ctrl+C to exit.")
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal, terminating services...")
        sys.exit(0)

def initialize_cloudflare_credentials():
    """Initialize Cloudflare credentials by running the setup script."""
    from setup_cloudflare import setup_cloudflare_credentials
    try:
        setup_cloudflare_credentials()
    except Exception as e:
        logger.error(f"Failed to initialize Cloudflare credentials", extra={'error': str(e)})
        sys.exit(1)

def main():
    """Main entrypoint function."""
    # Ensure we have a clean logger for main process
    setup_logging('main')
    
    # Initialize Cloudflare credentials
    initialize_cloudflare_credentials()
    
    # Schedule and run all managers
    schedule_managers()

if __name__ == "__main__":
    main() 