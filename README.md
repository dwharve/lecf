# Let's Encrypt Certificate Manager with Cloudflare DNS

A microservice that automatically manages Let's Encrypt certificates using Cloudflare DNS validation. This service supports multiple domains and wildcard certificates. It now also includes DDNS (Dynamic DNS) functionality to keep your Cloudflare DNS records updated with your current IP address.

## Features

- Automatic certificate renewal
- Cloudflare DNS validation
- Support for multiple domains
- Support for wildcard certificates
- Dynamic DNS (DDNS) updates for multiple domains
- Secure credential management
- Detailed logging
- Configurable renewal intervals
- Docker support for easy deployment
- Unified architecture with inheritance-based design
- Modular architecture with shared components
- Centralized scheduling for better resource management
- YAML configuration for more complex setups
- Flexible credential management (keep in .env or config.yaml)

## Prerequisites

- Python 3.8+ (for local development)
- Docker and Docker Compose (for containerized deployment)
- Cloudflare account with API token
- Root access (for certificate operations)

## Installation

### Local Installation

1. Clone this repository
2. Set up the development environment:
   ```powershell
   # Run the setup script
   .\activate.ps1
   ```
   
   This will:
   - Create a virtual environment
   - Install the package in development mode
   - Install all required dependencies
   
3. Create your configuration files:
   ```powershell
   Copy-Item .env.example .env
   Copy-Item config.yaml.example config.yaml
   ```
   
4. Edit the `.env` file with your sensitive configuration
5. Edit the `config.yaml` file with your general configuration

### Installation from PyPI (when published)

```bash
pip install lecf
```

### Docker Installation

1. Clone this repository
2. Use the management script to set up Docker:
   ```powershell
   .\manage.ps1 -Action setup -Environment docker
   ```
   
   This will:
   - Build the Docker images
   
3. Create your configuration files:
   ```powershell
   Copy-Item .env.example .env
   Copy-Item config.yaml.example config.yaml
   ```
   
4. Edit the `.env` file with your sensitive configuration
5. Edit the `config.yaml` file with your general configuration

## Configuration

LECF now uses a dual configuration approach:

1. **Sensitive data** is typically stored in `.env` file
2. **General configuration** is stored in `config.yaml` file

### Environment Variables (`.env`)

The `.env` file typically contains sensitive information like API tokens:

```
# Required Configuration
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token  # Can also be in config.yaml
CERTBOT_EMAIL=your_email@example.com  # Can also be in config.yaml
```

### YAML Configuration (`config.yaml`)

The `config.yaml` file contains all general configuration and supports more complex structures:

```yaml
# Domains Configuration
domains:
  - example.com,www.example.com  # Domain group 1
  - another.com,*.another.com    # Domain group 2 with wildcard

# DDNS Configuration
ddns:
  domains: example.com:@,www;another.com:@,sub
  check_interval_minutes: 15
  record_types: A

# Certificate Configuration
certificate:
  renewal_threshold_days: 30
  check_interval_hours: 12
  cert_dir: /etc/letsencrypt/live

# Cloudflare Configuration
cloudflare:
  email: your_email@example.com  # Used for certificate registration
  # You can specify the API token here, though it's more secure in .env
  # api_token: your_cloudflare_api_token

# Logging Configuration
logging:
  level: INFO
  # file: /var/log/lecf.log  # Uncomment to enable file logging
```

### Configuration Precedence

LECF will look for configuration in the following order:
1. YAML configuration file
2. Environment variables
3. Default values

This allows you to use whichever approach is most convenient for your setup.

### Security Considerations for API Token

For best security, we recommend storing the Cloudflare API token in the `.env` file rather than in the YAML configuration. However, both options are supported:

1. **More Secure**: Store the API token in `.env` file only
2. **More Convenient**: Store the API token in `config.yaml` under the `cloudflare` section

The system will check both locations and use whichever one is specified.

### DDNS Configuration

The DDNS feature requires the following configuration in your `config.yaml` file:

#### Configuration Format

DDNS configuration must be defined in the `config.yaml` file using the following format:

```yaml
ddns:
  domains:
    - domain: example.com
      subdomains: "@,www"
      record_types: A,AAAA  # This domain gets both IPv4 and IPv6 records
    - domain: another-example.com
      subdomains: "@,subdomain"
      record_types: A       # This domain gets only IPv4 records
  check_interval_minutes: 15
```

This allows you to:
- Configure different record types for different domains
- Configure some domains with IPv4 only (A records)
- Configure other domains with both IPv4 and IPv6 (A and AAAA records)
- Add TXT or other record types as needed per domain

If no record types are specified for a domain, A records (IPv4) will be used by default.

This will update the following DNS records when your IP changes:
- example.com (A and AAAA records)
- www.example.com (A and AAAA records)
- another-example.com (A records only)
- subdomain.another-example.com (A records only)

## Security Considerations

- The Cloudflare API token can be stored in either `.env` file (more secure) or YAML configuration
- API token stored in `/root/.secrets/cloudflare.ini` with secure permissions
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