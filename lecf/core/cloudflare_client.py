"""Cloudflare API client for interacting with Cloudflare services."""

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

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
        # Disable noisy HTTP request/response logging from the Cloudflare SDK
        self._configure_sdk_logging()

        cf_config = config.get_cloudflare_config(config.APP_CONFIG)

        # Check if we should create credentials file for the SDK
        use_cred_file = config.get_env_bool("CLOUDFLARE_USE_CREDENTIALS_FILE", False)

        if use_cred_file:
            # Create credentials file in ~/.secrets/cloudflare.ini
            home_dir = os.path.expanduser("~")
            secrets_dir = os.path.join(home_dir, ".secrets")
            cred_file_path = os.path.join(secrets_dir, "cloudflare.ini")

            # Create directory if it doesn't exist
            if not os.path.exists(secrets_dir):
                os.makedirs(secrets_dir, exist_ok=True)

            # Create/update credentials file
            with open(cred_file_path, "w", encoding="utf-8") as f:
                f.write("[cloudflare]\n")
                f.write(f"token = {api_token or cf_config['api_token']}\n")

            logger.debug(f"Created Cloudflare credentials file at {cred_file_path}")

            # Create client with credentials file
            self.cf = Client()
        else:
            # Create client with direct token
            self.cf = Client(api_token=api_token or cf_config["api_token"])

        logger.debug("CloudflareClient initialized")

    def _configure_sdk_logging(self):
        """Configure logging for the Cloudflare SDK to reduce verbosity."""
        # Cloudflare SDK uses httpx which uses httpcore which both log detailed HTTP requests
        # Disable or set to higher level to reduce noise
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
        logging.getLogger("httpcore.http11").setLevel(logging.WARNING)

        # Cloudflare SDK itself might log at INFO level
        logging.getLogger("cloudflare").setLevel(logging.WARNING)

    def _call_sdk_api(self, operation_name: str, methods: List[Callable], *args, **kwargs) -> Any:
        """
        Helper method to call Cloudflare SDK methods with multiple fallback strategies.

        Args:
            operation_name: Name of the operation for logging
            methods: List of method callables to try
            *args: Positional arguments to pass to the methods
            **kwargs: Keyword arguments to pass to the methods

        Returns:
            Return value from the first successful method call

        Raises:
            Exception: If all methods fail
        """
        all_errors = []

        for i, method in enumerate(methods):
            try:
                return method(*args, **kwargs)
            except Exception as e:
                all_errors.append(str(e))
                continue

        # If we get here, all methods failed
        error_msg = " | ".join(all_errors)
        logger.error(f"All methods failed for {operation_name}", extra={"errors": error_msg})
        raise Exception(f"Failed to {operation_name}: {error_msg}")

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
            logger.debug(f"Making direct API request", extra={"method": method, "url": url})

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
            extra={"domain": domain, "zone_name": zone_name},
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

            logger.debug(f"No zone found for domain", extra={"domain": domain})
            return None, None

        except Exception as e:
            logger.error(
                f"Error getting zone ID",
                extra={
                    "domain": domain,
                    "error": str(e),
                },
            )
            return None, None

    def get_dns_records(self, zone_id: str, params: Dict[str, Any] = None) -> List[Any]:
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
        logger.debug(f"Getting DNS records", extra={"zone_id": zone_id, "params": params})

        try:
            # Define approaches to try
            def approach1():
                if params:
                    return self.cf.dns.records.list(zone_id=zone_id, **params)
                return self.cf.dns.records.list(zone_id=zone_id)

            def approach2():
                endpoint = f"/zones/{zone_id}/dns_records"
                response = self.cf._request_api_get(endpoint, params=params)
                return response.get("result", [])

            def approach3():
                path = f"/zones/{zone_id}/dns_records"
                response = self._direct_api_request("get", path, params=params)
                if response and "result" in response:
                    return response["result"]
                return []

            # Try methods in order
            records_iterator = self._call_sdk_api(
                "get_dns_records", [approach1, approach2, approach3]
            )

            # Convert pagination iterator to a list if it's not already
            try:
                records = list(records_iterator)
            except (TypeError, ValueError):
                # If it's not iterable, it might be direct results from fallback methods
                records = records_iterator

            logger.debug(
                f"Found DNS records",
                extra={"zone_id": zone_id, "count": len(records) if records else 0},
            )
            return records

        except Exception as e:
            logger.error(
                f"Error getting DNS records",
                extra={"zone_id": zone_id, "error": str(e)},
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
        record_name = record_data.get("name", "unknown")
        record_type = record_data.get("type", "unknown")

        logger.debug(
            f"Creating DNS record",
            extra={
                "zone_id": zone_id,
                "record_name": record_name,
                "record_type": record_type,
            },
        )

        try:
            # Define approaches to try
            def approach1():
                return self.cf.dns.records.create(zone_id=zone_id, **record_data)

            def approach2():
                endpoint = f"/zones/{zone_id}/dns_records"
                response = self.cf._request_api_post(endpoint, json_data=record_data)
                if response and "result" in response and "id" in response["result"]:
                    return response["result"]["id"]
                raise Exception("No record ID in response")

            def approach3():
                path = f"/zones/{zone_id}/dns_records"
                response = self._direct_api_request("post", path, data=record_data)
                if response and "result" in response and "id" in response["result"]:
                    return response["result"]["id"]
                raise Exception("No record ID in response")

            # Try methods in order
            response = self._call_sdk_api("create_dns_record", [approach1, approach2, approach3])

            # Handle response from approach1 (SDK object)
            if hasattr(response, "id"):
                record_id = response.id
                logger.info(
                    f"Created DNS record",
                    extra={"record_name": record_name, "record_id": record_id},
                )
                return record_id

            # Handle response from approach2/approach3 (string ID)
            if isinstance(response, str):
                logger.info(
                    f"Created DNS record", extra={"record_name": record_name, "record_id": response}
                )
                return response

            # Unknown response type
            logger.error(
                f"Failed to create DNS record - unexpected response",
                extra={"response_type": type(response)},
            )
            return None

        except Exception as e:
            logger.error(
                f"Error creating DNS record",
                extra={
                    "zone_id": zone_id,
                    "record_name": record_name,
                    "error": str(e),
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
        record_name = record_data.get("name", "unknown")
        record_type = record_data.get("type", "unknown")

        logger.debug(
            f"Updating DNS record",
            extra={
                "zone_id": zone_id,
                "record_id": record_id,
                "record_name": record_name,
            },
        )

        try:
            # Define approaches to try
            def approach1():
                return self.cf.dns.records.update(record_id, zone_id=zone_id, **record_data)

            def approach2():
                endpoint = f"/zones/{zone_id}/dns_records/{record_id}"
                response = self.cf._request_api_put(endpoint, json_data=record_data)
                if response and "success" in response and response["success"]:
                    return True
                raise Exception("Update not successful")

            def approach3():
                path = f"/zones/{zone_id}/dns_records/{record_id}"
                response = self._direct_api_request("put", path, data=record_data)
                if response and "success" in response and response["success"]:
                    return True
                raise Exception("Update not successful")

            # Try methods in order
            response = self._call_sdk_api("update_dns_record", [approach1, approach2, approach3])

            # For approach1, any non-exception response is success
            logger.info(
                f"Updated DNS record", extra={"record_name": record_name, "record_id": record_id}
            )
            return True

        except Exception as e:
            logger.error(
                f"Error updating DNS record",
                extra={
                    "zone_id": zone_id,
                    "record_id": record_id,
                    "error": str(e),
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
        logger.debug(
            f"Deleting DNS record",
            extra={"zone_id": zone_id, "record_id": record_id},
        )

        try:
            # Define approaches to try
            def approach1():
                return self.cf.dns.records.delete(record_id, zone_id=zone_id)

            def approach2():
                endpoint = f"/zones/{zone_id}/dns_records/{record_id}"
                response = self.cf._request_api_delete(endpoint)
                if response and "success" in response and response["success"]:
                    return True
                raise Exception("Delete not successful")

            def approach3():
                path = f"/zones/{zone_id}/dns_records/{record_id}"
                response = self._direct_api_request("delete", path)
                if response and "success" in response and response["success"]:
                    return True
                raise Exception("Delete not successful")

            # Try methods in order
            response = self._call_sdk_api("delete_dns_record", [approach1, approach2, approach3])

            # For approach1, any non-exception response is success
            logger.info(f"Deleted DNS record", extra={"record_id": record_id})
            return True

        except Exception as e:
            logger.error(
                f"Error deleting DNS record",
                extra={
                    "zone_id": zone_id,
                    "record_id": record_id,
                    "error": str(e),
                },
            )
            return False

    # ----- Diagnostic Methods (used for debugging only) ----- #

    def run_diagnostics(self, zone_id: str = None) -> Dict[str, Any]:
        """
        Run diagnostics on the Cloudflare SDK.

        This method is intended for debugging purposes only and should not be used in production.
        It performs various tests to determine the capabilities and structure of the SDK.

        Args:
            zone_id: Optional zone ID to use for testing API methods

        Returns:
            Dictionary with diagnostic results
        """
        results = {
            "sdk_info": self._get_sdk_info(),
            "attributes": self._check_sdk_attributes(),
            "methods": self._check_sdk_methods(),
        }

        # Test API methods if zone_id is provided
        if zone_id:
            results["api_tests"] = self._test_api_methods(zone_id)

        return results

    def _get_sdk_info(self) -> Dict[str, Any]:
        """Get information about the Cloudflare SDK."""
        info = {}
        try:
            info["version"] = self.cf.VERSION if hasattr(self.cf, "VERSION") else "unknown"
            info["class"] = self.cf.__class__.__name__
            info["module"] = self.cf.__class__.__module__
        except Exception as e:
            info["error"] = str(e)
        return info

    def _check_sdk_attributes(self) -> Dict[str, bool]:
        """Check for the existence of key attributes in the SDK."""
        attrs = {}
        # Check top-level attributes
        for attr in ["dns", "zones"]:
            attrs[attr] = hasattr(self.cf, attr)

        # Check dns.records if dns exists
        if attrs.get("dns", False):
            attrs["dns.records"] = hasattr(self.cf.dns, "records")

        return attrs

    def _check_sdk_methods(self) -> Dict[str, bool]:
        """Check for the existence of key methods in the SDK."""
        methods = {}

        # Only check records methods if the attributes exist
        if hasattr(self.cf, "dns") and hasattr(self.cf.dns, "records"):
            for method in ["list", "create", "update", "delete"]:
                methods[f"dns.records.{method}"] = hasattr(self.cf.dns.records, method)

        return methods

    def _test_api_methods(self, zone_id: str) -> Dict[str, Any]:
        """Test API methods with the provided zone ID."""
        results = {}

        # Test get_dns_records
        try:
            records = self.get_dns_records(zone_id)
            results["get_dns_records"] = f"Success, found {len(records) if records else 0} records"
        except Exception as e:
            results["get_dns_records_error"] = str(e)

        # Test direct SDK methods if available
        if hasattr(self.cf, "dns") and hasattr(self.cf.dns, "records"):
            if hasattr(self.cf.dns.records, "list"):
                # Test with keyword args
                try:
                    records = self.cf.dns.records.list(zone_id=zone_id)
                    results["sdk_list_kw"] = "Success"
                except Exception as e:
                    results["sdk_list_kw_error"] = str(e)

                # Test with positional args
                try:
                    records = self.cf.dns.records.list(zone_id)
                    results["sdk_list_pos"] = "Success"
                except Exception as e:
                    results["sdk_list_pos_error"] = str(e)

        return results
