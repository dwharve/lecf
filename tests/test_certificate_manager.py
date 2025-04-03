"""Tests for the Certificate Manager."""

from datetime import datetime
from unittest.mock import patch

from lecf.managers.certificate import CertificateManager


class TestCertificateManager:
    """Tests for the CertificateManager class."""

    @patch("lecf.managers.certificate.get_env")
    @patch("lecf.managers.certificate.get_env_int")
    @patch("lecf.managers.certificate.CloudflareClient")
    @patch(
        "lecf.managers.certificate.config.APP_CONFIG",
        {
            "certificate": {
                "cert_dir": "/test/cert/dir",
                "renewal_threshold_days": 30,
                "check_interval_hours": 12,
                "email": "test@example.com",
            }
        },
    )
    def setup_method(self, method, mock_cf_client, mock_get_env_int, mock_get_env):
        """Set up the test fixtures."""
        # Mock environment variables
        mock_get_env.side_effect = lambda key, required=False, default=None: {
            "DOMAINS": "example.com,www.example.com;test.com",
            "CERTBOT_EMAIL": "test@example.com",
        }.get(key, default)

        mock_get_env_int.side_effect = lambda key, default=None: {
            "CERT_RENEWAL_THRESHOLD_DAYS": 30,
            "CERT_CHECK_INTERVAL_HOURS": 12,
        }.get(key, default)

        # Create instance
        self.manager = CertificateManager()

        # Set up mocks
        self.mock_cf_client_instance = mock_cf_client.return_value

    def test_initialization(self):
        """Test CertificateManager initialization."""
        assert self.manager.service_name == "certificate"
        assert self.manager.email == "test@example.com"
        assert self.manager.cert_dir == "/test/cert/dir"
        assert self.manager.renewal_threshold == 30
        assert self.manager.check_interval == 12
        assert self.manager.interval_unit == "hours"

        # Check domains were parsed correctly
        assert len(self.manager.domains) == 2
        assert set(["example.com", "www.example.com"]) in self.manager.domains
        assert set(["test.com"]) in self.manager.domains

    def test_setup_interval(self):
        """Test _setup_interval method."""
        assert self.manager.check_interval == 12
        assert self.manager.interval_unit == "hours"

    @patch("lecf.managers.certificate.get_env")
    def test_parse_domains_multiple_groups(self, mock_get_env):
        """Test domain parsing with multiple domain groups."""
        domains_str = "domain1.com,www.domain1.com;domain2.com;domain3.com,sub.domain3.com"
        result = self.manager._parse_domains(domains_str)

        assert len(result) == 3
        assert set(["domain1.com", "www.domain1.com"]) in result
        assert set(["domain2.com"]) in result
        assert set(["domain3.com", "sub.domain3.com"]) in result

    @patch("lecf.managers.certificate.get_env")
    def test_parse_domains_empty_config(self, mock_get_env):
        """Test domain parsing with empty configuration."""
        domains_str = ""
        result = self.manager._parse_domains(domains_str)

        assert len(result) == 0

    @patch("lecf.managers.certificate.get_env")
    def test_parse_domains_with_empty_parts(self, mock_get_env):
        """Test domain parsing with empty parts."""
        # Empty parts should be ignored
        domains_str = "domain1.com,,;domain2.com;;"
        result = self.manager._parse_domains(domains_str)

        assert len(result) == 2
        assert set(["domain1.com"]) in result
        assert set(["domain2.com"]) in result

    @patch("lecf.managers.certificate.datetime")
    @patch("lecf.managers.certificate.logger")
    def test_execute_cycle(self, mock_logger, mock_datetime):
        """Test the _execute_cycle method."""
        # Setup mock datetime
        mock_now = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = mock_now

        # Run the method
        self.manager._execute_cycle()

        # Verify the method ran as expected
        assert self.manager.last_check_time == mock_now

        # Verify logging was done for each domain group
        assert mock_logger.info.call_count >= 2  # One call per domain group
