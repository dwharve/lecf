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

## Prerequisites

- Python 3.8+ (for local development)
- Docker and Docker Compose (for containerized deployment)
- Cloudflare account with API token
- Root access (for certificate operations)

## Installation

### Local Installation

1. Clone this repository
2. Use the management script to set up the environment:
   ```powershell
   .\manage.ps1 -Action setup -Environment local
   ```
   
   This will:
   - Create a virtual environment
   - Install the required Python packages
   - Create a `.env` file from the template

### Docker Installation

1. Clone this repository
2. Use the management script to set up Docker:
   ```powershell
   .\manage.ps1 -Action setup -Environment docker
   ```
   
   This will:
   - Build the Docker images
   
3. Create your `.env` file:
   ```powershell
   Copy-Item .env.example .env
   ```
   
4. Edit the `.env` file with your configuration

## Configuration

1. Copy `.env.example` to `.env` (if not already done in setup):
   ```powershell
   Copy-Item .env.example .env
   ```

2. Edit `.env` and configure:
   - `CLOUDFLARE_API_TOKEN`: Your Cloudflare API token
   - `CERTBOT_EMAIL`: Your email address
   - `DOMAINS`: Comma-separated list of domains for certificates
   - `DDNS_DOMAINS`: Domains for DDNS updates (format: `domain.com:@,www;another.com:@,sub`)
   - Other settings as needed

## Usage

### Using the Management Script

The system includes a PowerShell management script (`manage.ps1`) that provides a unified interface for both local and Docker environments:

```powershell
.\manage.ps1 -Action [action] -Service [service] -Environment [environment]
```

Where:
- `[action]` is one of: `start`, `stop`, `restart`, `status`, `logs`, `build`, or `setup`
- `[service]` is one of: `all`, `cert`, `ddns`, or `docker` (default: `all`)
- `[environment]` is one of: `local` or `docker` (default: `local`)

Examples:

```powershell
# Set up the local environment
.\manage.ps1 -Action setup -Environment local

# Start all services locally
.\manage.ps1 -Action start -Service all

# Start only the DDNS service locally
.\manage.ps1 -Action start -Service ddns

# Start all services in Docker
.\manage.ps1 -Action start -Environment docker

# Show logs for the certificate manager in Docker
.\manage.ps1 -Action logs -Service cert -Environment docker

# Stop all Docker services
.\manage.ps1 -Action stop -Environment docker
```

### Manual Local Usage

Run the main script directly:
```powershell
python main.py --service [service]
```

Where `[service]` is one of: `all`, `cert`, or `ddns` (default: `all`)

### Manual Docker Usage

Start all services:
```powershell
docker-compose up -d
```

Start only the certificate manager:
```powershell
docker-compose up -d cert-manager
```

Start only the DDNS manager:
```powershell
docker-compose up -d ddns-manager
```

Start the all-in-one service (both managers in one container):
```powershell
docker-compose up -d all-in-one
```

View logs:
```powershell
docker-compose logs -f
```

Stop all services:
```powershell
docker-compose down
```

## System Architecture

The system consists of the following components:

1. **Base Manager**: Abstract base class defining the service manager interface
2. **Certificate Manager**: Handles Let's Encrypt certificate issuance and renewal using Cloudflare DNS for validation
3. **DDNS Manager**: Updates Cloudflare DNS records with your current public IP address
4. **Shared Utilities**: Common utilities for logging, configuration, and Cloudflare API interaction
5. **Main Entry Point**: A unified script that runs and schedules all services
6. **Management Script**: A PowerShell script for easy management of all components

The system uses a modular architecture with these main components:

- **base_manager.py**: Abstract base class that all service managers inherit from
- **utils.py**: Shared utilities for logging, environment variable handling, and configuration
- **cloudflare_client.py**: Shared client for Cloudflare API interaction
- **certificate_manager.py**: Certificate management functionality 
- **ddns_manager.py**: DDNS update functionality
- **main.py**: Entry point that discovers, initializes and schedules all service managers
- **manage.ps1**: PowerShell management interface

All scheduling is centralized in the main module using a common interface defined by the BaseManager class. This ensures consistent behavior across services and makes adding new service types straightforward.

### Service Manager Hierarchy

```
     ┌───────────────┐
     │  BaseManager  │
     └───────┬───────┘
             │
     ┌───────┴───────┐
     │               │
┌────▼────┐    ┌─────▼────┐
│Certificate│   │  DDNS    │
│ Manager   │   │ Manager  │
└───────────┘   └──────────┘
```

Each manager:
1. Inherits from BaseManager
2. Implements `_setup_interval()` to define its scheduling requirements
3. Implements `_execute_cycle()` to perform its specific operations
4. Uses the common `run()` method for consistent execution flow

### Simplified Deployment

With the new unified architecture, there's only one way to run the application - with all services enabled. This simplifies deployment, reduces configuration complexity, and ensures consistent behavior across environments.

## Testing and Linting

The system includes comprehensive testing and linting tools to ensure code quality and reliability.

### Running Tests

Use the management script to run tests:

```powershell
# Run all tests
.\manage.ps1 -Action test -Service all

# Run only utility tests
.\manage.ps1 -Action test -Service utils

# Run only base manager tests
.\manage.ps1 -Action test -Service base
```

The tests cover:
- Utility modules (utils.py, cloudflare_client.py)
- Base Manager functionality
- Scheduling mechanisms

### Linting the Code

The system uses flake8 and mypy for code quality checks:

```powershell
# Lint all code
.\manage.ps1 -Action lint -Service all

# Lint only utils
.\manage.ps1 -Action lint -Service utils

# Lint only manager modules
.\manage.ps1 -Action lint -Service managers

# Lint only test modules
.\manage.ps1 -Action lint -Service tests
```

Linting helps ensure:
- Consistent code style
- Type safety
- Best practices adherence

## Certificate Storage

When using Docker, certificates are stored in the `./certificates` directory, which is mounted as a volume to `/etc/letsencrypt` in the container. This ensures that certificates persist between container restarts.

## Logging

Logs are output in JSON format and include:
- Certificate operations
- DNS record management
- DDNS updates
- Errors and warnings
- Renewal attempts

## DDNS Configuration

The DDNS manager supports updating multiple domains and subdomains with your current public IP address. Configure it using these environment variables:

- `DDNS_DOMAINS`: Domains and subdomains to update in the format: `domain.com:subdomain1,subdomain2;domain2.com:subdomain1,@`
  - Use `@` to represent the root domain
  - Separate domains with semicolons (`;`)
  - Separate subdomains with commas (`,`)
- `DDNS_CHECK_INTERVAL_MINUTES`: How often to check for IP changes (default: 15 minutes)
- `DDNS_RECORD_TYPES`: DNS record types to update (default: A)

Example configuration:
```
DDNS_DOMAINS=example.com:@,www,home;anotherdomain.com:@,www
DDNS_CHECK_INTERVAL_MINUTES=15
DDNS_RECORD_TYPES=A
```

This will update the following DNS records when your IP changes:
- example.com
- www.example.com
- home.example.com
- anotherdomain.com
- www.anotherdomain.com

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