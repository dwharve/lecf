import os
import sys
import logging
from dotenv import load_dotenv
from pythonjsonlogger import jsonlogger
from typing import Dict, Any

# Load environment variables
load_dotenv()

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
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Set log level from environment or default to INFO
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logger.setLevel(log_level)
    
    # Add file handler if LOG_FILE is specified
    log_file = os.getenv('LOG_FILE')
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger

def get_env(key: str, default: Any = None, required: bool = False) -> Any:
    """
    Get environment variable with type conversion and validation.
    
    Args:
        key: Environment variable name
        default: Default value if not found
        required: If True, raises ValueError when the variable is not found
        
    Returns:
        The value of the environment variable
        
    Raises:
        ValueError: If required is True and the variable is not found
    """
    value = os.getenv(key)
    
    if value is None:
        if required:
            raise ValueError(f"Required environment variable '{key}' is not set")
        return default
        
    return value
    
def get_env_int(key: str, default: int = None, required: bool = False) -> int:
    """Get environment variable as integer."""
    value = get_env(key, None, required)
    
    if value is None:
        return default
        
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Environment variable '{key}' should be an integer, got '{value}'")
        
def get_env_bool(key: str, default: bool = None, required: bool = False) -> bool:
    """Get environment variable as boolean."""
    value = get_env(key, None, required)
    
    if value is None:
        return default
        
    return value.lower() in ('true', 'yes', '1', 'y')
    
def get_env_list(key: str, delimiter: str = ',', default: list = None, required: bool = False) -> list:
    """Get environment variable as a list."""
    value = get_env(key, None, required)
    
    if value is None:
        return default or []
        
    return [item.strip() for item in value.split(delimiter) if item.strip()]

def get_cloudflare_config() -> Dict[str, Any]:
    """Get Cloudflare configuration from environment variables."""
    return {
        'api_token': get_env('CLOUDFLARE_API_TOKEN', required=True),
        'email': get_env('CERTBOT_EMAIL'),
    }

# Initialize logger at module level for convenience
logger = setup_logging() 