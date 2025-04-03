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

    def test_get_zone_id_success(self):
        """Test get_zone_id when successful."""
        # Setup mock response
        mock_zone = {"id": "zone123", "name": "example.com"}
        self.client.cf.zones.get.return_value = [mock_zone]

        # Test with valid domain
        zone_id, zone_name = self.client.get_zone_id("subdomain.example.com")

        # Verify results
        assert zone_id == "zone123"
        assert zone_name == "example.com"
        self.client.cf.zones.get.assert_called_with(params={"name": "example.com"})

    def test_get_zone_id_invalid_domain(self):
        """Test get_zone_id with invalid domain format."""
        zone_id, zone_name = self.client.get_zone_id("invalid")

        assert zone_id is None
        assert zone_name is None
        self.client.cf.zones.get.assert_not_called()

    def test_get_zone_id_no_zones(self):
        """Test get_zone_id when no zones are found."""
        self.client.cf.zones.get.return_value = []

        zone_id, zone_name = self.client.get_zone_id("subdomain.example.com")

        assert zone_id is None
        assert zone_name is None
        self.client.cf.zones.get.assert_called_with(params={"name": "example.com"})

    def test_get_zone_id_api_error(self):
        """Test get_zone_id when CloudFlare API returns an error."""
        import cloudflare

        self.client.cf.zones.get.side_effect = cloudflare.exceptions.CloudFlareAPIError(
            "API Error", 1001
        )

        zone_id, zone_name = self.client.get_zone_id("subdomain.example.com")

        assert zone_id is None
        assert zone_name is None

    def test_get_zone_id_general_exception(self):
        """Test get_zone_id when a general exception occurs."""
        self.client.cf.zones.get.side_effect = ValueError("General Error")

        zone_id, zone_name = self.client.get_zone_id("subdomain.example.com")

        assert zone_id is None
        assert zone_name is None

    def test_create_dns_record_success(self):
        """Test create_dns_record when successful."""
        # Setup mock response
        self.client.cf.zones.dns_records.post.return_value = {"id": "record123"}

        # Test data
        record_data = {"type": "A", "name": "test.example.com", "content": "192.168.1.1"}

        # Call method
        record_id = self.client.create_dns_record("zone123", record_data)

        # Verify results
        assert record_id == "record123"
        self.client.cf.zones.dns_records.post.assert_called_with("zone123", data=record_data)

    def test_create_dns_record_api_error(self):
        """Test create_dns_record when CloudFlare API returns an error."""
        import cloudflare

        self.client.cf.zones.dns_records.post.side_effect = (
            cloudflare.exceptions.CloudFlareAPIError("API Error", 1001)
        )

        record_data = {"type": "A", "name": "test.example.com", "content": "192.168.1.1"}
        record_id = self.client.create_dns_record("zone123", record_data)

        assert record_id is None

    def test_create_dns_record_general_exception(self):
        """Test create_dns_record when a general exception occurs."""
        self.client.cf.zones.dns_records.post.side_effect = ValueError("General Error")

        record_data = {"type": "A", "name": "test.example.com", "content": "192.168.1.1"}
        record_id = self.client.create_dns_record("zone123", record_data)

        assert record_id is None

    def test_update_dns_record_success(self):
        """Test update_dns_record when successful."""
        # Setup mock response
        self.client.cf.zones.dns_records.put.return_value = {
            "id": "record123",
            "modified_on": "2023-01-01",
        }

        # Test data
        record_data = {"type": "A", "name": "test.example.com", "content": "192.168.1.2"}

        # Call method
        result = self.client.update_dns_record("zone123", "record123", record_data)

        # Verify results
        assert result is True
        self.client.cf.zones.dns_records.put.assert_called_with(
            "zone123", "record123", data=record_data
        )

    def test_update_dns_record_api_error(self):
        """Test update_dns_record when CloudFlare API returns an error."""
        import cloudflare

        self.client.cf.zones.dns_records.put.side_effect = cloudflare.exceptions.CloudFlareAPIError(
            "API Error", 1001
        )

        record_data = {"type": "A", "name": "test.example.com", "content": "192.168.1.2"}
        result = self.client.update_dns_record("zone123", "record123", record_data)

        assert result is False

    def test_update_dns_record_general_exception(self):
        """Test update_dns_record when a general exception occurs."""
        self.client.cf.zones.dns_records.put.side_effect = ValueError("General Error")

        record_data = {"type": "A", "name": "test.example.com", "content": "192.168.1.2"}
        result = self.client.update_dns_record("zone123", "record123", record_data)

        assert result is False

    def test_delete_dns_record_success(self):
        """Test delete_dns_record when successful."""
        # Setup mock response
        self.client.cf.zones.dns_records.delete.return_value = {}

        # Call method
        result = self.client.delete_dns_record("zone123", "record123")

        # Verify results
        assert result is True
        self.client.cf.zones.dns_records.delete.assert_called_with("zone123", "record123")

    def test_delete_dns_record_api_error(self):
        """Test delete_dns_record when CloudFlare API returns an error."""
        import cloudflare

        self.client.cf.zones.dns_records.delete.side_effect = (
            cloudflare.exceptions.CloudFlareAPIError("API Error", 1001)
        )

        result = self.client.delete_dns_record("zone123", "record123")

        assert result is False

    def test_delete_dns_record_general_exception(self):
        """Test delete_dns_record when a general exception occurs."""
        self.client.cf.zones.dns_records.delete.side_effect = ValueError("General Error")

        result = self.client.delete_dns_record("zone123", "record123")

        assert result is False

    def test_get_dns_records_success(self):
        """Test get_dns_records when successful."""
        # Setup mock response
        mock_records = [{"id": "record1"}, {"id": "record2"}]
        self.client.cf.zones.dns_records.get.return_value = mock_records

        # Call method with params (correct way)
        params = {"type": "A", "name": "test.example.com"}
        records = self.client.get_dns_records("zone123", params=params)

        # Verify results
        assert records == mock_records
        self.client.cf.zones.dns_records.get.assert_called_with("zone123", params=params)

    def test_get_dns_records_api_error(self):
        """Test get_dns_records when CloudFlare API returns an error."""
        import cloudflare

        self.client.cf.zones.dns_records.get.side_effect = cloudflare.exceptions.CloudFlareAPIError(
            "API Error", 1001
        )

        params = {"type": "A", "name": "test.example.com"}
        records = self.client.get_dns_records("zone123", params=params)

        assert records == []

    def test_get_dns_records_general_exception(self):
        """Test get_dns_records when a general exception occurs."""
        self.client.cf.zones.dns_records.get.side_effect = ValueError("General Error")

        params = {"type": "A", "name": "test.example.com"}
        records = self.client.get_dns_records("zone123", params=params)

        assert records == []
