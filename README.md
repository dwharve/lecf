# Let's Encrypt Certificate Manager with Cloudflare DNS

A microservice that automatically manages Let's Encrypt certificates using Cloudflare DNS validation. This service supports multiple domains and wildcard certificates.

## Features

- Automatic certificate renewal
- Cloudflare DNS validation
- Support for multiple domains
- Support for wildcard certificates
- Secure credential management
- Detailed logging
- Configurable renewal intervals
- Docker support for easy deployment

## Prerequisites

- Python 3.8+ (for local development)
- Docker and Docker Compose (for containerized deployment)
- Cloudflare account with API token
- Root access (for certificate operations)

## Installation

### Local Installation

1. Clone this repository
2. Install the required Python packages:
   ```powershell
   python -m pip install -r requirements.txt
   ```
3. Install Certbot with Cloudflare plugin:
   ```powershell
   python -m pip install certbot certbot-dns-cloudflare
   ```

### Docker Installation

1. Clone this repository
2. Create your `.env` file:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Edit the `.env` file with your configuration
4. Build and run the container:
   ```powershell
   docker-compose up -d
   ```

## Configuration

1. Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```

2. Edit `.env` and configure:
   - `CLOUDFLARE_API_TOKEN`: Your Cloudflare API token
   - `CERTBOT_EMAIL`: Your email address
   - `DOMAINS`: Comma-separated list of domains
   - Other settings as needed

3. Set up Cloudflare credentials:
   ```powershell
   python setup_cloudflare.py
   ```

## Usage

### Local Usage

Run the certificate manager:
```powershell
python certificate_manager.py
```

### Docker Usage

Start the service:
```powershell
docker-compose up -d
```

View logs:
```powershell
docker-compose logs -f
```

Stop the service:
```powershell
docker-compose down
```

The service will:
- Check existing certificates
- Obtain new certificates if needed
- Automatically renew certificates before expiration
- Log all operations

## Certificate Storage

When using Docker, certificates are stored in the `./certificates` directory, which is mounted as a volume to `/etc/letsencrypt` in the container. This ensures that certificates persist between container restarts.

## Logging

Logs are output in JSON format and include:
- Certificate operations
- DNS record management
- Errors and warnings
- Renewal attempts

## Security Considerations

- The Cloudflare API token is stored securely in `/root/.secrets/cloudflare.ini`
- File permissions are set to be readable only by root
- Environment variables are used for sensitive configuration
- Staging environment support for testing
- Docker volumes for persistent storage of certificates

## Troubleshooting

1. Check the logs for detailed error messages
2. Verify Cloudflare API token permissions
3. Ensure domains are properly configured in Cloudflare
4. Check DNS propagation if validation fails
5. Use staging environment for testing (`CERTBOT_STAGING=true`)
6. For Docker issues, check container logs with `docker-compose logs -f`

## License

MIT License 