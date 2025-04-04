"""Logging utilities for the LECF package."""

import logging
import os
import sys

from pythonjsonlogger import jsonlogger


def setup_logging(name: str = None) -> logging.Logger:
    """
    Set up and configure logging with consistent formatting.

    Args:
        name: Optional logger name. If None, returns the root logger.

    Returns:
        A configured logger instance
    """
    # Get logger
    logger = logging.getLogger(name)

    # Clear any existing handlers to avoid duplicates when called multiple times
    if logger.handlers:
        logger.handlers.clear()

    # Configure console handler to use stdout instead of stderr
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Set log level from environment or default to INFO
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(log_level)

    # Add file handler if LOG_FILE is specified
    log_file = os.getenv("LOG_FILE")
    if log_file:
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
                logger.debug(f"Created log directory: {log_dir}")
            except Exception as e:
                logger.error(f"Failed to create log directory: {log_dir}", extra={"error": str(e)})
        
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.debug(f"Log file handler added for: {log_file}")
        except Exception as e:
            logger.error(f"Failed to set up log file handler", extra={"path": log_file, "error": str(e)})

    return logger


# Initialize logger at module level for convenience
logger = setup_logging()
