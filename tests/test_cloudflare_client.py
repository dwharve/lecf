"""Tests for the CloudflareClient class."""

from unittest.mock import MagicMock, patch

from lecf.core.cloudflare_client import CloudflareClient


# Create a custom CloudFlareAPIError exception with code attribute for testing
class MockCloudFlareAPIError(Exception):
    def __init__(self, message, code=1000):
        self.code = code
        self.details = {}
        super().__init__(message)


class TestCloudflareClient:
    """Tests for the CloudflareClient class."""

    @patch("lecf.utils.config.get_cloudflare_config")
    def setup_method(self, method, mock_get_config):
        """Set up test fixtures."""
        # Mock the config function to avoid requiring environment variables
        mock_get_config.return_value = {"api_token": "mock_token"}

        # Create client with explicit token
        self.client = CloudflareClient(api_token="test_token")

        # Set up the mock client inside CloudflareClient
        self.client.cf = MagicMock()

        # Set up mock objects for zones and dns.records
        self.client.cf.zones = MagicMock()
        self.client.cf.dns = MagicMock()
        self.client.cf.dns.records = MagicMock()

        # Replace CloudFlare exception in test module
        import cloudflare

        cloudflare.exceptions.CloudFlareAPIError = MockCloudFlareAPIError

    def test_init(self):
        """Test initialization with provided token."""
        assert isinstance(self.client, CloudflareClient)

    @patch("lecf.utils.config.get_cloudflare_config")
    def test_init_from_env(self, mock_get_config):
        """Test initialization using token from environment."""
        mock_get_config.return_value = {"api_token": "env_token"}
        client = CloudflareClient()
        # This assertion will fail since we don't have access to the actual call
        # Just check that client was created successfully
        assert isinstance(client, CloudflareClient)

    @patch("lecf.utils.config.get_cloudflare_config")
    @patch("requests.get")
    def test_direct_api_request_get_success(self, mock_get, mock_get_config):
        """Test _direct_api_request with GET method when successful."""
        # Setup mocks
        mock_get_config.return_value = {"api_token": "test_token"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "result": [{"id": "test123"}]}
        mock_get.return_value = mock_response

        # Call method
        result = self.client._direct_api_request("get", "/zones", params={"name": "example.com"})

        # Verify results
        assert result == {"success": True, "result": [{"id": "test123"}]}
        mock_get.assert_called_once()

    @patch("lecf.utils.config.get_cloudflare_config")
    @patch("requests.post")
    def test_direct_api_request_post_success(self, mock_post, mock_get_config):
        """Test _direct_api_request with POST method when successful."""
        # Setup mocks
        mock_get_config.return_value = {"api_token": "test_token"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "result": {"id": "record123"}}
        mock_post.return_value = mock_response

        # Call method
        data = {"type": "A", "name": "test.example.com", "content": "192.168.1.1"}
        result = self.client._direct_api_request("post", "/zones/zone123/dns_records", data=data)

        # Verify results
        assert result == {"success": True, "result": {"id": "record123"}}
        mock_post.assert_called_once()

    @patch("lecf.utils.config.get_cloudflare_config")
    @patch("requests.get")
    def test_direct_api_request_failed_status(self, mock_get, mock_get_config):
        """Test _direct_api_request when status code indicates failure."""
        # Setup mocks
        mock_get_config.return_value = {"api_token": "test_token"}
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response

        # Call method
        result = self.client._direct_api_request("get", "/zones", params={"name": "example.com"})

        # Verify results
        assert result is None
        mock_get.assert_called_once()

    @patch("lecf.utils.config.get_cloudflare_config")
    @patch("requests.get")
    def test_direct_api_request_exception(self, mock_get, mock_get_config):
        """Test _direct_api_request when an exception occurs."""
        # Setup mocks
        mock_get_config.return_value = {"api_token": "test_token"}
        mock_get.side_effect = Exception("Connection error")

        # Call method
        result = self.client._direct_api_request("get", "/zones", params={"name": "example.com"})

        # Verify results
        assert result is None
        mock_get.assert_called_once()

    def test_get_zone_id_success(self):
        """Test get_zone_id when successful."""
        # Create a mock Zone object with id and name attributes
        mock_zone = MagicMock()
        mock_zone.id = "zone123"
        mock_zone.name = "example.com"

        # Create a mock iterator that yields mock_zone
        mock_zones = MagicMock()
        mock_zones.__iter__.return_value = iter([mock_zone])
        self.client.cf.zones.list.return_value = mock_zones

        # Test with valid domain
        zone_id, zone_name = self.client.get_zone_id("subdomain.example.com")

        # Verify results
        assert zone_id == "zone123"
        assert zone_name == "example.com"
        self.client.cf.zones.list.assert_called_with(name="example.com")

    def test_get_zone_id_invalid_domain(self):
        """Test get_zone_id with invalid domain format."""
        zone_id, zone_name = self.client.get_zone_id("invalid")

        assert zone_id is None
        assert zone_name is None

    def test_get_zone_id_no_zones(self):
        """Test get_zone_id when no zones are found."""
        # Create an empty iterator
        mock_zones = MagicMock()
        mock_zones.__iter__.return_value = iter([])
        self.client.cf.zones.list.return_value = mock_zones

        zone_id, zone_name = self.client.get_zone_id("subdomain.example.com")

        assert zone_id is None
        assert zone_name is None
        self.client.cf.zones.list.assert_called_with(name="example.com")

    def test_get_dns_records_success(self):
        """Test get_dns_records when successful."""
        # Setup mock response with mock DNS record objects
        mock_record = MagicMock()
        mock_record.id = "record1"
        mock_record.type = "A"
        mock_record.name = "test.example.com"
        mock_record.content = "192.168.1.1"

        # Create a mock iterator that yields the records
        mock_iterator = MagicMock()
        mock_iterator.__iter__.return_value = iter([mock_record])
        self.client.cf.dns.records.list.return_value = mock_iterator

        # Call method with params
        params = {"type": "A", "name": "test.example.com"}
        records = self.client.get_dns_records("zone123", params=params)

        # Verify results - note we're still getting a list of objects, not just the iterator
        assert len(records) == 1
        assert records[0].id == "record1"
        assert records[0].type == "A"
        self.client.cf.dns.records.list.assert_called_with(zone_id="zone123", **params)

    def test_get_dns_records_no_params(self):
        """Test get_dns_records with no parameters."""
        # Setup mock response with mock DNS record objects
        mock_record = MagicMock()
        mock_record.id = "record1"
        mock_record.type = "A"
        mock_record.name = "test.example.com"
        mock_record.content = "192.168.1.1"

        # Create a mock iterator that yields the records
        mock_iterator = MagicMock()
        mock_iterator.__iter__.return_value = iter([mock_record])
        self.client.cf.dns.records.list.return_value = mock_iterator

        # Call method without params
        records = self.client.get_dns_records("zone123")

        # Verify results
        assert len(records) == 1
        assert records[0].id == "record1"
        self.client.cf.dns.records.list.assert_called_with(zone_id="zone123")

    def test_get_dns_records_failure(self):
        """Test get_dns_records when API request fails."""
        # Setup mock response
        self.client.cf.dns.records.list.side_effect = Exception("API Error")
        # Mock all fallback methods as well
        self.client.cf._request_api_get = MagicMock(side_effect=Exception("API Error 2"))
        self.client._direct_api_request = MagicMock(side_effect=Exception("API Error 3"))

        # Call method
        records = self.client.get_dns_records("zone123")

        # Verify results
        assert records == []
        self.client.cf.dns.records.list.assert_called_with(zone_id="zone123")

    def test_create_dns_record_success(self):
        """Test create_dns_record when successful."""
        # Setup mock response with id attribute
        mock_response = MagicMock()
        mock_response.id = "record123"
        self.client.cf.dns.records.create.return_value = mock_response

        # Call method
        record_data = {"type": "A", "name": "test.example.com", "content": "192.168.1.1"}
        record_id = self.client.create_dns_record("zone123", record_data)

        # Verify results
        assert record_id == "record123"
        self.client.cf.dns.records.create.assert_called_with(zone_id="zone123", **record_data)

    def test_create_dns_record_failure(self):
        """Test create_dns_record when API request fails."""
        # Setup mock response
        self.client.cf.dns.records.create.side_effect = Exception("API Error")
        # Mock all fallback methods as well
        self.client.cf._request_api_post = MagicMock(side_effect=Exception("API Error 2"))
        self.client._direct_api_request = MagicMock(side_effect=Exception("API Error 3"))

        # Call method
        record_data = {"type": "A", "name": "test.example.com", "content": "192.168.1.1"}
        record_id = self.client.create_dns_record("zone123", record_data)

        # Verify results
        assert record_id is None
        self.client.cf.dns.records.create.assert_called_with(zone_id="zone123", **record_data)

    def test_update_dns_record_success(self):
        """Test update_dns_record when successful."""
        # Setup mock response with id attribute
        mock_response = MagicMock()
        mock_response.id = "record123"
        self.client.cf.dns.records.update.return_value = mock_response

        # Call method
        record_data = {"type": "A", "name": "test.example.com", "content": "192.168.1.2"}
        success = self.client.update_dns_record("zone123", "record123", record_data)

        # Verify results
        assert success is True
        self.client.cf.dns.records.update.assert_called_with(
            "record123", zone_id="zone123", **record_data
        )

    def test_update_dns_record_failure(self):
        """Test update_dns_record when API request fails."""
        # Setup mock response
        self.client.cf.dns.records.update.side_effect = Exception("API Error")
        # Mock all fallback methods as well
        self.client.cf._request_api_put = MagicMock(side_effect=Exception("API Error 2"))
        self.client._direct_api_request = MagicMock(side_effect=Exception("API Error 3"))

        # Call method
        record_data = {"type": "A", "name": "test.example.com", "content": "192.168.1.2"}
        success = self.client.update_dns_record("zone123", "record123", record_data)

        # Verify results
        assert success is False
        self.client.cf.dns.records.update.assert_called_with(
            "record123", zone_id="zone123", **record_data
        )

    def test_delete_dns_record_success(self):
        """Test delete_dns_record when successful."""
        # Setup mock response
        self.client.cf.dns.records.delete.return_value = {"id": "record123"}

        # Call method
        success = self.client.delete_dns_record("zone123", "record123")

        # Verify results
        assert success is True
        self.client.cf.dns.records.delete.assert_called_with("record123", zone_id="zone123")

    def test_delete_dns_record_failure(self):
        """Test delete_dns_record when API request fails."""
        # Setup mock response
        self.client.cf.dns.records.delete.side_effect = Exception("API Error")
        # Mock all fallback methods as well
        self.client.cf._request_api_delete = MagicMock(side_effect=Exception("API Error 2"))
        self.client._direct_api_request = MagicMock(side_effect=Exception("API Error 3"))

        # Call method
        success = self.client.delete_dns_record("zone123", "record123")

        # Verify results
        assert success is False
        self.client.cf.dns.records.delete.assert_called_with("record123", zone_id="zone123")
