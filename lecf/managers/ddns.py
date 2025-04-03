"""DDNS manager for updating Cloudflare DNS records with your current IP address."""

from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from lecf.core import BaseManager, CloudflareClient
from lecf.utils import config, get_env, get_env_int, logger


class DdnsManager(BaseManager):
    """DDNS manager for updating Cloudflare DNS records with the current public IP."""

    def __init__(self):
        """Initialize the DDNS manager."""
        super().__init__("ddns")

        # Parse domains configuration
        domains_config = self._get_domains_config()
        self.domains = self._parse_domains(domains_config)

        # Initialize Cloudflare client
        self.cloudflare = CloudflareClient()

        # Default record type is always A
        self.default_record_types = ["A"]

        # External IP check service URLs (we'll try them in order)
        self.ip_check_services = [
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://icanhazip.com",
            "https://checkip.amazonaws.com",
        ]

        # Track state
        self.current_ip = None
        self.last_check_time = None

        logger.debug(f"DDNS manager initialized for {len(self.domains)} domains")

    def _setup_interval(self) -> None:
        """Set up the check interval for DDNS updates."""
        self.check_interval = config.get_config_value(
            config.APP_CONFIG,
            "ddns",
            "check_interval_minutes",
            env_key="DDNS_CHECK_INTERVAL_MINUTES",
            default=15,
        )
        self.interval_unit = "minutes"

        logger.debug(
            f"DDNS check interval configured",
            extra={"interval": self.check_interval, "unit": self.interval_unit},
        )

    def _get_domains_config(self) -> List[Dict[str, Any]]:
        """
        Get DDNS domains configuration from YAML.

        Returns:
            List of domain config dictionaries
        """
        if "ddns" in config.APP_CONFIG and "domains" in config.APP_CONFIG["ddns"]:
            return config.APP_CONFIG["ddns"]["domains"]

        # No fallback - require the new format
        logger.error("Missing DDNS domains configuration in config.yaml")
        return []

    def _parse_domains(self, domains_config: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Parse the domains configuration.

        Format for dict config:
            [
                {
                    "domain": "domain.com",
                    "subdomains": "@,www",
                    "record_types": "A,AAAA"
                },
                {
                    "domain": "another.com",
                    "subdomains": "@,sub"
                }
            ]

        Returns:
            Dict mapping domains to their configuration
        """
        result = {}

        # Only handle new format (list of dicts)
        for domain_entry in domains_config:
            if not isinstance(domain_entry, dict):
                logger.warning(
                    f"Invalid domain configuration entry",
                    extra={"entry": domain_entry, "reason": "not_dict"},
                )
                continue

            domain = domain_entry.get("domain")
            if not domain:
                logger.warning(
                    f"Invalid domain configuration",
                    extra={"entry": domain_entry, "reason": "missing_domain"},
                )
                continue

            # Parse subdomains
            subdomains_str = domain_entry.get("subdomains", "@")
            subdomains = (
                [s.strip() for s in subdomains_str.split(",") if s.strip()]
                if isinstance(subdomains_str, str)
                else subdomains_str
            )

            if not subdomains:
                logger.warning(
                    f"Invalid domain configuration",
                    extra={"domain": domain, "reason": "no_subdomains"},
                )
                continue

            # Parse record types
            record_types_str = domain_entry.get("record_types")
            record_types = None
            if record_types_str:
                if isinstance(record_types_str, str):
                    record_types = [rt.strip() for rt in record_types_str.split(",") if rt.strip()]
                elif isinstance(record_types_str, list):
                    record_types = record_types_str

            # Store domain config
            result[domain] = {
                "subdomains": subdomains,
                "record_types": record_types,  # None means use default
            }

        return result

    def get_public_ip(self) -> Optional[str]:
        """
        Get the current public IP address using various services.

        Returns:
            Current public IP address or None if all services fail
        """
        for service_url in self.ip_check_services:
            try:
                logger.debug(f"Checking public IP using service", extra={"service": service_url})
                response = requests.get(service_url, timeout=10)

                if response.status_code == 200:
                    ip = response.text.strip()
                    logger.debug(f"Public IP found", extra={"ip": ip})
                    return ip
            except Exception as e:
                logger.debug(
                    f"Failed to get IP from service",
                    extra={"service": service_url, "error": str(e)},
                )
                continue

        logger.error("Failed to get public IP from all services")
        return None

    def update_dns_record(self, domain: str, subdomain: str, record_type: str, ip: str) -> bool:
        """
        Update a specific DNS record with the new IP.

        Args:
            domain: Domain name (zone name)
            subdomain: Subdomain to update (@ for root domain)
            record_type: DNS record type (A, AAAA, etc.)
            ip: IP address to set

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get zone ID
            zone_id, zone_name = self.cloudflare.get_zone_id(domain)
            if not zone_id:
                logger.error(f"No zone found for domain", extra={"domain": domain})
                return False

            # Handle root domain (@) special case
            record_name = domain if subdomain == "@" else f"{subdomain}.{domain}"

            logger.debug(
                f"Updating DNS record",
                extra={
                    "domain": domain,
                    "record_name": record_name,
                    "record_type": record_type,
                    "subdomain": subdomain,
                },
            )

            # Find existing record
            params = {"name": record_name, "type": record_type}

            # Get existing records
            dns_records = self.cloudflare.get_dns_records(zone_id, params)

            if dns_records:
                # Update existing record
                record_id = dns_records[0]["id"]
                current_ip = dns_records[0]["content"]

                logger.debug(
                    f"Existing record details",
                    extra={
                        "record_id": record_id,
                        "current_ip": current_ip,
                        "new_ip": ip,
                        "record_name": record_name,
                    },
                )

                if current_ip == ip:
                    logger.debug(
                        f"IP unchanged, skipping update",
                        extra={"record_name": record_name, "ip": ip},
                    )
                    return True

                record = {
                    "name": record_name,
                    "type": record_type,
                    "content": ip,
                    "ttl": 60,  # Short TTL for DDNS
                    "proxied": dns_records[0].get("proxied", False),  # Maintain proxy status
                }

                logger.debug(
                    f"Updating existing DNS record",
                    extra={"record_id": record_id, "record": record},
                )

                success = self.cloudflare.update_dns_record(zone_id, record_id, record)
                if success:
                    logger.info(
                        f"Updated DNS record",
                        extra={"record_type": record_type, "record_name": record_name, "ip": ip},
                    )
                    return True

                logger.error(
                    f"Failed to update DNS record",
                    extra={"record_name": record_name, "record_id": record_id},
                )
                return False

            # Create new record
            record = {
                "name": record_name,
                "type": record_type,
                "content": ip,
                "ttl": 60,
                "proxied": False,
            }

            logger.debug(f"Creating new DNS record", extra={"zone_id": zone_id, "record": record})

            record_id = self.cloudflare.create_dns_record(zone_id, record)
            if record_id:
                logger.info(
                    f"Created new DNS record",
                    extra={"record_type": record_type, "record_name": record_name, "ip": ip},
                )
                return True

            logger.error(f"Failed to create DNS record", extra={"record_name": record_name})
            return False

        except Exception as e:
            logger.error(
                f"Failed to update DNS record",
                extra={
                    "domain": domain,
                    "subdomain": subdomain,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return False

    def _execute_cycle(self) -> None:
        """Implement the DDNS update cycle."""
        logger.debug("Starting DDNS update cycle")

        # Get current public IP
        ip = self.get_public_ip()
        if not ip:
            logger.error("Could not update domains: failed to get public IP")
            return

        # Skip update if IP hasn't changed since last check
        if ip == self.current_ip:
            logger.debug("IP unchanged since last check, skipping updates")
            self.last_check_time = datetime.now()
            return

        # Log if IP has changed
        if self.current_ip is not None:
            logger.info(
                f"Public IP address changed", extra={"previous_ip": self.current_ip, "new_ip": ip}
            )
        else:
            logger.info(f"Initial IP address detected", extra={"ip": ip})

        update_count = 0
        error_count = 0

        # Process each domain
        for domain, config in self.domains.items():
            logger.debug(
                f"Processing domain",
                extra={"domain": domain, "subdomains": config.get("subdomains")},
            )

            # Get record types to update
            record_types = config.get("record_types") or self.default_record_types

            # Update each subdomain
            for subdomain in config.get("subdomains", []):
                for record_type in record_types:
                    success = self.update_dns_record(domain, subdomain, record_type, ip)

                    if success:
                        update_count += 1
                    else:
                        error_count += 1

        # Log summary
        logger.info(
            f"DDNS update completed",
            extra={"updated": update_count, "errors": error_count, "domains": len(self.domains)},
        )

        # Track state
        self.current_ip = ip
        self.last_check_time = datetime.now()
