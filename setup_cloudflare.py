import os
import stat
from pathlib import Path
from dotenv import load_dotenv

def setup_cloudflare_credentials():
    """Set up Cloudflare credentials file for certbot."""
    load_dotenv()
    
    # Create .secrets directory if it doesn't exist
    secrets_dir = Path('/root/.secrets')
    secrets_dir.mkdir(parents=True, exist_ok=True)
    
    # Create cloudflare.ini file
    cloudflare_ini = secrets_dir / 'cloudflare.ini'
    
    # Write credentials to file
    with open(cloudflare_ini, 'w') as f:
        f.write(f"dns-cloudflare-api-token = {os.getenv('CLOUDFLARE_API_TOKEN')}\n")
    
    # Set secure permissions (readable only by root)
    os.chmod(cloudflare_ini, stat.S_IRUSR | stat.S_IWUSR)
    
    print("Cloudflare credentials file created successfully at /root/.secrets/cloudflare.ini")

if __name__ == "__main__":
    setup_cloudflare_credentials() 