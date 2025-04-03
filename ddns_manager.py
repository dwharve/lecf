import time
import requests
from datetime import datetime
from typing import Dict, List, Optional

# Import shared modules
from utils import logger, get_env, get_env_int, get_env_list
from cloudflare_client import CloudflareClient
from base_manager import BaseManager

class DdnsManager(BaseManager):
    def __init__(self):
        # Initialize base class
        super().__init__("DDNS")
        
        # Initialize manager-specific attributes
        self.cloudflare = CloudflareClient()
        
        # Parse domains to manage from environment variable
        self.domains = self._parse_domains(get_env('DDNS_DOMAINS', ''))
        
        # External IP check service URLs (we'll try them in order)
        self.ip_check_services = [
            'https://api.ipify.org',
            'https://ifconfig.me/ip',
            'https://icanhazip.com',
            'https://checkip.amazonaws.com'
        ]
        
        # Cache for current IP to avoid unnecessary updates
        self.current_ip = None
        self.last_check_time = None
        
        # Record types to update
        self.record_types = get_env_list('DDNS_RECORD_TYPES', default=['A'])
        
        # Log initialization
        logger.debug("DdnsManager initialized", extra={
            'domains': self.domains,
            'check_interval': self.check_interval,
            'record_types': self.record_types
        })
    
    def _setup_interval(self) -> None:
        """Set up the check interval for DDNS updates."""
        self.check_interval = get_env_int('DDNS_CHECK_INTERVAL_MINUTES', 15)
        self.interval_unit = "minutes"
    
    def _execute_cycle(self) -> None:
        """Execute a single DDNS update cycle."""
        self.update_all_domains()

    def _parse_domains(self, domains_str: str) -> Dict[str, List[str]]:
        """
        Parse domains string into a dict mapping zone names to records.
        Format: example.com:www,@,subdomain;another.com:@,sub1,sub2
        
        Returns a dict like:
        {
            'example.com': ['www', '@', 'subdomain'],
            'another.com': ['@', 'sub1', 'sub2']
        }
        """
        domain_map = {}
        
        if not domains_str:
            logger.warning("No DDNS domains specified. Please set DDNS_DOMAINS environment variable.")
            return domain_map
            
        zone_groups = domains_str.split(';')
        
        for group in zone_groups:
            if not group.strip() or ':' not in group:
                continue
                
            parts = group.split(':')
            if len(parts) != 2:
                continue
                
            zone_name = parts[0].strip()
            subdomains = [s.strip() for s in parts[1].split(',') if s.strip()]
            
            if zone_name and subdomains:
                domain_map[zone_name] = subdomains
                
        return domain_map

    def get_public_ip(self) -> Optional[str]:
        """Get the current public IP address using various services."""
        for service_url in self.ip_check_services:
            try:
                logger.debug(f"Checking public IP using service", extra={'service': service_url})
                response = requests.get(service_url, timeout=10)
                
                if response.status_code == 200:
                    ip = response.text.strip()
                    logger.debug(f"Public IP found", extra={'ip': ip})
                    return ip
            except Exception as e:
                logger.debug(f"Failed to get IP from service", 
                           extra={'service': service_url, 'error': str(e)})
                continue
                
        logger.error("Failed to get public IP from all services")
        return None

    def update_dns_record(self, zone_id: str, zone_name: str, subdomain: str, record_type: str, ip: str) -> bool:
        """Update a specific DNS record with the new IP."""
        try:
            # Handle root domain (@) special case
            record_name = zone_name if subdomain == '@' else f"{subdomain}.{zone_name}"
            
            logger.debug(f"Updating DNS record", extra={
                'zone_name': zone_name,
                'record_name': record_name,
                'record_type': record_type
            })
            
            # Find existing record
            params = {
                'name': record_name,
                'type': record_type
            }
            
            records = self.cloudflare.get_dns_records(zone_id, params)
            
            if records:
                # Update existing record
                record_id = records[0]['id']
                current_ip = records[0]['content']
                
                if current_ip == ip:
                    logger.debug(f"IP unchanged, skipping update", extra={
                        'record_name': record_name,
                        'ip': ip
                    })
                    return True
                
                record = {
                    'name': record_name,
                    'type': record_type,
                    'content': ip,
                    'ttl': 60,  # Short TTL for DDNS
                    'proxied': records[0].get('proxied', False)  # Maintain proxy status
                }
                
                success = self.cloudflare.update_dns_record(zone_id, record_id, record)
                if success:
                    logger.info(f"Updated {record_type} record for {record_name} to {ip}")
                    return True
                return False
                
            else:
                # Create new record
                record = {
                    'name': record_name,
                    'type': record_type,
                    'content': ip,
                    'ttl': 60,
                    'proxied': False
                }
                
                record_id = self.cloudflare.create_dns_record(zone_id, record)
                if record_id:
                    logger.info(f"Created new {record_type} record for {record_name} with IP {ip}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Failed to update DNS record", 
                       extra={'record_name': record_name, 'error': str(e), 'error_type': type(e).__name__})
            return False

    def update_all_domains(self) -> None:
        """Update all configured domains with the current IP."""
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
            
        self.current_ip = ip
        self.last_check_time = datetime.now()
        
        logger.info(f"Updating all domains to IP {ip}")
        
        update_count = 0
        error_count = 0
        
        # Process each zone
        for zone_name, subdomains in self.domains.items():
            try:
                # Get zone ID
                zone_id, _ = self.cloudflare.get_zone_id(zone_name)
                if not zone_id:
                    logger.error(f"No zone found for domain", extra={'zone_name': zone_name})
                    error_count += 1
                    continue
                
                # Update each subdomain
                for subdomain in subdomains:
                    for record_type in self.record_types:
                        success = self.update_dns_record(
                            zone_id, zone_name, subdomain, record_type, ip
                        )
                        
                        if success:
                            update_count += 1
                        else:
                            error_count += 1
                            
            except Exception as e:
                logger.error(f"Error processing zone", 
                           extra={'zone_name': zone_name, 'error': str(e)})
                error_count += 1
                
        logger.info(f"DDNS update completed", 
                  extra={'updated': update_count, 'errors': error_count}) 