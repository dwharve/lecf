"""DDNS manager for updating Cloudflare DNS records with your current IP address."""

from datetime import datetime
from typing import Any, Dict, List

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

        # Track state
        self.current_ip = None
        self.last_check_time = None

        logger.info(f"DDNS manager initialized for {len(self.domains)} domains")

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

    def _execute_cycle(self) -> None:
        """Implement the DDNS update cycle."""
        logger.debug("Starting DDNS update cycle")

        # In a real implementation, this would:
        # 1. Get the current public IP address
        # 2. Compare with previously stored IP
        # 3. If different, update DNS records for all configured domains

        # For each domain, log the record types that will be updated
        for domain, config in self.domains.items():
            record_types = config.get("record_types") or self.default_record_types
            logger.info(
                f"Would update DNS records for domain",
                extra={
                    "domain": domain,
                    "subdomains": config.get("subdomains"),
                    "record_types": record_types,
                },
            )

        # Track state
        self.current_ip = "127.0.0.1"  # Placeholder
        self.last_check_time = datetime.now()
