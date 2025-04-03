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
        
        # Diagnostic information about the structure of the SDK
        self._log_sdk_structure()

    def _log_sdk_structure(self):
        """Log diagnostic information about the Cloudflare SDK structure."""
        try:
            # Log basic client information
            logger.debug("Cloudflare SDK structure diagnostic")
            
            # Check if dns and records attributes exist
            if hasattr(self.cf, 'dns'):
                logger.debug("Client has dns attribute")
                
                if hasattr(self.cf.dns, 'records'):
                    logger.debug("Client.dns has records attribute")
                    
                    # Check the actual methods on the records object
                    records_methods = [method for method in dir(self.cf.dns.records) if not method.startswith('_')]
                    logger.debug(f"Available methods on cf.dns.records: {records_methods}")
                    
                    # Try to get the actual function signature for the list method
                    if hasattr(self.cf.dns.records, 'list'):
                        import inspect
                        try:
                            sig = str(inspect.signature(self.cf.dns.records.list))
                            logger.debug(f"Signature of dns.records.list: {sig}")
                        except Exception as e:
                            logger.debug(f"Could not get signature: {str(e)}")
                else:
                    logger.debug("Client.dns does NOT have records attribute")
            else:
                logger.debug("Client does NOT have dns attribute")
                
        except Exception as e:
            logger.error(f"Error during SDK structure diagnostics: {str(e)}")

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
        logger.debug("DEBUG VERSION CHECK: get_dns_records using keyword arguments")
        try:
            logger.debug(
                f"Getting DNS records",
                extra={"zone_id": zone_id, "params": params},
            )

            # Try different approaches to get DNS records
            try:
                # Approach 1: According to the Cloudflare SDK documentation, use keyword arguments
                if params:
                    records_iterator = self.cf.dns.records.list(zone_id=zone_id, **params)
                else:
                    records_iterator = self.cf.dns.records.list(zone_id=zone_id)
                    
                logger.debug("Successfully called self.cf.dns.records.list with keyword arguments")
            except Exception as e1:
                logger.debug(f"First approach failed: {str(e1)}")
                
                try:
                    # Approach 2: Try direct API calls via the SDK's internal structure
                    # This is a fallback in case the API structure has changed
                    endpoint = f"/zones/{zone_id}/dns_records"
                    if params:
                        response = self.cf._request_api_get(endpoint, params=params)
                    else:
                        response = self.cf._request_api_get(endpoint)
                        
                    logger.debug("Successfully called self.cf._request_api_get directly")
                    return response.get("result", [])
                except Exception as e2:
                    logger.debug(f"Second approach failed: {str(e2)}")
                    
                    # As a last resort, use our direct API request method
                    logger.debug("Falling back to direct API request")
                    path = f"/zones/{zone_id}/dns_records"
                    response = self._direct_api_request("get", path, params=params)
                    if response and "result" in response:
                        return response["result"]
                    raise Exception(f"All approaches failed: {str(e1)}, {str(e2)}")
                
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
        logger.debug("DEBUG VERSION CHECK: create_dns_record using keyword arguments")
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

            # Try different approaches to create DNS records
            try:
                # Approach 1: According to the Cloudflare SDK documentation, use keyword arguments
                response = self.cf.dns.records.create(zone_id=zone_id, **record_data)
                logger.debug("Successfully called self.cf.dns.records.create with keyword arguments")
            except Exception as e1:
                logger.debug(f"First approach failed: {str(e1)}")
                
                try:
                    # Approach 2: Try direct API calls via the SDK's internal structure
                    # This is a fallback in case the API structure has changed
                    endpoint = f"/zones/{zone_id}/dns_records"
                    response = self.cf._request_api_post(endpoint, json_data=record_data)
                    logger.debug("Successfully called self.cf._request_api_post directly")
                    
                    if response and "result" in response and "id" in response["result"]:
                        return response["result"]["id"]
                except Exception as e2:
                    logger.debug(f"Second approach failed: {str(e2)}")
                    
                    # As a last resort, use our direct API request method
                    logger.debug("Falling back to direct API request")
                    path = f"/zones/{zone_id}/dns_records"
                    response = self._direct_api_request("post", path, data=record_data)
                    if response and "result" in response and "id" in response["result"]:
                        return response["result"]["id"]
                    raise Exception(f"All approaches failed: {str(e1)}, {str(e2)}")
            
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
        logger.debug("DEBUG VERSION CHECK: update_dns_record using keyword arguments")
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

            # Try different approaches to update DNS records
            try:
                # Approach 1: According to the Cloudflare SDK documentation
                response = self.cf.dns.records.update(record_id, zone_id=zone_id, **record_data)
                logger.debug("Successfully called self.cf.dns.records.update with record_id and keyword arguments")
            except Exception as e1:
                logger.debug(f"First approach failed: {str(e1)}")
                
                try:
                    # Approach 2: Try direct API calls via the SDK's internal structure
                    endpoint = f"/zones/{zone_id}/dns_records/{record_id}"
                    response = self.cf._request_api_put(endpoint, json_data=record_data)
                    logger.debug("Successfully called self.cf._request_api_put directly")
                    
                    if response and "success" in response and response["success"]:
                        return True
                except Exception as e2:
                    logger.debug(f"Second approach failed: {str(e2)}")
                    
                    # As a last resort, use our direct API request method
                    logger.debug("Falling back to direct API request")
                    path = f"/zones/{zone_id}/dns_records/{record_id}"
                    response = self._direct_api_request("put", path, data=record_data)
                    if response and "success" in response and response["success"]:
                        return True
                    raise Exception(f"All approaches failed: {str(e1)}, {str(e2)}")
            
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
        logger.debug("DEBUG VERSION CHECK: delete_dns_record using keyword arguments")
        try:
            logger.debug(
                f"Deleting DNS record",
                extra={"zone_id": zone_id, "record_id": record_id},
            )

            # Try different approaches to delete DNS records
            try:
                # Approach 1: According to the Cloudflare SDK documentation
                response = self.cf.dns.records.delete(record_id, zone_id=zone_id)
                logger.debug("Successfully called self.cf.dns.records.delete with record_id and keyword arguments")
            except Exception as e1:
                logger.debug(f"First approach failed: {str(e1)}")
                
                try:
                    # Approach 2: Try direct API calls via the SDK's internal structure
                    endpoint = f"/zones/{zone_id}/dns_records/{record_id}"
                    response = self.cf._request_api_delete(endpoint)
                    logger.debug("Successfully called self.cf._request_api_delete directly")
                    
                    if response and "success" in response and response["success"]:
                        return True
                except Exception as e2:
                    logger.debug(f"Second approach failed: {str(e2)}")
                    
                    # As a last resort, use our direct API request method
                    logger.debug("Falling back to direct API request")
                    path = f"/zones/{zone_id}/dns_records/{record_id}"
                    response = self._direct_api_request("delete", path)
                    if response and "success" in response and response["success"]:
                        return True
                    raise Exception(f"All approaches failed: {str(e1)}, {str(e2)}")
            
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

    def test_dns_methods(self, zone_id: str = None) -> Dict[str, Any]:
        """
        Run diagnostic tests on DNS methods.
        
        This is a diagnostic function to test different ways of calling the Cloudflare SDK.

        Args:
            zone_id: Optional zone ID to use for testing

        Returns:
            Dictionary with diagnostic information
        """
        results = {
            "methods": {},
            "attributes": {},
            "tests": {}
        }
        
        # Get SDK information
        try:
            results["sdk_version"] = self.cf.VERSION if hasattr(self.cf, "VERSION") else "unknown"
        except Exception as e:
            results["sdk_version_error"] = str(e)
            
        # Check attributes
        for attr_name in ["dns", "zones"]:
            try:
                results["attributes"][attr_name] = hasattr(self.cf, attr_name)
            except Exception as e:
                results["attributes"][f"{attr_name}_error"] = str(e)
        
        # If dns attribute exists, check records 
        if hasattr(self.cf, "dns"):
            try:
                results["attributes"]["dns.records"] = hasattr(self.cf.dns, "records")
            except Exception as e:
                results["attributes"]["dns.records_error"] = str(e)
        
        # If we have records, check methods
        if hasattr(self.cf, "dns") and hasattr(self.cf.dns, "records"):
            for method_name in ["list", "create", "update", "delete"]:
                try:
                    results["methods"][f"dns.records.{method_name}"] = hasattr(self.cf.dns.records, method_name)
                except Exception as e:
                    results["methods"][f"dns.records.{method_name}_error"] = str(e)
        
        # Test get_zone
        if zone_id:
            # Test get_dns_records with different approaches
            try:
                # Try the current implementation with keyword arguments
                records = self.get_dns_records(zone_id)
                results["tests"]["get_dns_records"] = f"Success, found {len(records)} records"
            except Exception as e:
                results["tests"]["get_dns_records_error"] = str(e)
                
            # Try direct call to list
            if hasattr(self.cf, "dns") and hasattr(self.cf.dns, "records") and hasattr(self.cf.dns.records, "list"):
                try:
                    # Try with keyword argument
                    records = self.cf.dns.records.list(zone_id=zone_id)
                    results["tests"]["direct_list_kw"] = "Success"
                except Exception as e1:
                    results["tests"]["direct_list_kw_error"] = str(e1)
                    
                    try:
                        # Try with positional argument
                        records = self.cf.dns.records.list(zone_id)
                        results["tests"]["direct_list_pos"] = "Success"
                    except Exception as e2:
                        results["tests"]["direct_list_pos_error"] = str(e2)
        
        return results
