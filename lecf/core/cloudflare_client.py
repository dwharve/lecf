"""Cloudflare API client for interacting with Cloudflare services."""

from typing import Any, Dict, List, Optional, Tuple
import os

import cloudflare
from cloudflare import Client

from lecf.utils import config, logger


class CloudflareClient:
    """
    Shared Cloudflare API client for both certificate and DDNS management.
    
    This class uses the official Cloudflare Python SDK (cloudflare) to interact
    with the Cloudflare API. It provides methods for managing DNS records and
    zones using high-level SDK interfaces instead of direct API calls.
    
    Configuration:
        - The client can be initialized with an API token directly or will use
          the configured token from environment variables or config file.
        - Set CLOUDFLARE_USE_CREDENTIALS_FILE=true to create a credentials file
          at ~/.secrets/cloudflare.ini which will be used by the SDK.
    
    Usage:
        client = CloudflareClient()
        zone_id, zone_name = client.get_zone_id("example.com")
        records = client.get_dns_records(zone_id, {"type": "A"})
    """

    def __init__(self, api_token: str = None):
        """
        Initialize the Cloudflare client.

        Args:
            api_token: Cloudflare API token. If None, fetched from config.
        """
        cf_config = config.get_cloudflare_config(config.APP_CONFIG)
        
        # Check if we should create credentials file for the SDK
        use_cred_file = config.get_env_bool("CLOUDFLARE_USE_CREDENTIALS_FILE", False)
        cred_file_path = None
        
        if use_cred_file:
            # Create credentials file in ~/.secrets/cloudflare.ini
            home_dir = os.path.expanduser("~")
            secrets_dir = os.path.join(home_dir, ".secrets")
            cred_file_path = os.path.join(secrets_dir, "cloudflare.ini")
            
            # Create directory if it doesn't exist
            if not os.path.exists(secrets_dir):
                os.makedirs(secrets_dir, exist_ok=True)
                
            # Create/update credentials file
            with open(cred_file_path, "w") as f:
                f.write("[cloudflare]\n")
                f.write(f"token = {api_token or cf_config['api_token']}\n")
                
            logger.debug(f"Created Cloudflare credentials file at {cred_file_path}")
            
            # Create client with credentials file
            self.cf = Client()
        else:
            # Create client with direct token
            self.cf = Client(api_token=api_token or cf_config["api_token"])
        
        logger.debug("CloudflareClient initialized")

    def _direct_api_request(
        self, method: str, path: str, params: dict = None, data: dict = None
    ) -> Any:
        """
        Make a direct API request to Cloudflare.
        
        This method is maintained for backward compatibility but new code should
        use the SDK interfaces.

        Args:
            method: HTTP method (get, post, put, delete)
            path: API path
            params: Query parameters
            data: Request data

        Returns:
            API response
        """
        try:
            logger.debug(
                f"Making direct API request",
                extra={"method": method, "path": path, "params": params},
            )

            # Import requests if needed
            import requests

            # Get the authentication token
            cf_config = config.get_cloudflare_config(config.APP_CONFIG)
            token = cf_config["api_token"]

            # Set up headers with authentication
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Cloudflare API base URL
            base_url = "https://api.cloudflare.com/client/v4"

            # Make the request using the requests library directly
            url = f"{base_url}{path}"
            logger.debug(
                f"Making direct HTTP request to Cloudflare API",
                extra={"method": method, "url": url},
            )

            if method.lower() == "get":
                response = requests.get(url, headers=headers, params=params)
            elif method.lower() == "post":
                response = requests.post(url, headers=headers, params=params, json=data)
            elif method.lower() == "put":
                response = requests.put(url, headers=headers, params=params, json=data)
            elif method.lower() == "delete":
                response = requests.delete(url, headers=headers, params=params)
            else:
                logger.error(f"Unsupported HTTP method", extra={"method": method})
                return None

            # Check if request was successful
            if response.status_code >= 200 and response.status_code < 300:
                logger.debug(
                    f"Successful API response", extra={"status_code": response.status_code}
                )
                return response.json()

            # If we get here, request was not successful
            logger.error(
                f"API request failed",
                extra={"status_code": response.status_code, "response": response.text},
            )
            return None

        except Exception as e:
            logger.error(
                f"Direct API request failed",
                extra={
                    "method": method,
                    "path": path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return None

    def get_zone_id(self, domain: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get zone ID for a domain using the CloudflareSDK.
        
        Uses the zones.list method from the Cloudflare SDK to retrieve zone information
        based on the domain name. The domain is parsed to extract the root domain (zone name).

        Args:
            domain: The domain to get the zone for (can be a subdomain)

        Returns:
            Tuple of (zone_id, zone_name) or (None, None) if not found
            
        Example:
            zone_id, zone_name = client.get_zone_id("subdomain.example.com")
            # Returns the zone ID and name for "example.com"
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
            # Use SDK to get zones - note: list doesn't take params as a keyword
            # Instead, pass name directly as a parameter
            zones = self.cf.zones.list(name=zone_name)
            
            # SyncV4PagePaginationArray doesn't support len(), but we can iterate over it
            # Try to get the first item in the iterator
            found_zone = None
            for zone in zones:
                found_zone = zone
                break
                
            if found_zone:
                # Access Zone object properties using attribute notation instead of dictionary notation
                # According to Cloudflare Python SDK documentation
                zone_id = found_zone.id
                zone_name = found_zone.name
                logger.debug(
                    f"Found zone",
                    extra={
                        "zone_id": zone_id,
                        "zone_name": zone_name,
                    },
                )
                return zone_id, zone_name

            logger.error(
                f"No zone found for domain",
                extra={"domain": domain, "zone_name": zone_name},
            )
            return None, None

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
        Get DNS records for a zone using the Cloudflare SDK.
        
        Uses the dns.records.list method from the SDK to retrieve DNS records
        for a specified zone ID with optional filtering parameters.

        Args:
            zone_id: Cloudflare zone ID
            params: Optional filtering parameters, such as:
                   - type: Record type (A, AAAA, CNAME, etc.)
                   - name: Record name (e.g., "subdomain.example.com")
                   - content: Record content (e.g., IP address)
                   - per_page: Number of records per page
                   - page: Page number

        Returns:
            List of DNS records
            
        Example:
            records = client.get_dns_records(zone_id, {"type": "A", "name": "www.example.com"})
        """
        try:
            logger.debug(
                f"Getting DNS records",
                extra={"zone_id": zone_id, "params": params},
            )

            # According to the Cloudflare SDK documentation (https://raw.githubusercontent.com/cloudflare/cloudflare-python/refs/heads/main/api.md)
            # The method signature is client.dns.records.list(*, zone_id, **params)
            # This means zone_id should be a keyword argument, not a positional argument
            if params:
                records_iterator = self.cf.dns.records.list(zone_id=zone_id, **params)
            else:
                records_iterator = self.cf.dns.records.list(zone_id=zone_id)
                
            # Convert pagination iterator to a list
            records = list(records_iterator)
            
            logger.debug(
                f"Found DNS records",
                extra={"zone_id": zone_id, "count": len(records)},
            )
            return records

        except Exception as e:
            logger.error(
                f"Cloudflare API error when getting DNS records",
                extra={"zone_id": zone_id, "error": str(e), "error_type": type(e).__name__},
            )
            return []

    def create_dns_record(self, zone_id: str, record_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a DNS record using the Cloudflare SDK.
        
        Uses the dns.records.create method from the SDK to create a new DNS record
        in the specified zone.

        Args:
            zone_id: Cloudflare zone ID
            record_data: Record data to create, including:
                         - type: Record type (A, AAAA, CNAME, etc.)
                         - name: Record name (e.g., "subdomain.example.com")
                         - content: Record content (e.g., IP address)
                         - ttl: Time to live in seconds (1 for automatic)
                         - proxied: Whether the record is proxied (default: False)

        Returns:
            Record ID if successful, None otherwise
            
        Example:
            record_data = {
                "type": "A",
                "name": "www.example.com",
                "content": "192.0.2.1",
                "ttl": 1,
                "proxied": False
            }
            record_id = client.create_dns_record(zone_id, record_data)
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

            # According to the Cloudflare SDK documentation (https://raw.githubusercontent.com/cloudflare/cloudflare-python/refs/heads/main/api.md)
            # The method signature is client.dns.records.create(*, zone_id, **params)
            # This means zone_id should be a keyword argument, not a positional argument
            response = self.cf.dns.records.create(zone_id=zone_id, **record_data)
            
            # Access response properties using attribute notation instead of dictionary notation
            if response and hasattr(response, 'id'):
                record_id = response.id
                logger.debug(
                    f"Successfully created DNS record",
                    extra={"record_id": record_id},
                )
                return record_id

            logger.error(
                f"Failed to create DNS record",
                extra={"zone_id": zone_id, "record_name": record_name},
            )
            return None

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
        Update a DNS record using the Cloudflare SDK.
        
        Uses the dns.records.update method from the SDK to update an existing DNS record.

        Args:
            zone_id: Cloudflare zone ID
            record_id: DNS record ID
            record_data: Record data to update, which may include:
                        - type: Record type (A, AAAA, CNAME, etc.)
                        - name: Record name (e.g., "subdomain.example.com")
                        - content: Record content (e.g., IP address)
                        - ttl: Time to live in seconds (1 for automatic)
                        - proxied: Whether the record is proxied

        Returns:
            True if successful, False otherwise
            
        Example:
            updated = client.update_dns_record(
                zone_id, 
                record_id, 
                {"content": "192.0.2.2", "ttl": 1}
            )
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

            # According to the Cloudflare SDK documentation
            # The method signature is:
            # client.dns.records.update(record_id, *, zone_id, **params)
            # Note: record_id is positional but zone_id is a keyword argument
            response = self.cf.dns.records.update(record_id, zone_id=zone_id, **record_data)
            
            # Check response using attribute access
            if response:
                logger.debug(f"Successfully updated DNS record")
                return True

            logger.error(
                f"Failed to update DNS record",
                extra={"zone_id": zone_id, "record_id": record_id, "record_name": record_name},
            )
            return False

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
        Delete a DNS record using the Cloudflare SDK.
        
        Uses the dns.records.delete method from the SDK to remove an existing DNS record.

        Args:
            zone_id: Cloudflare zone ID
            record_id: DNS record ID

        Returns:
            True if successful, False otherwise
            
        Example:
            deleted = client.delete_dns_record(zone_id, record_id)
        """
        try:
            logger.debug(
                f"Deleting DNS record",
                extra={"zone_id": zone_id, "record_id": record_id},
            )

            # According to the Cloudflare SDK documentation
            # The method signature is:
            # client.dns.records.delete(record_id, *, zone_id)
            # Note: record_id is positional but zone_id is a keyword argument
            response = self.cf.dns.records.delete(record_id, zone_id=zone_id)
            
            if response:
                logger.debug(f"Successfully deleted DNS record")
                return True

            logger.error(
                f"Failed to delete DNS record",
                extra={"zone_id": zone_id, "record_id": record_id},
            )
            return False

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
