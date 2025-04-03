import CloudFlare
from typing import Dict, List, Optional, Any, Tuple
from utils import logger, get_cloudflare_config

class CloudflareClient:
    """Shared Cloudflare API client for both certificate and DDNS management."""
    
    def __init__(self, api_token: str = None):
        """
        Initialize the Cloudflare client.
        
        Args:
            api_token: Cloudflare API token. If None, fetched from environment.
        """
        config = get_cloudflare_config() 
        self.cf = CloudFlare.CloudFlare(token=api_token or config['api_token'])
        logger.debug("CloudflareClient initialized")
    
    def get_zone_id(self, domain: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get zone ID for a domain.
        
        Args:
            domain: The domain to get the zone for
            
        Returns:
            Tuple of (zone_id, zone_name) or (None, None) if not found
        """
        # Extract root domain (zone name)
        parts = domain.split('.')
        if len(parts) >= 2:
            zone_name = f"{parts[-2]}.{parts[-1]}"
        else:
            logger.error(f"Invalid domain format", extra={'domain': domain})
            return None, None
        
        logger.debug(f"Looking up zone for domain", 
                   extra={'domain': domain, 'zone_name': zone_name, 'domain_parts': parts})
            
        try:
            # Get zone ID
            logger.debug(f"Sending Cloudflare API request for zone", 
                       extra={'domain': domain, 'zone_name': zone_name, 'action': 'zones.get'})
            
            zones = self.cf.zones.get(params={'name': zone_name})
            logger.debug(f"Received zone response from Cloudflare API", 
                       extra={'domain': domain, 'zone_name': zone_name, 'zones_found': len(zones) if zones else 0})
            
            if not zones:
                logger.error(f"No zone found for domain", 
                           extra={'domain': domain, 'zone_name': zone_name, 'reason': 'empty_response'})
                return None, None
                
            zone = zones[0]
            zone_id = zone['id']
            actual_zone_name = zone.get('name', zone_name)
            
            logger.debug(f"Found zone for domain", 
                        extra={
                            'domain': domain, 
                            'zone_name': zone_name, 
                            'actual_zone_name': actual_zone_name,
                            'zone_id': zone_id,
                            'zone_status': zone.get('status')
                        })
            
            return zone_id, actual_zone_name
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            logger.error(f"Cloudflare API error when getting zone ID", 
                       extra={
                           'domain': domain, 
                           'zone_name': zone_name, 
                           'error_code': e.code, 
                           'error': str(e),
                           'details': getattr(e, 'details', None)
                       })
            return None, None
        except Exception as e:
            logger.error(f"Failed to get zone ID for domain", 
                       extra={'domain': domain, 'error': str(e), 'error_type': type(e).__name__})
            return None, None
    
    def create_dns_record(self, zone_id: str, record_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a DNS record.
        
        Args:
            zone_id: Cloudflare zone ID
            record_data: Record data to create
            
        Returns:
            Record ID if successful, None otherwise
        """
        try:
            record_name = record_data.get('name', 'unknown')
            record_type = record_data.get('type', 'unknown')
            
            logger.debug(f"Creating DNS record", 
                       extra={
                           'zone_id': zone_id, 
                           'record_data': record_data,
                           'record_name': record_name,
                           'record_type': record_type,
                           'action': 'dns_records.post'
                       })
            
            result = self.cf.zones.dns_records.post(zone_id, data=record_data)
            record_id = result['id']
            
            logger.debug(f"Created DNS record successfully", 
                       extra={
                           'zone_id': zone_id, 
                           'record_id': record_id,
                           'record_name': record_name,
                           'record_type': record_type,
                           'api_response': result
                       })
            
            return record_id
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            logger.error(f"Cloudflare API error when creating DNS record", 
                       extra={
                           'zone_id': zone_id,
                           'record_data': record_data,
                           'error_code': e.code, 
                           'error': str(e),
                           'details': getattr(e, 'details', None)
                       })
            return None
        except Exception as e:
            logger.error(f"Failed to create DNS record", 
                       extra={'zone_id': zone_id, 'error': str(e), 'error_type': type(e).__name__})
            return None
    
    def update_dns_record(self, zone_id: str, record_id: str, record_data: Dict[str, Any]) -> bool:
        """
        Update a DNS record.
        
        Args:
            zone_id: Cloudflare zone ID
            record_id: DNS record ID
            record_data: Record data to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            record_name = record_data.get('name', 'unknown')
            record_type = record_data.get('type', 'unknown')
            record_content = record_data.get('content', 'unknown')
            
            logger.debug(f"Updating DNS record", 
                       extra={
                           'zone_id': zone_id, 
                           'record_id': record_id,
                           'record_name': record_name,
                           'record_type': record_type,
                           'record_content': record_content,
                           'action': 'dns_records.put'
                       })
            
            result = self.cf.zones.dns_records.put(zone_id, record_id, data=record_data)
            
            logger.debug(f"Updated DNS record successfully", 
                       extra={
                           'zone_id': zone_id, 
                           'record_id': record_id,
                           'record_name': record_name,
                           'api_response': result
                       })
            
            return True
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            logger.error(f"Cloudflare API error when updating DNS record", 
                       extra={
                           'zone_id': zone_id, 
                           'record_id': record_id, 
                           'record_data': record_data,
                           'error_code': e.code, 
                           'error': str(e),
                           'details': getattr(e, 'details', None)
                       })
            return False
        except Exception as e:
            logger.error(f"Failed to update DNS record", 
                       extra={'zone_id': zone_id, 'record_id': record_id, 'error': str(e), 'error_type': type(e).__name__})
            return False
    
    def delete_dns_record(self, zone_id: str, record_id: str) -> bool:
        """
        Delete a DNS record.
        
        Args:
            zone_id: Cloudflare zone ID
            record_id: DNS record ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug(f"Deleting DNS record", 
                       extra={'zone_id': zone_id, 'record_id': record_id, 'action': 'dns_records.delete'})
            
            self.cf.zones.dns_records.delete(zone_id, record_id)
            
            logger.debug(f"Deleted DNS record successfully", 
                       extra={'zone_id': zone_id, 'record_id': record_id})
            
            return True
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            logger.error(f"Cloudflare API error when deleting DNS record", 
                       extra={
                           'zone_id': zone_id, 
                           'record_id': record_id, 
                           'error_code': e.code, 
                           'error': str(e),
                           'details': getattr(e, 'details', None)
                       })
            return False
        except Exception as e:
            logger.error(f"Failed to delete DNS record", 
                       extra={'zone_id': zone_id, 'record_id': record_id, 'error': str(e), 'error_type': type(e).__name__})
            return False
    
    def get_dns_records(self, zone_id: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Get DNS records for a zone.
        
        Args:
            zone_id: Cloudflare zone ID
            params: Additional parameters for filtering
            
        Returns:
            List of DNS records
        """
        try:
            logger.debug(f"Getting DNS records", 
                       extra={'zone_id': zone_id, 'params': params, 'action': 'dns_records.get'})
            
            records = self.cf.zones.dns_records.get(zone_id, params=params or {})
            
            # Log detailed information about the records
            record_details = [
                {
                    'id': r.get('id', 'unknown'),
                    'name': r.get('name', 'unknown'),
                    'type': r.get('type', 'unknown'),
                    'content': r.get('content', 'unknown'),
                    'proxied': r.get('proxied', False)
                }
                for r in records[:5]  # Limit to first 5 to avoid excessive logging
            ]
            
            logger.debug(f"Found {len(records)} DNS records", 
                       extra={
                           'zone_id': zone_id, 
                           'record_count': len(records),
                           'record_details': record_details,
                           'has_more': len(records) > 5
                       })
            
            return records
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            logger.error(f"Cloudflare API error when getting DNS records", 
                       extra={
                           'zone_id': zone_id, 
                           'params': params,
                           'error_code': e.code, 
                           'error': str(e),
                           'details': getattr(e, 'details', None)
                       })
            return []
        except Exception as e:
            logger.error(f"Failed to get DNS records", 
                       extra={'zone_id': zone_id, 'error': str(e), 'error_type': type(e).__name__})
            return [] 