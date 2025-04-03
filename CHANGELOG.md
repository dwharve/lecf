# Changelog

## Version 0.2.1 - Flexible API Token Configuration

### Added
- Added ability to specify Cloudflare API token in either `.env` or `config.yaml`
- Added documentation about security considerations for API token placement

### Changed
- Updated configuration system to check YAML first, then environment variables
- Updated README with instructions for both configuration approaches
- Enhanced security documentation with best practices

## Version 0.2.0 - YAML Configuration Update

### Added
- New YAML configuration system (`config.yaml`)
- Ability to define complex configuration structures in YAML
- Configuration precedence system (YAML → Environment Variables → Defaults)
- Example YAML configuration file (`config.yaml.example`)

### Changed
- Moved non-sensitive configuration from `.env` to `config.yaml`
- Sensitive data still remains in `.env` for security
- Updated Docker setup to mount the YAML configuration file
- Updated managers to read from YAML configuration first
- Updated README with new configuration approach

### Dependencies
- Added PyYAML as a project dependency

## Version 0.1.0 - Initial Release

- Initial version with Let's Encrypt certificate management
- Cloudflare DNS validation
- DDNS (Dynamic DNS) functionality
- Docker support
- Environment variable configuration 