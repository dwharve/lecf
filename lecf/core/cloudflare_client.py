"""Cloudflare API client for interacting with Cloudflare services."""

from typing import Any, Dict, List, Optional, Tuple

import cloudflare
from cloudflare import CloudflareClient as Client
from cloudflare.types import Account, Zone, PermissionGroupListResponse

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
        self.cf = Client(api_token=api_token or cf_config["api_token"])
        
        logger.debug("CloudflareClient initialized")

    def _direct_api_request(
        self, method: str, path: str, params: dict = None, data: dict = None
    ) -> Any:
        """
        Make a direct API request to Cloudflare.

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
            # Get zone ID using the SDK
            logger.debug(
                f"Sending Cloudflare API request for zones",
                extra={"domain": domain, "zone_name": zone_name},
            )

            zones = self.cf.zones.list()
            
            # Find our zone
            for zone in zones:
                if isinstance(zone, dict) and zone.get("name") == zone_name:
                    zone_id = zone.get("id")
                    logger.debug(
                        f"Found zone",
                        extra={
                            "zone_id": zone_id,
                            "zone_name": zone_name,
                        },
                    )
                    return zone_id, zone_name
                elif hasattr(zone, "name") and zone.name == zone_name:
                    zone_id = zone.id
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
        Get DNS records for a zone.

        Args:
            zone_id: Cloudflare zone ID
            params: Optional filtering parameters

        Returns:
            List of DNS records
        """
        try:
            logger.debug(
                f"Getting DNS records",
                extra={"zone_id": zone_id, "params": params},
            )

            # Try using the SDK
            try:
                # Convert to dict for consistency in return type
                records = []
                for record in self.cf.zones.dns_records.list(zone_id=zone_id, params=params):
                    if hasattr(record, "__dict__"):
                        record_dict = vars(record)
                    elif isinstance(record, dict):
                        record_dict = record
                    else:
                        # Try to convert to dict
                        record_dict = {}
                        for attr in dir(record):
                            if not attr.startswith("_") and not callable(getattr(record, attr)):
                                record_dict[attr] = getattr(record, attr)
                    
                    records.append(record_dict)
                
                if records:
                    logger.debug(
                        f"Found DNS records using SDK",
                        extra={"zone_id": zone_id, "count": len(records)},
                    )
                    return records
            except Exception as e1:
                logger.debug(
                    f"Failed to get DNS records using SDK",
                    extra={"error": str(e1), "error_type": type(e1).__name__},
                )

            # Fall back to direct API call
            path = f"/zones/{zone_id}/dns_records"
            response = self._direct_api_request("get", path, params)

            if response and "result" in response:
                records = response["result"]
                logger.debug(
                    f"Found DNS records using direct API call",
                    extra={"zone_id": zone_id, "count": len(records)},
                )
                return records

            logger.error(f"Failed to get DNS records", extra={"zone_id": zone_id})
            return []

        except Exception as e:
            logger.error(
                f"Cloudflare API error when getting DNS records",
                extra={"zone_id": zone_id, "error": str(e), "error_type": type(e).__name__},
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

            # Try using the SDK
            try:
                result = self.cf.zones.dns_records.create(zone_id=zone_id, data=record_data)
                
                # Extract ID from the result
                if hasattr(result, "id"):
                    record_id = result.id
                elif isinstance(result, dict) and "id" in result:
                    record_id = result["id"]
                else:
                    # Try to find id in response
                    record_id = None
                    for key, value in vars(result).items():
                        if key == "id":
                            record_id = value
                            break
                
                if record_id:
                    logger.debug(
                        f"Successfully created DNS record using SDK",
                        extra={"record_id": record_id},
                    )
                    return record_id
            except Exception as e1:
                logger.debug(
                    f"Failed to create DNS record using SDK",
                    extra={"error": str(e1), "error_type": type(e1).__name__},
                )

            # Fall back to direct API call
            path = f"/zones/{zone_id}/dns_records"
            response = self._direct_api_request("post", path, data=record_data)

            if response and "result" in response and "id" in response["result"]:
                record_id = response["result"]["id"]
                logger.debug(
                    f"Successfully created DNS record using direct API request",
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

            # Try using the SDK
            try:
                self.cf.zones.dns_records.update(
                    dns_record_id=record_id, zone_id=zone_id, data=record_data
                )
                logger.debug(f"Successfully updated DNS record using SDK")
                return True
            except Exception as e1:
                logger.debug(
                    f"Failed to update DNS record using SDK",
                    extra={"error": str(e1), "error_type": type(e1).__name__},
                )

            # Fall back to direct API call
            path = f"/zones/{zone_id}/dns_records/{record_id}"
            response = self._direct_api_request("put", path, data=record_data)

            if response and "success" in response and response["success"]:
                logger.debug(f"Successfully updated DNS record using direct API request")
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

            # Try using the SDK
            try:
                self.cf.zones.dns_records.delete(dns_record_id=record_id, zone_id=zone_id)
                logger.debug(f"Successfully deleted DNS record using SDK")
                return True
            except Exception as e1:
                logger.debug(
                    f"Failed to delete DNS record using SDK",
                    extra={"error": str(e1), "error_type": type(e1).__name__},
                )

            # Fall back to direct API call
            path = f"/zones/{zone_id}/dns_records/{record_id}"
            response = self._direct_api_request("delete", path)

            if response and "success" in response and response["success"]:
                logger.debug(f"Successfully deleted DNS record using direct API request")
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
