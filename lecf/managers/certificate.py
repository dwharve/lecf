"""Certificate manager for Let's Encrypt certificates using Cloudflare DNS validation."""

from datetime import datetime
from typing import List, Set

from lecf.core import BaseManager, CloudflareClient
from lecf.utils import config, get_env, get_env_int, logger


class CertificateManager(BaseManager):
    """Certificate manager for Let's Encrypt certificates using Cloudflare DNS validation."""

    def __init__(self):
        """Initialize the Certificate manager."""
        super().__init__("certificate")

        # Parse domains configuration
        domains_config = self._get_domains_config()
        self.domains = self._parse_domains(domains_config)

        # Get certbot email
        self.email = get_env("CERTBOT_EMAIL", required=True)

        # Set certificate paths
        self.cert_dir = config.get_config_value(
            config.APP_CONFIG,
            "certificate",
            "cert_dir",
            env_key="CERT_DIR",
            default="/etc/letsencrypt/live",
        )

        # Set renewal threshold (days before expiry to renew)
        self.renewal_threshold = config.get_config_value(
            config.APP_CONFIG,
            "certificate",
            "renewal_threshold_days",
            env_key="CERT_RENEWAL_THRESHOLD_DAYS",
            default=30,
        )

        # Initialize Cloudflare client
        self.cloudflare = CloudflareClient()

        logger.info(f"Certificate manager initialized for {len(self.domains)} domain groups")

    def _setup_interval(self) -> None:
        """Set up the check interval for certificate renewal checks."""
        self.check_interval = config.get_config_value(
            config.APP_CONFIG,
            "certificate",
            "check_interval_hours",
            env_key="CERT_CHECK_INTERVAL_HOURS",
            default=12,
        )
        self.interval_unit = "hours"

        logger.debug(
            f"Certificate check interval configured",
            extra={"interval": self.check_interval, "unit": self.interval_unit},
        )

    def _get_domains_config(self) -> str:
        """
        Get domains configuration from YAML or environment.

        Returns:
            String containing domains configuration
        """
        if "domains" in config.APP_CONFIG and config.APP_CONFIG["domains"]:
            # Convert YAML list to semicolon-separated string
            return ";".join(config.APP_CONFIG["domains"])

        # Fall back to environment variable
        return get_env("DOMAINS", required=True)

    def _parse_domains(self, domains_str: str) -> List[Set[str]]:
        """
        Parse the domains configuration string.

        Format: domain.com,www.domain.com;another.com
        Where:
        - domain.com,www.domain.com are domains that should be included in the same certificate
        - ; separates different certificates
        - , separates domains within the same certificate

        Returns:
            List of sets, where each set contains domains for a single certificate.
        """
        result = []

        # Split by semicolon to get individual certificate configs
        cert_configs = domains_str.split(";")

        for config_str in cert_configs:
            if not config_str.strip():
                continue

            # Split by comma to get domains for this certificate
            domains = {d.strip() for d in config_str.split(",") if d.strip()}

            if not domains:
                logger.warning(
                    f"Invalid certificate configuration",
                    extra={"config": config_str, "reason": "empty_domains"},
                )
                continue

            result.append(domains)

        return result

    def _execute_cycle(self) -> None:
        """Implement the certificate renewal cycle."""
        logger.debug("Starting certificate renewal cycle")

        # In a real implementation, this would:
        # 1. Check all certificates for expiry dates
        # 2. For certificates nearing expiry, initiate renewal
        # 3. Use Cloudflare DNS validation

        # For now, just log that we would do this
        for i, domains in enumerate(self.domains):
            cert_name = next(iter(domains))  # Use first domain as cert name

            logger.info(
                f"Would check certificate {i+1}/{len(self.domains)}",
                extra={"domains": list(domains), "primary_domain": cert_name},
            )

        # Track state
        self.last_check_time = datetime.now()
