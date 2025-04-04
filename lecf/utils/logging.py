"""Logging utilities for the LECF package."""

import logging
import os
import sys
from pathlib import Path
import datetime

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
    logger_name = name if name else "root"

    # Clear any existing handlers to avoid duplicates when called multiple times
    if logger.handlers:
        handler_count = len(logger.handlers)
        logger.handlers.clear()
        if name is None:  # Only log this for root logger to avoid circular issues
            print(f"Cleared {handler_count} existing handlers from {logger_name} logger")

    # Configure console handler to use stdout instead of stderr
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Set log level from environment or default to INFO
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(log_level)
    
    # Configure propagation - by default child loggers should propagate to parent
    logger.propagate = name is not None  # Propagate if not root logger
    if name is None:  # Only log this for root logger to avoid circular issues
        print(f"Configured {logger_name} logger with level {log_level}")

    # Add file handler if LOG_FILE is specified
    log_file = os.getenv("LOG_FILE")
    if log_file:
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
                if name is None:  # Only log this for root logger to avoid circular issues
                    print(f"Created log directory: {log_dir}")
            except Exception as e:
                if name is None:  # Only log this for root logger to avoid circular issues
                    print(f"Failed to create log directory {log_dir}: {str(e)}")
                logger.error(f"Failed to create log directory: {log_dir}", extra={"error": str(e)})
        
        try:
            file_path = Path(log_file)
            # Ensure write permissions for the log file
            file_handler = logging.FileHandler(log_file, mode='a')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            if name is None:  # Only log this for root logger to avoid circular issues
                print(f"Added file handler for {logger_name} logger to {log_file}")
            
            # If this is the root logger, make sure it has permission to write
            if name is None and file_path.exists():
                try:
                    # Open file to verify write access
                    with open(log_file, 'a') as f:
                        test_message = f"Log file write test from {logger_name} logger at {datetime.datetime.now()}\n"
                        f.write(test_message)
                    print(f"Verified write access to log file: {log_file}")
                except Exception as e:
                    print(f"No write access to log file {log_file}: {str(e)}")
                    logger.error(f"No write access to log file", extra={"path": log_file, "error": str(e)})
                    
            logger.debug(f"Log file handler added for: {log_file}")
        except Exception as e:
            if name is None:  # Only log this for root logger to avoid circular issues
                print(f"Failed to set up log file handler for {log_file}: {str(e)}")
            logger.error(f"Failed to set up log file handler", extra={"path": log_file, "error": str(e)})

    return logger


# Initialize logger at module level for convenience
logger = setup_logging()
