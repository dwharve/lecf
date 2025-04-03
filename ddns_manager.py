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
        domains_str = get_env('DDNS_DOMAINS', '')
        logger.debug("Parsing DDNS domains from environment", extra={'raw_domains': domains_str})
        self.domains = self._parse_domains(domains_str)
        
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
            'record_types': self.record_types,
            'domain_count': len(self.domains)
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
            
        # Split into zone groups first for debugging
        zone_groups = domains_str.split(';')
        logger.debug(f"Found {len(zone_groups)} zone groups in DDNS configuration", 
                   extra={'zone_groups': zone_groups})
        
        for i, group in enumerate(zone_groups):
            logger.debug(f"Processing zone group {i+1}/{len(zone_groups)}", 
                       extra={'group': group, 'group_index': i})
            
            if not group.strip():
                logger.debug(f"Skipping empty zone group", extra={'group_index': i})
                continue
                
            if ':' not in group:
                logger.warning(f"Invalid zone group format (missing ':' separator)", 
                             extra={'group': group, 'group_index': i})
                continue
                
            parts = group.split(':')
            if len(parts) != 2:
                logger.warning(f"Invalid zone group format (expected 1 ':' separator)", 
                             extra={'group': group, 'group_index': i, 'parts_count': len(parts)})
                continue
                
            zone_name = parts[0].strip()
            raw_subdomains = parts[1]
            subdomains = [s.strip() for s in raw_subdomains.split(',') if s.strip()]
            
            logger.debug(f"Parsed zone configuration", 
                       extra={
                           'zone_name': zone_name, 
                           'subdomains': subdomains,
                           'raw_subdomains': raw_subdomains,
                           'subdomain_count': len(subdomains)
                       })
            
            if zone_name and subdomains:
                domain_map[zone_name] = subdomains
                logger.debug(f"Added zone to domain map", 
                           extra={'zone_name': zone_name, 'subdomains': subdomains})
            else:
                logger.warning(f"Skipping invalid zone configuration", 
                             extra={'zone_name': zone_name, 'subdomains': subdomains})
                
        # Log final result
        logger.debug(f"Domain mapping complete", 
                   extra={'domain_count': len(domain_map), 'domain_map': domain_map})
                
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
                'record_type': record_type,
                'subdomain': subdomain
            })
            
            # Find existing record
            params = {
                'name': record_name,
                'type': record_type
            }
            
            logger.debug(f"Searching for existing DNS record", extra={
                'zone_id': zone_id,
                'params': params
            })
            
            records = self.cloudflare.get_dns_records(zone_id, params)
            logger.debug(f"Found {len(records) if records else 0} existing records", 
                       extra={'record_count': len(records) if records else 0})
            
            if records:
                # Update existing record
                record_id = records[0]['id']
                current_ip = records[0]['content']
                
                logger.debug(f"Existing record details", extra={
                    'record_id': record_id,
                    'current_ip': current_ip,
                    'new_ip': ip,
                    'record_name': record_name
                })
                
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
                
                logger.debug(f"Updating existing DNS record", extra={
                    'record_id': record_id,
                    'record': record
                })
                
                success = self.cloudflare.update_dns_record(zone_id, record_id, record)
                if success:
                    logger.info(f"Updated {record_type} record for {record_name} to {ip}")
                    return True
                
                logger.error(f"Failed to update DNS record", extra={
                    'record_name': record_name,
                    'record_id': record_id
                })
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
                
                logger.debug(f"Creating new DNS record", extra={
                    'zone_id': zone_id,
                    'record': record
                })
                
                record_id = self.cloudflare.create_dns_record(zone_id, record)
                if record_id:
                    logger.info(f"Created new {record_type} record for {record_name} with IP {ip}")
                    return True
                
                logger.error(f"Failed to create DNS record", extra={
                    'record_name': record_name
                })
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
        
        logger.info(f"Updating all domains to IP {ip}", extra={'domain_count': len(self.domains)})
        
        update_count = 0
        error_count = 0
        
        # Log all domains that will be processed
        logger.debug(f"Domains to be processed", extra={
            'domains': list(self.domains.keys()),
            'domain_count': len(self.domains)
        })
        
        # Process each zone
        zone_index = 0
        for zone_name, subdomains in self.domains.items():
            zone_index += 1
            try:
                logger.debug(f"Processing zone {zone_index}/{len(self.domains)}", 
                           extra={'zone_name': zone_name, 'subdomains': subdomains})
                
                # Get zone ID
                zone_id, actual_zone_name = self.cloudflare.get_zone_id(zone_name)
                if not zone_id:
                    logger.error(f"No zone found for domain", extra={'zone_name': zone_name})
                    error_count += 1
                    continue
                
                logger.debug(f"Found zone ID for {zone_name}", 
                           extra={'zone_id': zone_id, 'actual_zone_name': actual_zone_name})
                
                # Log all subdomains for this zone
                logger.debug(f"Subdomains to process for zone {zone_name}", 
                           extra={'subdomains': subdomains, 'subdomain_count': len(subdomains)})
                
                # Update each subdomain
                for subdomain_index, subdomain in enumerate(subdomains):
                    logger.debug(f"Processing subdomain {subdomain_index+1}/{len(subdomains)}", 
                               extra={'zone_name': zone_name, 'subdomain': subdomain})
                    
                    for record_type in self.record_types:
                        logger.debug(f"Processing record type {record_type}", 
                                   extra={'zone_name': zone_name, 'subdomain': subdomain, 'record_type': record_type})
                        
                        success = self.update_dns_record(
                            zone_id, zone_name, subdomain, record_type, ip
                        )
                        
                        if success:
                            update_count += 1
                            logger.debug(f"Successfully updated record", 
                                       extra={'zone_name': zone_name, 'subdomain': subdomain, 'record_type': record_type})
                        else:
                            error_count += 1
                            logger.debug(f"Failed to update record", 
                                       extra={'zone_name': zone_name, 'subdomain': subdomain, 'record_type': record_type})
                            
            except Exception as e:
                logger.error(f"Error processing zone", 
                           extra={'zone_name': zone_name, 'error': str(e), 'error_type': type(e).__name__})
                error_count += 1
                
        logger.info(f"DDNS update completed", 
                  extra={'updated': update_count, 'errors': error_count, 'zone_count': len(self.domains)}) 