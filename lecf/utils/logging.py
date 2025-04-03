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
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Initialize logger at module level for convenience
logger = setup_logging()
