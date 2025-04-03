"""Setup Cloudflare credentials for certbot."""

import os
import stat
from pathlib import Path
from typing import Optional

from lecf.utils import config, logger


def setup_cloudflare_credentials():
    """Set up Cloudflare credentials file for certbot."""
    # Create .secrets directory if it doesn't exist
    secrets_dir = Path("/root/.secrets")
    try:
        secrets_dir.mkdir(parents=True, exist_ok=True)

        # Get Cloudflare configuration from YAML or environment variables
        cf_config = config.get_cloudflare_config(config.APP_CONFIG)

        # Get API token and email
        api_token = cf_config["api_token"]
        email = cf_config.get("email")

        # Create cloudflare.ini file
        cloudflare_ini = secrets_dir / "cloudflare.ini"

        # Write credentials to file using the correct key name (with underscores, not hyphens)
        with open(cloudflare_ini, "w", encoding="utf-8") as f:
            f.write(f"dns_cloudflare_api_token = {api_token}\n")
            if email:
                f.write(f"dns_cloudflare_email = {email}\n")

        # Set secure permissions (readable only by root)
        os.chmod(cloudflare_ini, stat.S_IRUSR | stat.S_IWUSR)

        logger.info(
            "Cloudflare credentials file created successfully", extra={"path": str(cloudflare_ini)}
        )
    except Exception as e:
        logger.error(
            "Failed to create Cloudflare credentials file",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        raise


def get_cloudflare_email() -> Optional[str]:
    """
    Get Cloudflare email from YAML config or environment variables.

    Returns:
        Email address or None if not specified
    """
    # Use new configuration function to get email
    cf_config = config.get_cloudflare_config(config.APP_CONFIG)
    return cf_config.get("email")


if __name__ == "__main__":
    from lecf.utils import setup_logging

    setup_logging()
    setup_cloudflare_credentials()
