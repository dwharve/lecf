"""Certificate manager for Let's Encrypt certificates using Cloudflare DNS validation."""

import os
import subprocess
from datetime import datetime, timedelta
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

        # Get certbot email from config or environment
        self.email = config.get_config_value(
            config.APP_CONFIG,
            "certificate",
            "email",
            env_key="CERTBOT_EMAIL",
            required=True,
        )

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

        # Check if staging environment should be used
        self.staging = config.get_config_value(
            config.APP_CONFIG,
            "certificate",
            "use_staging",
            env_key="CERTBOT_STAGING",
            default=False,
        )

        # Initialize Cloudflare client
        self.cloudflare = CloudflareClient()

        logger.debug(f"Certificate manager initialized for {len(self.domains)} domain groups")

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

    def obtain_certificate(self, domains: List[str]) -> bool:
        """
        Obtain a new certificate for the specified domains.

        Args:
            domains: List of domains to include in the certificate

        Returns:
            True if successful, False otherwise
        """
        try:
            primary_domain = domains[0]
            logger.debug(
                f"Starting certificate acquisition",
                extra={"domains": domains, "primary_domain": primary_domain},
            )

            # Build certbot command
            cmd = [
                "certbot",
                "certonly",
                "--dns-cloudflare",
                "--dns-cloudflare-credentials",
                "/root/.secrets/cloudflare.ini",
                "--email",
                self.email,
                "--agree-tos",
                "--non-interactive",
            ]

            # Add staging flag if enabled
            if self.staging:
                cmd.append("--staging")
                logger.debug(
                    f"Using staging environment for certificate",
                    extra={"domains": domains, "staging": True},
                )

            # Check if any of the domains are wildcards
            has_wildcard = any("*" in domain for domain in domains)
            if has_wildcard:
                # For wildcard certificates, we need the ACME v2 endpoint
                cmd.extend(["--server", "https://acme-v02.api.letsencrypt.org/directory"])
                cmd.extend(["--dns-cloudflare-propagation-seconds", "60"])
                logger.debug(
                    f"Using wildcard certificate configuration",
                    extra={"domains": domains, "wildcard": True, "propagation_wait": 60},
                )

            # Add all domains to the certificate
            for domain in domains:
                cmd.extend(["-d", domain])

            logger.debug(
                f"Executing certbot command",
                extra={"domains": domains, "command": " ".join(cmd)},
            )

            # Log at INFO level that we're obtaining a certificate
            logger.info(
                f"Obtaining certificate for domains",
                extra={"domains": domains, "primary_domain": primary_domain},
            )

            # Execute certbot command
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.debug(
                    f"Certbot output for successful certificate acquisition",
                    extra={"domains": domains, "stdout": result.stdout},
                )
                logger.info(
                    f"Successfully obtained certificate",
                    extra={"domains": domains, "primary_domain": primary_domain},
                )
                return True

            logger.debug(
                f"Certbot error output for failed certificate acquisition",
                extra={
                    "domains": domains,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                },
            )
            logger.error(
                f"Failed to obtain certificate",
                extra={
                    "domains": domains,
                    "primary_domain": primary_domain,
                    "error": result.stderr,
                },
            )
            return False

        except Exception as e:
            logger.error(
                f"Error obtaining certificate",
                extra={"domains": domains, "error": str(e), "error_type": type(e).__name__},
            )
            return False

    def check_certificate_expiry(self, domains: List[str]) -> bool:
        """
        Check if certificate for domains exists and needs renewal.

        Args:
            domains: List of domains in the certificate

        Returns:
            True if certificate needs to be renewed or obtained, False otherwise
        """
        try:
            primary_domain = domains[0]
            logger.debug(
                f"Checking certificate expiry",
                extra={"domains": domains, "primary_domain": primary_domain},
            )

            # Use the primary domain to check the certificate
            cmd = ["certbot", "certificates", "--domain", primary_domain]
            logger.debug(
                f"Executing certbot check command",
                extra={
                    "domains": domains,
                    "primary_domain": primary_domain,
                    "command": " ".join(cmd),
                },
            )

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.debug(
                    f"Certbot check output",
                    extra={
                        "domains": domains,
                        "primary_domain": primary_domain,
                        "stdout": result.stdout,
                    },
                )

                # Check if certificate exists
                if "No certificates found." in result.stdout:
                    logger.info(
                        f"No certificate found, will obtain new one",
                        extra={"domains": domains, "primary_domain": primary_domain},
                    )
                    return True

                # Extract the domains in the certificate
                cert_domains = []
                if "Domains:" in result.stdout:
                    domains_section = result.stdout.split("Domains:")[1].split("\n")[0].strip()
                    cert_domains = [d.strip() for d in domains_section.split() if d.strip()]
                    logger.debug(
                        f"Found domains in certificate",
                        extra={"domains": domains, "cert_domains": cert_domains},
                    )

                # Check if all required domains are in the certificate
                missing_domains = [d for d in domains if d not in cert_domains]
                if missing_domains:
                    logger.info(
                        f"Certificate missing domains, will obtain new certificate",
                        extra={"domains": domains, "missing_domains": missing_domains},
                    )
                    return True

                # Parse the output and check for expiration date
                if "VALID: " in result.stdout:
                    expiration_part = result.stdout.split("VALID: ")[1].split("\n")[0]
                    logger.debug(
                        f"Found expiration date in certbot output",
                        extra={
                            "domains": domains,
                            "primary_domain": primary_domain,
                            "expiration_str": expiration_part,
                        },
                    )

                    try:
                        # Try to handle different date formats
                        if "days)" in expiration_part:
                            # Format like "89 days)" - extract the number of days
                            days_str = expiration_part.split(" ")[0]
                            days_to_expiry = int(days_str)
                            logger.debug(
                                f"Parsed days to expiry from certbot output",
                                extra={
                                    "domains": domains,
                                    "primary_domain": primary_domain,
                                    "days_to_expiry": days_to_expiry,
                                },
                            )
                        else:
                            # Original format assumed to be YYYY-MM-DD
                            expiration_date = datetime.strptime(expiration_part, "%Y-%m-%d")
                            days_to_expiry = (expiration_date - datetime.now()).days
                            logger.debug(
                                f"Parsed expiration date from certbot output",
                                extra={
                                    "domains": domains,
                                    "primary_domain": primary_domain,
                                    "expires_on": expiration_date.isoformat(),
                                    "days_to_expiry": days_to_expiry,
                                },
                            )

                        logger.debug(
                            f"Certificate expiration analysis",
                            extra={
                                "domains": domains,
                                "primary_domain": primary_domain,
                                "expiration_str": expiration_part,
                                "days_to_expiry": days_to_expiry,
                                "renewal_threshold": self.renewal_threshold,
                            },
                        )

                        if days_to_expiry <= self.renewal_threshold:
                            logger.info(
                                f"Certificate needs renewal",
                                extra={
                                    "domains": domains,
                                    "primary_domain": primary_domain,
                                    "days_to_expiry": days_to_expiry,
                                },
                            )
                            return True

                        logger.info(
                            f"Certificate is valid and not due for renewal",
                            extra={
                                "domains": domains,
                                "primary_domain": primary_domain,
                                "days_to_expiry": days_to_expiry,
                            },
                        )
                        return False
                    except ValueError as e:
                        logger.error(
                            f"Failed to parse expiration date",
                            extra={
                                "domains": domains,
                                "primary_domain": primary_domain,
                                "expiration_str": expiration_part,
                                "error": str(e),
                            },
                        )
                        # Since we couldn't parse the date, let's take a cautious approach
                        logger.info(
                            f"Unable to determine certificate expiration, assuming renewal needed",
                            extra={"domains": domains, "primary_domain": primary_domain},
                        )
                        return True
                else:
                    logger.warning(
                        f"Could not find expiration date in certbot output",
                        extra={
                            "domains": domains,
                            "primary_domain": primary_domain,
                            "stdout": result.stdout,
                        },
                    )
                    # No valid certificate found, obtain a new one
                    logger.info(
                        f"No valid certificate found, will obtain new one",
                        extra={"domains": domains, "primary_domain": primary_domain},
                    )
                    return True
            else:
                logger.warning(
                    f"Error checking certificate, will obtain new one",
                    extra={
                        "domains": domains,
                        "primary_domain": primary_domain,
                        "stderr": result.stderr,
                    },
                )
                return True

        except Exception as e:
            logger.error(
                f"Error checking certificate",
                extra={"domains": domains, "error": str(e), "error_type": type(e).__name__},
            )
            # Assume we need to renew if there's an error
            return True

    def _execute_cycle(self) -> None:
        """Implement the certificate renewal cycle."""
        logger.debug("Starting certificate renewal cycle")

        for i, domain_group in enumerate(self.domains):
            domain_list = list(domain_group)
            primary_domain = domain_list[0]

            logger.debug(
                f"Checking certificate {i+1}/{len(self.domains)}",
                extra={"domains": domain_list, "primary_domain": primary_domain},
            )

            # Check if certificate needs renewal
            if self.check_certificate_expiry(domain_list):
                # Attempt to obtain/renew certificate
                self.obtain_certificate(domain_list)

        # Track state
        self.last_check_time = datetime.now()
