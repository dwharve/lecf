"""Configuration utilities for the LECF package."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Global application configuration
APP_CONFIG = {}


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


def get_env_bool(
    key: str, default: Optional[bool] = None, required: bool = False
) -> Optional[bool]:
    """Get environment variable as boolean."""
    value = get_env(key, None, required)

    if value is None:
        return default

    return value.lower() in ("true", "yes", "1", "y")


def get_env_int(key: str, default: Optional[int] = None, required: bool = False) -> Optional[int]:
    """Get environment variable as integer."""
    value = get_env(key, None, required)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable '{key}' is not a valid integer: {value}") from exc


def get_env_list(
    key: str,
    separator: str = ",",
    delimiter: str = None,  # For backward compatibility
    default: Optional[List[str]] = None,
    required: bool = False,
) -> Optional[List[str]]:
    """Get environment variable as list of strings."""
    value = get_env(key, None, required)

    if value is None:
        return default or []

    # Use delimiter if provided (for backward compatibility)
    sep = delimiter if delimiter is not None else separator

    return [item.strip() for item in value.split(sep) if item.strip()]


def get_cloudflare_config(yaml_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get Cloudflare configuration from YAML config or environment variables.

    Args:
        yaml_config: Optional YAML configuration dictionary

    Returns:
        Dictionary with Cloudflare configuration

    Raises:
        ValueError: If the API token is not found in either location and required
    """
    config = {}

    # First try to get API token from YAML config
    if yaml_config and "cloudflare" in yaml_config:
        cf_config = yaml_config["cloudflare"]
        if "api_token" in cf_config:
            config["api_token"] = cf_config["api_token"]
        if "email" in cf_config:
            config["email"] = cf_config["email"]

    # Fall back to environment variables for any missing values
    if "api_token" not in config:
        config["api_token"] = get_env("CLOUDFLARE_API_TOKEN", required=True)

    if "email" not in config:
        config["email"] = get_env("CERTBOT_EMAIL")

    return config


def load_yaml_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file. If None, looks in standard locations.

    Returns:
        Dictionary of configuration values

    Raises:
        FileNotFoundError: If the configuration file does not exist
        yaml.YAMLError: If the YAML file is invalid
    """
    if config_path is None:
        # Search for config in standard locations
        search_paths = [
            Path("config.yaml"),  # Current directory
            Path("config.yml"),
            Path("/app/config.yaml"),  # Docker container
            Path("/app/config.yml"),
            Path.home() / ".config" / "lecf" / "config.yaml",  # User config
            Path.home() / ".config" / "lecf" / "config.yml",
        ]

        for path in search_paths:
            if path.exists():
                config_path = str(path)
                break
        else:
            raise FileNotFoundError("Configuration file not found in standard locations")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Update the global APP_CONFIG
    result = config or {}
    APP_CONFIG.clear()
    APP_CONFIG.update(result)

    return result


def get_config_value(
    config: Dict[str, Any],
    section: str,
    key: str,
    env_key: Optional[str] = None,
    default: Any = None,
    required: bool = False,
) -> Any:
    """
    Get configuration value with fallback to environment variable.

    Args:
        config: Configuration dictionary from YAML
        section: Section name in YAML config
        key: Key name in the section
        env_key: Environment variable name to check as fallback
        default: Default value if not found in either location
        required: If True, raises ValueError when the value is not found

    Returns:
        The configuration value from YAML or environment

    Raises:
        ValueError: If required is True and the value is not found
    """
    # Check in YAML config first
    if section in config and key in config[section]:
        return config[section][key]

    # Fall back to environment variable if provided
    if env_key:
        return get_env(env_key, default, required)

    # Not found in either location
    if required:
        raise ValueError(f"Required configuration '{section}.{key}' not found")

    return default
