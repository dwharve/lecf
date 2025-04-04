"""Tests for the DDNS Manager."""

from datetime import datetime
from unittest.mock import Mock, patch

from lecf.managers.ddns import DdnsManager


class TestDdnsManager:
    """Tests for the DdnsManager class."""

    @patch("lecf.managers.ddns.get_env")
    @patch("lecf.managers.ddns.get_env_int")
    @patch("lecf.managers.ddns.CloudflareClient")
    def setup_method(self, method, mock_cf_client, mock_get_env_int, mock_get_env):
        """Set up the test fixtures."""
        # Mock environment variables
        mock_get_env.side_effect = lambda key, required=False, default=None: {}.get(key, default)

        mock_get_env_int.side_effect = lambda key, default=None: {
            "DDNS_CHECK_INTERVAL_MINUTES": 15
        }.get(key, default)

        # Mock config.APP_CONFIG
        with patch.dict(
            "lecf.utils.config.APP_CONFIG",
            {
                "ddns": {
                    "domains": [
                        {"domain": "example.com", "subdomains": "@,www"},
                        {"domain": "test.com", "subdomains": "@"},
                    ]
                }
            },
        ):
            # Create instance
            self.manager = DdnsManager()

        # Set up mocks
        self.mock_cf_client_instance = mock_cf_client.return_value

    def test_initialization(self):
        """Test DdnsManager initialization."""
        assert self.manager.service_name == "ddns"
        assert self.manager.check_interval == 15
        assert self.manager.interval_unit == "minutes"

        # Check domains were parsed correctly
        assert len(self.manager.domains) == 2
        assert "example.com" in self.manager.domains
        assert "test.com" in self.manager.domains
        assert set(self.manager.domains["example.com"]["subdomains"]) == set(["@", "www"])
        assert set(self.manager.domains["test.com"]["subdomains"]) == set(["@"])

        # Verify default record types is always A
        assert self.manager.default_record_types == ["A"]

        # Verify state variables
        assert self.manager.current_ip is None
        assert self.manager.last_check_time is None

    def test_setup_interval(self):
        """Test _setup_interval method."""
        assert self.manager.check_interval == 15
        assert self.manager.interval_unit == "minutes"

    def test_parse_domains_new_format(self):
        """Test domain parsing with dictionary format."""
        domains_config = [
            {"domain": "domain1.com", "subdomains": "@,www", "record_types": "A,AAAA"},
            {"domain": "domain2.com", "subdomains": "sub1,sub2", "record_types": "A"},
            {
                "domain": "domain3.com",
                "subdomains": "@",
                # No record_types specified, should use default
            },
        ]
        result = self.manager._parse_domains(domains_config)

        assert len(result) == 3
        assert "domain1.com" in result
        assert "domain2.com" in result
        assert "domain3.com" in result
        assert set(result["domain1.com"]["subdomains"]) == set(["@", "www"])
        assert set(result["domain2.com"]["subdomains"]) == set(["sub1", "sub2"])
        assert set(result["domain3.com"]["subdomains"]) == set(["@"])
        # Check record types
        assert set(result["domain1.com"]["record_types"]) == set(["A", "AAAA"])
        assert result["domain2.com"]["record_types"] == ["A"]
        assert result["domain3.com"]["record_types"] is None

    def test_parse_domains_empty_config(self):
        """Test domain parsing with empty configuration."""
        domains_config = []
        result = self.manager._parse_domains(domains_config)

        assert len(result) == 0

    @patch("lecf.managers.ddns.datetime")
    @patch("lecf.managers.ddns.logger")
    def test_execute_cycle(self, mock_logger, mock_datetime):
        """Test the _execute_cycle method."""
        # Setup mock datetime
        mock_now = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = mock_now

        # Create a manager with test data
        self.manager.domains = {
            "example.com": {"subdomains": ["@", "www"], "record_types": ["A", "AAAA"]},
            "test.com": {"subdomains": ["@"], "record_types": None},  # Use default
        }
        self.manager.default_record_types = ["A"]

        # Mock the get_public_ip method to return a known value
        self.manager.get_public_ip = lambda: "127.0.0.1"

        # Mock update_dns_record to return a status string
        self.manager.update_dns_record = lambda domain, subdomain, record_type, ip: "updated"

        # Run the method
        self.manager._execute_cycle()

        # Verify the method ran as expected
        assert self.manager.current_ip == "127.0.0.1"  # Now matches our mocked value
        assert self.manager.last_check_time == mock_now

        # Verify logging
        mock_logger.info.assert_any_call(f"Initial IP address detected", extra={"ip": "127.0.0.1"})

        # Check the updated completion log format
        mock_logger.info.assert_any_call(
            f"DDNS update completed",
            extra={
                "domains_processed": 2,
                "records_updated": 5,
                "records_created": 0,
                "records_unchanged": 0,
                "errors": 0,
                "total_records": 5,
            },
        )

    @patch("lecf.managers.ddns.logger")
    def test_update_dns_record(self, mock_logger):
        """Test the update_dns_record method with Cloudflare SDK objects."""
        # Mock Cloudflare client
        self.manager.cloudflare = mock_cf = Mock()

        # Mock zone ID lookup
        mock_cf.get_zone_id.return_value = ("zone123", "example.com")

        # Create a mock DNS record object with attribute-style access
        mock_record = Mock()
        mock_record.id = "record123"
        mock_record.content = "192.168.0.1"  # Current IP
        mock_record.proxied = True

        # Mock DNS records response - return a list containing our mock object
        mock_cf.get_dns_records.return_value = [mock_record]

        # Mock successful update
        mock_cf.update_dns_record.return_value = True

        # Test updating an existing record
        result = self.manager.update_dns_record("example.com", "@", "A", "192.168.0.2")

        # Verify zone_id lookup
        mock_cf.get_zone_id.assert_called_with("example.com")

        # Verify get_dns_records call
        mock_cf.get_dns_records.assert_called_with("zone123", {"name": "example.com", "type": "A"})

        # Verify the record was updated with correct parameters
        mock_cf.update_dns_record.assert_called_with(
            "zone123",
            "record123",
            {
                "name": "example.com",
                "type": "A",
                "content": "192.168.0.2",
                "ttl": 60,
                "proxied": True,  # Should maintain the existing proxied status
            },
        )

        # Verify result is the correct status string
        assert result == "updated"

        # Test when IP hasn't changed
        mock_record.content = "192.168.0.2"  # Same as new IP
        result = self.manager.update_dns_record("example.com", "@", "A", "192.168.0.2")
        assert result == "unchanged"
        # Update shouldn't be called again since IP is the same
        mock_cf.update_dns_record.assert_called_once()

        # Test creating a new record when none exists
        mock_cf.get_dns_records.return_value = []  # No existing records
        mock_cf.create_dns_record.return_value = "new_record_id"

        result = self.manager.update_dns_record("example.com", "www", "A", "192.168.0.2")

        # Verify create DNS record was called with correct parameters
        mock_cf.create_dns_record.assert_called_with(
            "zone123",
            {
                "name": "www.example.com",
                "type": "A",
                "content": "192.168.0.2",
                "ttl": 60,
                "proxied": False,  # New records default to not proxied
            },
        )

        # Verify result is the correct status string
        assert result == "created"

        # Test error handling
        mock_cf.get_zone_id.return_value = (None, None)  # Zone not found
        result = self.manager.update_dns_record("nonexistent.com", "@", "A", "192.168.0.2")
        assert result == "error"
