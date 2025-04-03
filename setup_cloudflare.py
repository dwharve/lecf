import os
import stat
from pathlib import Path

# Import shared modules
from utils import logger, get_env

def setup_cloudflare_credentials():
    """Set up Cloudflare credentials file for certbot."""
    # Create .secrets directory if it doesn't exist
    secrets_dir = Path('/root/.secrets')
    try:
        secrets_dir.mkdir(parents=True, exist_ok=True)
        
        # Get API token from environment
        api_token = get_env('CLOUDFLARE_API_TOKEN', required=True)
        
        # Create cloudflare.ini file
        cloudflare_ini = secrets_dir / 'cloudflare.ini'
        
        # Write credentials to file using the correct key name (with underscores, not hyphens)
        with open(cloudflare_ini, 'w') as f:
            f.write(f"dns_cloudflare_api_token = {api_token}\n")
        
        # Set secure permissions (readable only by root)
        os.chmod(cloudflare_ini, stat.S_IRUSR | stat.S_IWUSR)
        
        logger.info("Cloudflare credentials file created successfully", 
                  extra={'path': str(cloudflare_ini)})
    except Exception as e:
        logger.error("Failed to create Cloudflare credentials file", 
                   extra={'error': str(e), 'error_type': type(e).__name__})
        raise

if __name__ == "__main__":
    from utils import setup_logging
    setup_logging()
    setup_cloudflare_credentials() 