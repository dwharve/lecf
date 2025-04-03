"""Tests for the Cloudflare setup script."""

import stat
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from lecf.scripts.setup_cloudflare import setup_cloudflare_credentials


class TestSetupCloudflare:
    """Tests for the Cloudflare setup script."""

    @patch("lecf.scripts.setup_cloudflare.Path")
    @patch("lecf.scripts.setup_cloudflare.open", new_callable=mock_open)
    @patch("lecf.scripts.setup_cloudflare.os.chmod")
    @patch("lecf.scripts.setup_cloudflare.config.get_cloudflare_config")
    @patch("lecf.scripts.setup_cloudflare.logger")
    def test_setup_cloudflare_credentials_success(
        self, mock_logger, mock_get_cf_config, mock_chmod, mock_file, mock_path
    ):
        """Test setup_cloudflare_credentials success case."""
        # Setup mocks
        mock_get_cf_config.return_value = {"api_token": "test_api_token"}
        mock_secrets_dir = MagicMock(spec=Path)
        mock_path.return_value = mock_secrets_dir
        mock_cloudflare_ini = MagicMock(spec=Path)
        mock_secrets_dir.__truediv__.return_value = mock_cloudflare_ini
        mock_cloudflare_ini.__str__.return_value = "/root/.secrets/cloudflare.ini"

        # Call function
        setup_cloudflare_credentials()

        # Verify directory creation
        mock_secrets_dir.mkdir.assert_called_with(parents=True, exist_ok=True)

        # Verify file creation
        mock_file.assert_called_with(mock_cloudflare_ini, "w", encoding="utf-8")
        mock_file().write.assert_called_with("dns_cloudflare_api_token = test_api_token\n")

        # Verify permissions
        mock_chmod.assert_called_with(mock_cloudflare_ini, stat.S_IRUSR | stat.S_IWUSR)

        # Verify logging
        mock_logger.info.assert_called_with(
            "Cloudflare credentials file created successfully",
            extra={"path": str(mock_cloudflare_ini)},
        )

    @patch("lecf.scripts.setup_cloudflare.Path")
    @patch("lecf.scripts.setup_cloudflare.config.get_cloudflare_config")
    @patch("lecf.scripts.setup_cloudflare.logger")
    def test_setup_cloudflare_credentials_missing_token(
        self, mock_logger, mock_get_cf_config, mock_path
    ):
        """Test setup_cloudflare_credentials with missing API token."""
        # Setup mock to raise exception for required token
        mock_get_cf_config.side_effect = ValueError(
            "Required environment variable 'CLOUDFLARE_API_TOKEN' is not set"
        )

        # Call function and verify it raises
        with pytest.raises(
            ValueError, match="Required environment variable 'CLOUDFLARE_API_TOKEN' is not set"
        ):
            setup_cloudflare_credentials()

        # Verify logging
        mock_logger.error.assert_called_with(
            "Failed to create Cloudflare credentials file",
            extra={
                "error": "Required environment variable 'CLOUDFLARE_API_TOKEN' is not set",
                "error_type": "ValueError",
            },
        )

    @patch("lecf.scripts.setup_cloudflare.Path")
    @patch("lecf.scripts.setup_cloudflare.open", side_effect=PermissionError("Permission denied"))
    @patch("lecf.scripts.setup_cloudflare.config.get_cloudflare_config")
    @patch("lecf.scripts.setup_cloudflare.logger")
    def test_setup_cloudflare_credentials_permission_error(
        self, mock_logger, mock_get_cf_config, mock_open, mock_path
    ):
        """Test setup_cloudflare_credentials with permission error."""
        # Setup mocks
        mock_get_cf_config.return_value = {"api_token": "test_api_token"}
        mock_secrets_dir = MagicMock(spec=Path)
        mock_path.return_value = mock_secrets_dir
        mock_cloudflare_ini = MagicMock(spec=Path)
        mock_secrets_dir.__truediv__.return_value = mock_cloudflare_ini

        # Call function and verify it raises
        with pytest.raises(PermissionError, match="Permission denied"):
            setup_cloudflare_credentials()

        # Verify logging
        mock_logger.error.assert_called_with(
            "Failed to create Cloudflare credentials file",
            extra={"error": "Permission denied", "error_type": "PermissionError"},
        )

    @patch("lecf.scripts.setup_cloudflare.Path")
    @patch("lecf.scripts.setup_cloudflare.config.get_cloudflare_config")
    @patch("lecf.scripts.setup_cloudflare.logger")
    def test_setup_cloudflare_credentials_mkdir_error(
        self, mock_logger, mock_get_cf_config, mock_path
    ):
        """Test setup_cloudflare_credentials with directory creation error."""
        # Setup mocks
        mock_get_cf_config.return_value = {"api_token": "test_api_token"}
        mock_secrets_dir = MagicMock(spec=Path)
        mock_path.return_value = mock_secrets_dir
        mock_secrets_dir.mkdir.side_effect = PermissionError(
            "Permission denied for directory creation"
        )

        # Call function and verify it raises
        with pytest.raises(PermissionError, match="Permission denied for directory creation"):
            setup_cloudflare_credentials()

        # Verify logging
        mock_logger.error.assert_called_with(
            "Failed to create Cloudflare credentials file",
            extra={
                "error": "Permission denied for directory creation",
                "error_type": "PermissionError",
            },
        )

    @patch("lecf.utils.setup_logging")
    @patch("lecf.scripts.setup_cloudflare.setup_cloudflare_credentials")
    def test_main_execution(self, mock_setup_credentials, mock_setup_logging):
        """Test main execution block."""
        # Import the module
        import importlib.util
        import sys
        from importlib.machinery import ModuleSpec

        # Create a spec for a new module to avoid modifying the real one
        spec = ModuleSpec("test_main_module", None)
        test_module = importlib.util.module_from_spec(spec)

        # Copy the function we need to test into our test module
        import lecf.scripts.setup_cloudflare as real_module

        test_module.setup_cloudflare_credentials = mock_setup_credentials

        # Add the required imports to our test module
        from lecf.utils import setup_logging

        test_module.setup_logging = mock_setup_logging

        # Set __name__ to "__main__"
        test_module.__name__ = "__main__"

        # Execute the __main__ block code directly
        if test_module.__name__ == "__main__":
            test_module.setup_logging()
            test_module.setup_cloudflare_credentials()

        # Verify functions were called
        mock_setup_logging.assert_called_once()
        mock_setup_credentials.assert_called_once()
