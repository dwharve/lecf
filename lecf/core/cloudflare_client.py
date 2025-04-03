"""Cloudflare API client for interacting with Cloudflare services."""

from typing import Any, Dict, List, Optional, Tuple

import cloudflare

from lecf.utils import config, logger


class CloudflareClient:
    """Shared Cloudflare API client for both certificate and DDNS management."""

    def __init__(self, api_token: str = None):
        """
        Initialize the Cloudflare client.

        Args:
            api_token: Cloudflare API token. If None, fetched from config.
        """
        cf_config = config.get_cloudflare_config(config.APP_CONFIG)
        self.cf = cloudflare.Client(api_token=api_token or cf_config["api_token"])
        
        # Determine the API client capabilities by checking available methods
        self._check_client_capabilities()
        
        logger.debug("CloudflareClient initialized")
    
    def _check_client_capabilities(self):
        """Check the capabilities of the Cloudflare API client to determine which methods to use."""
        self.has_zones_list = hasattr(self.cf.zones, 'list')
        logger.debug(f"Cloudflare client capabilities checked", extra={"has_zones_list": self.has_zones_list})

    def get_zone_id(self, domain: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get zone ID for a domain.

        Args:
            domain: The domain to get the zone for

        Returns:
            Tuple of (zone_id, zone_name) or (None, None) if not found
        """
        # Extract root domain (zone name)
        parts = domain.split(".")
        if len(parts) >= 2:
            zone_name = f"{parts[-2]}.{parts[-1]}"
        else:
            logger.error(f"Invalid domain format", extra={"domain": domain})
            return None, None

        logger.debug(
            f"Looking up zone for domain",
            extra={"domain": domain, "zone_name": zone_name, "domain_parts": parts},
        )

        try:
            # Get zone ID
            logger.debug(
                f"Sending Cloudflare API request for zones",
                extra={"domain": domain, "zone_name": zone_name},
            )

            # Try multiple methods to get the zones
            zones = []
            methods_tried = []
            
            # Method 1: Try using zones.list() if available
            if self.has_zones_list:
                try:
                    methods_tried.append("zones.list()")
                    zones = self.cf.zones.list()
                    logger.debug(f"Successfully retrieved zones using zones.list()")
                except Exception as e1:
                    logger.debug(f"Failed to get zones using list method", 
                                 extra={"error": str(e1), "error_type": type(e1).__name__})
            
            # Method 2: Try direct call to zones() as a callable
            if not zones:
                try:
                    methods_tried.append("zones()")
                    zones = self.cf.zones()
                    logger.debug(f"Successfully retrieved zones using zones()")
                except Exception as e2:
                    logger.debug(f"Failed to get zones using direct call", 
                                 extra={"error": str(e2), "error_type": type(e2).__name__})
            
            # Method 3: Try client.list_zones()
            if not zones:
                try:
                    methods_tried.append("client.list_zones()")
                    # Some versions of the client have a list_zones method
                    if hasattr(self.cf, 'list_zones'):
                        zones = self.cf.list_zones()
                        logger.debug(f"Successfully retrieved zones using client.list_zones()")
                except Exception as e3:
                    logger.debug(f"Failed to get zones using list_zones method", 
                                 extra={"error": str(e3), "error_type": type(e3).__name__})
                    
            logger.debug(f"Attempted zone retrieval methods", extra={"methods_tried": methods_tried})
            
            if not zones:
                logger.error(f"Could not retrieve zones with any method", 
                             extra={"methods_tried": methods_tried})
                return None, None
            
            # Log the type of what we're dealing with to understand the structure
            if zones and len(zones) > 0:
                first_zone_type = type(zones[0]).__name__
                logger.debug(f"First zone is of type", extra={"zone_type": first_zone_type})
                
                # Try to access a name property or attribute to understand the structure
                try:
                    sample_props = {}
                    first_zone = zones[0]
                    # Try various ways to get properties
                    if hasattr(first_zone, 'name'):
                        sample_props['name'] = first_zone.name
                    if hasattr(first_zone, 'id'):
                        sample_props['id'] = first_zone.id
                    # Try dictionary-like access too
                    try:
                        if 'name' in first_zone:
                            sample_props['dict_name'] = first_zone['name']
                    except:
                        pass
                    
                    logger.debug(f"Sample zone properties", extra={"properties": sample_props})
                except Exception as e:
                    logger.debug(f"Error inspecting zone properties", extra={"error": str(e)})
            
            # Filter zones by name in Python - try different access methods since we're not sure of the object structure
            matching_zones = []
            for zone in zones:
                try:
                    # Try as attribute first
                    if hasattr(zone, 'name') and getattr(zone, 'name') == zone_name:
                        matching_zones.append(zone)
                        continue
                        
                    # Try as dictionary key
                    try:
                        if zone['name'] == zone_name:
                            matching_zones.append(zone)
                            continue
                    except:
                        pass
                        
                    # Try with get() method if available
                    try:
                        if hasattr(zone, 'get') and zone.get('name') == zone_name:
                            matching_zones.append(zone)
                            continue
                    except:
                        pass
                except Exception as e:
                    logger.debug(f"Error matching zone", extra={"error": str(e), "zone": str(zone)})

            logger.debug(
                f"Filtered zones by name",
                extra={
                    "domain": domain,
                    "zone_name": zone_name,
                    "all_zones_count": len(zones),
                    "matching_zones_count": len(matching_zones),
                },
            )

            if not matching_zones:
                logger.error(
                    f"No zone found for domain",
                    extra={"domain": domain, "zone_name": zone_name, "reason": "not_in_results"},
                )
                return None, None

            zone = matching_zones[0]
            
            # Try to extract zone_id and actual_zone_name
            zone_id = None
            actual_zone_name = None
            
            # Try as attribute
            if hasattr(zone, 'id'):
                zone_id = zone.id
            if hasattr(zone, 'name'):
                actual_zone_name = zone.name
                
            # Try as dictionary
            if zone_id is None:
                try:
                    zone_id = zone['id']
                except:
                    pass
            if actual_zone_name is None:
                try:
                    actual_zone_name = zone['name']
                except:
                    pass
            
            # Fallback
            if actual_zone_name is None:
                actual_zone_name = zone_name
                
            if zone_id is None:
                logger.error(
                    f"Failed to extract zone ID from zone object",
                    extra={"domain": domain, "zone_name": zone_name},
                )
                return None, None

            logger.debug(
                f"Found zone for domain",
                extra={
                    "domain": domain,
                    "zone_name": zone_name,
                    "actual_zone_name": actual_zone_name,
                    "zone_id": zone_id,
                },
            )

            return zone_id, actual_zone_name
        except Exception as e:
            logger.error(
                f"Cloudflare API error when getting zone ID",
                extra={
                    "domain": domain,
                    "zone_name": zone_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return None, None

    def get_dns_records(self, zone_id: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Get DNS records for a zone that match the specified parameters.

        Args:
            zone_id: Cloudflare zone ID
            params: Optional filtering parameters (name, type, etc.)

        Returns:
            List of DNS records or empty list if none found or on error
        """
        try:
            logger.debug(
                f"Getting DNS records",
                extra={"zone_id": zone_id, "params": params},
            )

            # Try to get DNS records with the zone_id
            records = []
            methods_tried = []

            # Method 1: Try directly with zone_id
            try:
                methods_tried.append("dns_records.get(zone_id)")
                records = self.cf.zones.dns_records.get(zone_id)
                logger.debug(f"Successfully retrieved DNS records using dns_records.get(zone_id)")
            except Exception as e1:
                logger.debug(f"Failed to get DNS records using direct method", 
                            extra={"error": str(e1), "error_type": type(e1).__name__})
            
            if not records:
                logger.error(f"Could not retrieve DNS records with any method", 
                            extra={"methods_tried": methods_tried, "zone_id": zone_id})
                return []

            # If params are specified, filter the records in Python
            if params:
                filtered_records = []
                for record in records:
                    try:
                        match = True
                        for key, value in params.items():
                            # Try multiple ways to get the property value
                            record_value = None
                            
                            # Try attribute access
                            if hasattr(record, key):
                                record_value = getattr(record, key)
                            
                            # Try dictionary access
                            if record_value is None:
                                try:
                                    record_value = record[key]
                                except:
                                    pass
                            
                            # Try get() method
                            if record_value is None and hasattr(record, 'get'):
                                try:
                                    record_value = record.get(key)
                                except:
                                    pass
                            
                            if record_value != value:
                                match = False
                                break
                                
                        if match:
                            filtered_records.append(record)
                    except Exception as e:
                        logger.debug(f"Error matching record", 
                                    extra={"error": str(e), "record": str(record)})
                        
                records = filtered_records

                logger.debug(
                    f"Filtered DNS records by parameters",
                    extra={
                        "zone_id": zone_id, 
                        "params": params,
                        "original_count": len(records) if records else 0,
                        "filtered_count": len(filtered_records),
                    },
                )

            # Convert records to dictionaries if they're objects
            normalized_records = []
            for record in records:
                try:
                    if not isinstance(record, dict):
                        # Try to convert to dict
                        record_dict = {}
                        
                        # Common DNS record attributes
                        attrs = ['id', 'type', 'name', 'content', 'proxied', 'ttl', 'priority']
                        
                        for attr in attrs:
                            # Try as attribute
                            if hasattr(record, attr):
                                record_dict[attr] = getattr(record, attr)
                            # Try as dict key
                            else:
                                try:
                                    record_dict[attr] = record[attr]
                                except:
                                    pass
                        
                        normalized_records.append(record_dict)
                    else:
                        normalized_records.append(record)
                except Exception as e:
                    logger.debug(f"Error normalizing record", 
                                extra={"error": str(e), "record": str(record)})
                    # Include as-is in case of error
                    normalized_records.append(record)

            logger.debug(
                f"Retrieved DNS records",
                extra={"zone_id": zone_id, "count": len(normalized_records)},
            )

            return normalized_records
        except Exception as e:
            logger.error(
                f"Cloudflare API error when getting DNS records",
                extra={
                    "zone_id": zone_id,
                    "params": params,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return []

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
            record_name = record_data.get("name", "unknown")
            record_type = record_data.get("type", "unknown")

            logger.debug(
                f"Creating DNS record",
                extra={
                    "zone_id": zone_id,
                    "record_data": record_data,
                    "record_name": record_name,
                    "record_type": record_type,
                },
            )

            # Try multiple approaches to create the DNS record
            methods_tried = []
            result = None

            # Method 1: Try with **record_data
            try:
                methods_tried.append("dns_records.post(zone_id, **record_data)")
                result = self.cf.zones.dns_records.post(zone_id, **record_data)
                logger.debug(f"Successfully created DNS record using dns_records.post(zone_id, **record_data)")
            except Exception as e1:
                logger.debug(f"Failed to create DNS record using **record_data method", 
                            extra={"error": str(e1), "error_type": type(e1).__name__})
                
                # Method 2: Try with data=record_data
                try:
                    methods_tried.append("dns_records.post(zone_id, data=record_data)")
                    result = self.cf.zones.dns_records.post(zone_id, data=record_data)
                    logger.debug(f"Successfully created DNS record using dns_records.post(zone_id, data=record_data)")
                except Exception as e2:
                    logger.debug(f"Failed to create DNS record using data=record_data method", 
                                extra={"error": str(e2), "error_type": type(e2).__name__})

            if not result:
                logger.error(f"Could not create DNS record with any method", 
                            extra={"methods_tried": methods_tried, "zone_id": zone_id})
                return None

            # Extract the record ID from the result which may be an object or dict
            record_id = None
            
            # Try as attribute
            if hasattr(result, 'id'):
                record_id = result.id
            
            # Try as dictionary
            if record_id is None:
                try:
                    record_id = result["id"]
                except:
                    pass
            
            if record_id is None:
                logger.error(
                    f"Failed to extract record ID from result",
                    extra={"zone_id": zone_id, "result_type": type(result).__name__},
                )
                return None

            logger.debug(
                f"Created DNS record successfully",
                extra={
                    "zone_id": zone_id,
                    "record_id": record_id,
                    "record_name": record_name,
                    "record_type": record_type,
                },
            )

            return record_id
        except Exception as e:
            logger.error(
                f"Cloudflare API error when creating DNS record",
                extra={
                    "zone_id": zone_id,
                    "record_data": record_data,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
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
            record_name = record_data.get("name", "unknown")
            record_type = record_data.get("type", "unknown")
            record_content = record_data.get("content", "unknown")

            logger.debug(
                f"Updating DNS record",
                extra={
                    "zone_id": zone_id,
                    "record_id": record_id,
                    "record_name": record_name,
                    "record_type": record_type,
                    "record_content": record_content,
                },
            )

            # Try multiple approaches to update the DNS record
            methods_tried = []
            result = None

            # Method 1: Try with **record_data
            try:
                methods_tried.append("dns_records.put(zone_id, record_id, **record_data)")
                result = self.cf.zones.dns_records.put(zone_id, record_id, **record_data)
                logger.debug(f"Successfully updated DNS record using dns_records.put(zone_id, record_id, **record_data)")
            except Exception as e1:
                logger.debug(f"Failed to update DNS record using **record_data method", 
                            extra={"error": str(e1), "error_type": type(e1).__name__})
                
                # Method 2: Try with data=record_data
                try:
                    methods_tried.append("dns_records.put(zone_id, record_id, data=record_data)")
                    result = self.cf.zones.dns_records.put(zone_id, record_id, data=record_data)
                    logger.debug(f"Successfully updated DNS record using dns_records.put(zone_id, record_id, data=record_data)")
                except Exception as e2:
                    logger.debug(f"Failed to update DNS record using data=record_data method", 
                                extra={"error": str(e2), "error_type": type(e2).__name__})

            if not result:
                logger.error(f"Could not update DNS record with any method", 
                            extra={"methods_tried": methods_tried, "zone_id": zone_id, "record_id": record_id})
                return False

            logger.debug(
                f"Updated DNS record successfully",
                extra={
                    "zone_id": zone_id,
                    "record_id": record_id,
                    "record_name": record_name,
                },
            )

            return True
        except Exception as e:
            logger.error(
                f"Cloudflare API error when updating DNS record",
                extra={
                    "zone_id": zone_id,
                    "record_id": record_id,
                    "record_data": record_data,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
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
            logger.debug(
                f"Deleting DNS record",
                extra={"zone_id": zone_id, "record_id": record_id},
            )

            # Simply call delete method - should be consistent across versions
            result = self.cf.zones.dns_records.delete(zone_id, record_id)

            logger.debug(
                f"Deleted DNS record successfully",
                extra={"zone_id": zone_id, "record_id": record_id},
            )

            return True
        except Exception as e:
            logger.error(
                f"Cloudflare API error when deleting DNS record",
                extra={
                    "zone_id": zone_id,
                    "record_id": record_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return False
