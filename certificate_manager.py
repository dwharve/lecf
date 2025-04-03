import os
import subprocess
import time
from datetime import datetime, timedelta
from typing import List, Dict

# Import shared modules
from utils import logger, get_env, get_env_int, get_env_bool
from cloudflare_client import CloudflareClient
from base_manager import BaseManager

class CertificateManager(BaseManager):
    def __init__(self):
        # Initialize base class
        super().__init__("Certificate")
        
        # Initialize manager-specific attributes
        self.cloudflare = CloudflareClient()
        self.domain_groups = self._parse_domain_groups(get_env('DOMAINS', ''))
        self.email = get_env('CERTBOT_EMAIL')
        self.staging = get_env_bool('CERTBOT_STAGING', False)
        self.renewal_interval = get_env_int('RENEWAL_INTERVAL_DAYS', 30)
        
        # Log initialization parameters (without sensitive data)
        logger.debug("CertificateManager initialized", extra={
            'domain_groups': self.domain_groups,
            'staging': self.staging,
            'renewal_interval': self.renewal_interval,
            'check_interval': self.check_interval
        })
    
    def _setup_interval(self) -> None:
        """Set up the check interval for certificate renewals."""
        self.check_interval = get_env_int('RENEWAL_CHECK_INTERVAL_HOURS', 12)
        self.interval_unit = "hours"
    
    def _execute_cycle(self) -> None:
        """Execute a single certificate check and renewal cycle."""
        self.check_and_renew_all_certificates()

    def _parse_domain_groups(self, domains_str: str) -> List[List[str]]:
        """
        Parse domains string into groups of related domains.
        Format: domain1.com,*.domain1.com;domain2.com,*.domain2.com
        
        Semicolons separate certificate groups
        Commas separate domains within a group
        """
        if not domains_str:
            return []
            
        domain_groups = []
        groups = domains_str.split(';')
        
        for group in groups:
            if not group.strip():
                continue
                
            domains = [d.strip() for d in group.split(',') if d.strip()]
            if domains:
                domain_groups.append(domains)
                
        # If no explicit grouping (no semicolons), automatically group related domains
        if len(domain_groups) == 1 and ';' not in domains_str:
            domain_map = {}
            auto_groups = []
            
            # Group by root domain
            for domain in domain_groups[0]:
                # Extract root domain
                parts = domain.split('.')
                if len(parts) >= 2:
                    root_domain = parts[-2] + '.' + parts[-1]
                    if '*' in domain:
                        # Remove the asterisk for grouping
                        root_domain = root_domain
                        
                    if root_domain not in domain_map:
                        domain_map[root_domain] = []
                    domain_map[root_domain].append(domain)
            
            # Create groups from the map
            for domains in domain_map.values():
                auto_groups.append(domains)
                
            return auto_groups
        
        return domain_groups

    def setup_cloudflare_dns(self, domain: str, token: str) -> None:
        """Set up DNS validation for Cloudflare."""
        try:
            logger.debug(f"Setting up Cloudflare DNS for domain", 
                        extra={'domain': domain, 'action': 'setup_dns_start'})
            
            # Get zone info
            zone_id, zone_name = self.cloudflare.get_zone_id(domain)
            if not zone_id:
                raise Exception(f"No Cloudflare zone found for {domain}")
            
            # Prepare DNS record
            record_name = f'_acme-challenge.{domain}'
            dns_record = {
                'name': record_name,
                'type': 'TXT',
                'content': token,
                'ttl': 120
            }
            
            # Create DNS record
            record_id = self.cloudflare.create_dns_record(zone_id, dns_record)
            if not record_id:
                raise Exception(f"Failed to create DNS record for {domain}")
            
            logger.info(f"Created DNS record for {domain}", extra={'domain': domain})
        except Exception as e:
            logger.error(f"Failed to create DNS record for {domain}", 
                        extra={'domain': domain, 'error': str(e), 'error_type': type(e).__name__})
            raise

    def cleanup_cloudflare_dns(self, domain: str) -> None:
        """Clean up DNS validation records."""
        try:
            logger.debug(f"Cleaning up Cloudflare DNS for domain", 
                        extra={'domain': domain, 'action': 'cleanup_dns_start'})
            
            # Get zone info
            zone_id, zone_name = self.cloudflare.get_zone_id(domain)
            if not zone_id:
                logger.error(f"No zone found for cleanup", 
                            extra={'domain': domain, 'zone_name': zone_name})
                return
                
            record_name = f'_acme-challenge.{domain}'
            
            # Get records to delete
            params = {'name': record_name, 'type': 'TXT'}
            records = self.cloudflare.get_dns_records(zone_id, params)
            
            if not records:
                logger.debug(f"No DNS records found to clean up", 
                            extra={'domain': domain, 'record_name': record_name})
                return
                
            logger.debug(f"Found {len(records)} DNS records to clean up", 
                        extra={'domain': domain, 'record_count': len(records)})
            
            # Delete records
            deleted_count = 0
            for record in records:
                if self.cloudflare.delete_dns_record(zone_id, record['id']):
                    deleted_count += 1
            
            logger.info(f"Cleaned up DNS records for {domain}", 
                       extra={'domain': domain, 'records_removed': deleted_count})
        except Exception as e:
            logger.error(f"Failed to cleanup DNS records for {domain}", 
                        extra={'domain': domain, 'error': str(e), 'error_type': type(e).__name__})

    def obtain_certificate(self, domains: List[str]) -> None:
        """Obtain a new certificate for the specified domains."""
        try:
            primary_domain = domains[0]
            logger.debug(f"Starting certificate acquisition for domain group", 
                        extra={'domains': domains, 'primary_domain': primary_domain, 'action': 'obtain_cert_start'})
            
            cmd = [
                'certbot', 'certonly',
                '--dns-cloudflare',
                '--dns-cloudflare-credentials', '/root/.secrets/cloudflare.ini',
                '--email', self.email,
                '--agree-tos',
                '--non-interactive'
            ]

            if self.staging:
                cmd.append('--staging')
                logger.debug(f"Using staging environment for certificate", 
                           extra={'domains': domains, 'staging': True})

            # Check if any of the domains are wildcards
            has_wildcard = any('*' in domain for domain in domains)
            if has_wildcard:
                # For wildcard certificates, we need the ACME v2 endpoint
                cmd.extend(['--server', 'https://acme-v02.api.letsencrypt.org/directory'])
                cmd.extend(['--dns-cloudflare-propagation-seconds', '60'])
                logger.debug(f"Using wildcard certificate configuration", 
                           extra={'domains': domains, 'wildcard': True, 'propagation_wait': 60})
            
            # Add all domains to the certificate
            for domain in domains:
                cmd.extend(['-d', domain])
            
            logger.debug(f"Executing certbot command", 
                        extra={'domains': domains, 'command': ' '.join(cmd)})

            logger.info(f"Attempting to obtain certificate for domains: {', '.join(domains)}", 
                       extra={'domains': domains})
            
            # Execute certbot command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.debug(f"Certbot output for successful certificate acquisition", 
                           extra={'domains': domains, 'stdout': result.stdout})
                logger.info(f"Successfully obtained certificate for domains: {', '.join(domains)}", 
                           extra={'domains': domains})
            else:
                logger.debug(f"Certbot error output for failed certificate acquisition", 
                           extra={
                               'domains': domains, 
                               'stdout': result.stdout, 
                               'stderr': result.stderr, 
                               'returncode': result.returncode
                           })
                logger.error(f"Failed to obtain certificate for domains: {', '.join(domains)}", 
                           extra={'domains': domains, 'error': result.stderr})
                raise Exception(f"Certificate acquisition failed: {result.stderr}")

        except Exception as e:
            logger.error(f"Error obtaining certificate for domains: {', '.join(domains)}", 
                        extra={'domains': domains, 'error': str(e), 'error_type': type(e).__name__})
            raise

    def check_certificate_for_domains(self, domains: List[str]) -> None:
        """Check and renew certificate for a group of related domains."""
        try:
            primary_domain = domains[0]
            logger.debug(f"Checking certificate for domain group", 
                      extra={'domains': domains, 'primary_domain': primary_domain, 'action': 'check_group_start'})
            
            # Use the primary domain to check the certificate
            cmd = ['certbot', 'certificates', '--domain', primary_domain]
            logger.debug(f"Executing certbot check command", 
                       extra={'domains': domains, 'primary_domain': primary_domain, 'command': ' '.join(cmd)})
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.debug(f"Certbot check output", 
                           extra={'domains': domains, 'primary_domain': primary_domain, 'stdout': result.stdout})
                
                # Check if certificate exists
                if 'No certificates found.' in result.stdout:
                    logger.info(f"No certificate found for domains: {', '.join(domains)}, obtaining new one", 
                              extra={'domains': domains, 'primary_domain': primary_domain, 'action': 'obtain_new'})
                    self.obtain_certificate(domains)
                    return
                
                # Extract the domains in the certificate
                cert_domains = []
                if 'Domains:' in result.stdout:
                    domains_section = result.stdout.split('Domains:')[1].split('\n')[0].strip()
                    cert_domains = [d.strip() for d in domains_section.split() if d.strip()]
                    logger.debug(f"Found domains in certificate", 
                               extra={'domains': domains, 'cert_domains': cert_domains})
                
                # Check if all required domains are in the certificate
                missing_domains = [d for d in domains if d not in cert_domains]
                if missing_domains:
                    logger.info(f"Certificate missing domains: {', '.join(missing_domains)}, obtaining new certificate", 
                              extra={'domains': domains, 'missing_domains': missing_domains, 'action': 'obtain_new'})
                    self.obtain_certificate(domains)
                    return
                
                # Parse the output and check for expiration date
                if 'VALID: ' in result.stdout:
                    expiration_part = result.stdout.split('VALID: ')[1].split('\n')[0]
                    logger.debug(f"Found expiration date in certbot output", 
                               extra={'domains': domains, 'primary_domain': primary_domain, 'expiration_str': expiration_part})
                    
                    try:
                        # Try to handle different date formats
                        if "days)" in expiration_part:
                            # Format like "89 days)" - extract the number of days
                            days_str = expiration_part.split(' ')[0]
                            days_to_expiry = int(days_str)
                            logger.debug(f"Parsed days to expiry from certbot output", 
                                       extra={'domains': domains, 'primary_domain': primary_domain, 'days_to_expiry': days_to_expiry})
                        else:
                            # Original format assumed to be YYYY-MM-DD
                            expiration_date = datetime.strptime(expiration_part, '%Y-%m-%d')
                            days_to_expiry = (expiration_date - datetime.now()).days
                            logger.debug(f"Parsed expiration date from certbot output", 
                                       extra={
                                           'domains': domains, 
                                           'primary_domain': primary_domain,
                                           'expires_on': expiration_date.isoformat(), 
                                           'days_to_expiry': days_to_expiry
                                       })
                        
                        logger.debug(f"Certificate expiration analysis", 
                                   extra={
                                       'domains': domains, 
                                       'primary_domain': primary_domain,
                                       'expiration_str': expiration_part,
                                       'days_to_expiry': days_to_expiry,
                                       'renewal_threshold': self.renewal_interval
                                   })
                        
                        if days_to_expiry <= self.renewal_interval:
                            logger.info(f"Certificate for domains: {', '.join(domains)} needs renewal", 
                                      extra={
                                          'domains': domains, 
                                          'primary_domain': primary_domain,
                                          'days_to_expiry': days_to_expiry,
                                          'action': 'renewal_needed' 
                                      })
                            self.obtain_certificate(domains)
                        else:
                            logger.info(f"Certificate for domains: {', '.join(domains)} is valid and not due for renewal", 
                                      extra={
                                          'domains': domains, 
                                          'primary_domain': primary_domain,
                                          'days_to_expiry': days_to_expiry
                                      })
                    except ValueError as e:
                        logger.error(f"Failed to parse expiration date for domains: {', '.join(domains)}", 
                                    extra={
                                        'domains': domains, 
                                        'primary_domain': primary_domain,
                                        'expiration_str': expiration_part,
                                        'error': str(e)
                                    })
                        # Since we couldn't parse the date, let's take a cautious approach
                        logger.info(f"Unable to determine certificate expiration for domains: {', '.join(domains)}, assuming renewal needed", 
                                  extra={'domains': domains, 'primary_domain': primary_domain, 'action': 'renewal_assumed_needed'})
                        self.obtain_certificate(domains)
                else:
                    logger.warning(f"Could not find expiration date in certbot output for domains: {', '.join(domains)}", 
                                 extra={'domains': domains, 'primary_domain': primary_domain, 'stdout': result.stdout})
                    # No valid certificate found, obtain a new one
                    logger.info(f"No valid certificate found for domains: {', '.join(domains)}, obtaining new one", 
                              extra={'domains': domains, 'primary_domain': primary_domain, 'action': 'obtain_new'})
                    self.obtain_certificate(domains)
            else:
                logger.warning(f"No certificate found for domains: {', '.join(domains)}, obtaining new one", 
                             extra={'domains': domains, 'primary_domain': primary_domain, 'stderr': result.stderr, 'action': 'obtain_new'})
                self.obtain_certificate(domains)

        except Exception as e:
            logger.error(f"Error checking certificate for domains: {', '.join(domains)}", 
                       extra={'domains': domains, 'primary_domain': primary_domain, 'error': str(e), 'error_type': type(e).__name__})

    def check_and_renew_all_certificates(self) -> None:
        """Check and renew certificates for all domain groups."""
        logger.debug("Starting certificate check for all domain groups", 
                    extra={'domain_groups': self.domain_groups, 'action': 'check_all_start'})
        
        for domain_group in self.domain_groups:
            self.check_certificate_for_domains(domain_group) 