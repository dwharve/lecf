"""Tests for the CLI module."""

import argparse
import sys
from unittest.mock import MagicMock, patch

import pytest

from lecf import cli
from lecf.core import BaseManager


class TestCli:
    """Tests for the CLI module."""

    @patch("lecf.cli.importlib.import_module")
    def test_initialize_manager_success(self, mock_import_module):
        """Test initialize_manager success case."""
        # Setup mock
        mock_manager_instance = MagicMock(spec=BaseManager)
        mock_manager_class = MagicMock(return_value=mock_manager_instance)
        mock_module = MagicMock()
        mock_module.CertificateManager = mock_manager_class
        mock_import_module.return_value = mock_module

        # Call the function
        manager = cli.initialize_manager("certificate")

        # Verify the function behavior
        mock_import_module.assert_called_with("lecf.managers.certificate")
        assert manager == mock_manager_instance

    def test_initialize_manager_unknown(self):
        """Test initialize_manager with unknown manager key."""
        with pytest.raises(ValueError, match="Unknown manager: unknown_manager"):
            cli.initialize_manager("unknown_manager")

    @patch("lecf.cli.importlib.import_module")
    @patch("lecf.cli.logger")
    def test_initialize_manager_error(self, mock_logger, mock_import_module):
        """Test initialize_manager error handling."""
        # Setup mock to raise exception
        mock_import_module.side_effect = ImportError("Test error")

        # Call the function and verify it raises
        with pytest.raises(ImportError):
            cli.initialize_manager("certificate")

        # Verify logging
        mock_logger.error.assert_called_with(
            "Failed to initialize certificate manager",
            extra={"error": "Test error", "error_type": "ImportError"},
        )

    @patch("lecf.cli.sys.exit")
    @patch("lecf.cli.logger")
    def test_initialize_cloudflare_credentials_success(self, mock_logger, mock_exit):
        """Test initialize_cloudflare_credentials success case."""
        with patch("lecf.scripts.setup_cloudflare.setup_cloudflare_credentials") as mock_setup:
            # Call function
            cli.initialize_cloudflare_credentials()

            # Verify setup function was called
            mock_setup.assert_called_once()

    @patch("lecf.cli.sys.exit")
    @patch("lecf.cli.logger")
    def test_initialize_cloudflare_credentials_error(self, mock_logger, mock_exit):
        """Test initialize_cloudflare_credentials error handling."""
        with patch("lecf.scripts.setup_cloudflare.setup_cloudflare_credentials") as mock_setup:
            # Setup mock to raise exception
            mock_setup.side_effect = Exception("Setup error")

            # Call function
            cli.initialize_cloudflare_credentials()

            # Verify error handling and exit
            mock_logger.error.assert_called_with(
                "Failed to initialize Cloudflare credentials", extra={"error": "Setup error"}
            )
            mock_exit.assert_called_with(1)

    def test_parse_args_defaults(self):
        """Test parse_args with default arguments."""
        # Save and restore sys.argv
        old_argv = sys.argv
        try:
            # Set up test arguments
            sys.argv = ["lecf"]
            args = cli.parse_args()

            # Verify defaults
            assert args.service == "all"
            assert args.debug is False

        finally:
            # Restore original sys.argv
            sys.argv = old_argv

    def test_parse_args_with_args(self):
        """Test parse_args with specific arguments."""
        # Save and restore sys.argv
        old_argv = sys.argv
        try:
            # Set up test arguments
            sys.argv = ["lecf", "--service", "certificate", "--debug"]
            args = cli.parse_args()

            # Verify args
            assert args.service == "certificate"
            assert args.debug is True

        finally:
            # Restore original sys.argv
            sys.argv = old_argv

    @patch("lecf.cli.parse_args")
    @patch("lecf.cli.setup_logging")
    @patch("lecf.cli.load_configuration")
    @patch("lecf.cli.initialize_cloudflare_credentials")
    @patch("lecf.cli.schedule_managers")
    def test_main(
        self, mock_schedule, mock_init_cf, mock_load_config, mock_setup_logging, mock_parse_args
    ):
        """Test main function."""
        # Setup mock
        mock_args = argparse.Namespace(service="all", debug=False, config=None)
        mock_parse_args.return_value = mock_args

        # Call function
        cli.main()

        # Verify function calls
        mock_parse_args.assert_called_once()
        mock_setup_logging.assert_called_with("main")
        mock_load_config.assert_called_once_with(None)
        mock_init_cf.assert_called_once()
        mock_schedule.assert_called_once_with(run_once=False)

    @patch("lecf.cli.parse_args")
    @patch("lecf.cli.setup_logging")
    @patch("lecf.cli.load_configuration")
    @patch("lecf.cli.initialize_cloudflare_credentials")
    @patch("lecf.cli.schedule_managers")
    @patch("os.environ", {})
    def test_main_with_debug(
        self, mock_schedule, mock_init_cf, mock_load_config, mock_setup_logging, mock_parse_args
    ):
        """Test main function with debug flag."""
        # Setup mock
        mock_args = argparse.Namespace(service="all", debug=True, config="custom_config.yaml")
        mock_parse_args.return_value = mock_args

        # Call function
        cli.main()

        # Verify debug environment variable was set
        from os import environ

        assert environ.get("LOG_LEVEL") == "DEBUG"

        # Verify function calls
        mock_setup_logging.assert_called_with("main")
        mock_load_config.assert_called_once_with("custom_config.yaml")
        mock_init_cf.assert_called_once()
        mock_schedule.assert_called_once_with(run_once=False)

    @patch("lecf.cli.schedule")
    @patch("lecf.cli.initialize_manager")
    @patch("lecf.cli.logger")
    @patch("lecf.cli.sys.exit")
    def test_schedule_managers_success(
        self, mock_exit, mock_logger, mock_init_manager, mock_schedule
    ):
        """Test schedule_managers with successful initialization of all managers."""
        # Setup mock managers
        mock_manager1 = MagicMock(spec=BaseManager)
        mock_manager1.service_name = "certificate"
        mock_manager1.get_schedule_info.return_value = (24, "hours")

        mock_manager2 = MagicMock(spec=BaseManager)
        mock_manager2.service_name = "ddns"
        mock_manager2.get_schedule_info.return_value = (30, "minutes")

        # Configure initialize_manager to return the mock managers
        mock_init_manager.side_effect = [mock_manager1, mock_manager2]

        # Setup schedule mocks
        mock_minutes = MagicMock()
        mock_hours = MagicMock()
        mock_days = MagicMock()
        mock_schedule.every.return_value.minutes = mock_minutes
        mock_schedule.every.return_value.hours = mock_hours
        mock_schedule.every.return_value.days = mock_days

        # Mock schedule.get_jobs to return some jobs
        mock_job = MagicMock()
        mock_job.next_run = "2023-01-01T12:00:00"  # Updated to match new format
        mock_schedule.get_jobs.return_value = [mock_job]

        # Call function with run_once=True to skip the infinite loop
        cli.schedule_managers(run_once=True)

        # Verify managers were initialized and run
        assert mock_init_manager.call_count == 2
        mock_manager1.run.assert_called_once()
        mock_manager2.run.assert_called_once()

        # Verify schedule was configured
        mock_schedule.every.assert_any_call(24)
        mock_schedule.every.assert_any_call(30)
        mock_hours.do.assert_called_once_with(mock_manager1.run)
        mock_minutes.do.assert_called_once_with(mock_manager2.run)

        # Verify we logged skipping the scheduler loop
        mock_logger.debug.assert_called_with("Running in test mode, skipping scheduler loop")

    @patch("lecf.cli.initialize_manager")
    @patch("lecf.cli.logger")
    @patch("lecf.cli.sys.exit")
    def test_schedule_managers_no_managers(self, mock_exit, mock_logger, mock_init_manager):
        """Test schedule_managers when no managers can be initialized."""
        # Configure initialize_manager to raise an exception
        mock_init_manager.side_effect = Exception("Manager initialization failed")

        # We need to reset the mocks before the test
        mock_exit.reset_mock()
        mock_logger.reset_mock()

        # We need to patch AVAILABLE_MANAGERS to limit the number of services being initialized
        with patch("lecf.cli.AVAILABLE_MANAGERS", {"certificate": None}):
            # Call function with run_once=True (though it will exit early due to no managers)
            cli.schedule_managers(run_once=True)

            # Verify error handling
            mock_logger.error.assert_any_call(
                "Failed to initialize certificate manager, service will be unavailable",
                extra={"error": "Manager initialization failed"},
            )
            mock_logger.error.assert_any_call("No services could be initialized, exiting")

            # We only care that sys.exit was called with code 1
            assert mock_exit.call_count >= 1
            mock_exit.assert_any_call(1)

    @patch("lecf.cli.schedule")
    @patch("lecf.cli.initialize_manager")
    @patch("lecf.cli.logger")
    @patch("lecf.cli.sys.exit")
    def test_schedule_managers_initial_cycle_error(
        self, mock_exit, mock_logger, mock_init_manager, mock_schedule
    ):
        """Test schedule_managers with error during initial cycle."""
        # Setup mock manager that raises an error on run
        mock_manager = MagicMock(spec=BaseManager)
        mock_manager.service_name = "certificate"
        mock_manager.get_schedule_info.return_value = (24, "hours")
        mock_manager.run.side_effect = Exception("Run error")

        # Configure initialize_manager to return the mock manager
        mock_init_manager.return_value = mock_manager

        # Setup schedule mocks
        mock_hours = MagicMock()
        mock_schedule.every.return_value.hours = mock_hours

        # Mock job for get_jobs
        mock_job = MagicMock()
        mock_job.next_run = "2023-01-01T12:00:00"
        mock_schedule.get_jobs.return_value = [mock_job]

        # We need to patch AVAILABLE_MANAGERS to limit the number of services being initialized
        with patch("lecf.cli.AVAILABLE_MANAGERS", {"certificate": None}):
            # Call function with run_once=True
            cli.schedule_managers(run_once=True)

            # Verify error logging - note the message includes "initial"
            mock_logger.error.assert_any_call(
                "Error during initial certificate cycle", extra={"error": "Run error"}
            )

            # Verify schedule was still configured
            mock_schedule.every.assert_called_once_with(24)
            mock_hours.do.assert_called_once_with(mock_manager.run)

            # Verify we logged skipping the scheduler loop
            mock_logger.debug.assert_called_with("Running in test mode, skipping scheduler loop")

    @patch("lecf.cli.schedule")
    @patch("lecf.cli.initialize_manager")
    @patch("lecf.cli.logger")
    @patch("lecf.cli.sys.exit")
    def test_schedule_managers_days_schedule(
        self, mock_exit, mock_logger, mock_init_manager, mock_schedule
    ):
        """Test schedule_managers with days scheduling."""
        # Setup mock manager with days interval
        mock_manager = MagicMock(spec=BaseManager)
        mock_manager.service_name = "certificate"
        mock_manager.get_schedule_info.return_value = (7, "days")

        # Configure initialize_manager to return the mock manager
        mock_init_manager.return_value = mock_manager

        # Setup schedule mocks
        mock_days = MagicMock()
        mock_schedule.every.return_value.days = mock_days

        # Mock schedule.get_jobs to return some jobs
        mock_job = MagicMock()
        mock_job.next_run = "2023-01-01T12:00:00"
        mock_schedule.get_jobs.return_value = [mock_job]

        # We need to patch AVAILABLE_MANAGERS to limit the number of services being initialized
        with patch("lecf.cli.AVAILABLE_MANAGERS", {"certificate": None}):
            # Call function with run_once=True
            cli.schedule_managers(run_once=True)

            # Verify days scheduling was used
            mock_schedule.every.assert_called_once_with(7)
            mock_days.do.assert_called_once_with(mock_manager.run)

            # Verify we logged skipping the scheduler loop
            mock_logger.debug.assert_called_with("Running in test mode, skipping scheduler loop")

    @patch("lecf.cli.schedule")
    @patch("lecf.cli.initialize_manager")
    @patch("lecf.cli.logger")
    @patch("lecf.cli.sys.exit")
    def test_schedule_managers_unknown_interval_unit(
        self, mock_exit, mock_logger, mock_init_manager, mock_schedule
    ):
        """Test schedule_managers with an unknown interval unit."""
        # Setup mock manager with unknown interval unit
        mock_manager = MagicMock(spec=BaseManager)
        mock_manager.service_name = "certificate"
        mock_manager.get_schedule_info.return_value = (24, "unknown_unit")

        # Configure initialize_manager to return the mock manager
        mock_init_manager.return_value = mock_manager

        # Setup schedule mocks
        mock_hours = MagicMock()
        mock_schedule.every.return_value.hours = mock_hours

        # Mock schedule.get_jobs to return some jobs
        mock_job = MagicMock()
        mock_job.next_run = "2023-01-01T12:00:00"
        mock_schedule.get_jobs.return_value = [mock_job]

        # We need to patch AVAILABLE_MANAGERS to limit the number of services being initialized
        with patch("lecf.cli.AVAILABLE_MANAGERS", {"certificate": None}):
            # Call function with run_once=True
            cli.schedule_managers(run_once=True)

            # Verify warning about unknown unit
            mock_logger.warning.assert_called_with(
                "Unknown interval unit unknown_unit for certificate, defaulting to hours"
            )

            # Verify schedule defaults to hours
            mock_schedule.every.assert_called_once_with(24)
            mock_hours.do.assert_called_once_with(mock_manager.run)

            # Verify we logged skipping the scheduler loop
            mock_logger.debug.assert_called_with("Running in test mode, skipping scheduler loop")

    @patch("lecf.cli.config.load_yaml_config")
    @patch("lecf.cli.logger")
    @patch("lecf.cli.setup_logging")
    @patch("lecf.utils.config.APP_CONFIG", {})  # Start with empty config
    def test_load_configuration_success(self, mock_setup_logging, mock_logger, mock_load_yaml):
        """Test load_configuration success case."""
        # Set up mock to return a valid config
        test_config = {
            "logging": {"level": "DEBUG", "file": "/var/log/test.log"},
            "cloudflare": {"email": "test@example.com"},
        }
        mock_load_yaml.return_value = test_config

        # Call function
        cli.load_configuration("test_config.yaml")

        # Verify load_yaml_config was called with the right parameter
        mock_load_yaml.assert_called_once_with("test_config.yaml")

        # Verify logging was set up through logger calls
        mock_logger.info.assert_any_call("Configuration loaded successfully")
        mock_logger.info.assert_any_call("Log level set to DEBUG")
        mock_logger.info.assert_any_call("Log file set to /var/log/test.log")
        mock_setup_logging.assert_called_once_with("main")

    @patch("lecf.cli.config.load_yaml_config")
    @patch("lecf.cli.logger")
    def test_load_configuration_file_not_found(self, mock_logger, mock_load_yaml):
        """Test load_configuration when file is not found."""
        # Set up mock to raise FileNotFoundError
        mock_load_yaml.side_effect = FileNotFoundError("File not found")

        # Call function
        cli.load_configuration("nonexistent.yaml")

        # Verify warning was logged
        mock_logger.warning.assert_called_with(
            "Configuration file not found, using environment variables only"
        )

    @patch("lecf.cli.config.load_yaml_config")
    @patch("lecf.cli.logger")
    def test_load_configuration_error(self, mock_logger, mock_load_yaml):
        """Test load_configuration when an error occurs."""
        # Set up mock to raise an exception
        mock_load_yaml.side_effect = Exception("Test error")

        # Call function
        cli.load_configuration("invalid.yaml")

        # Verify error was logged
        mock_logger.error.assert_called_with(
            "Error loading configuration", extra={"error": "Test error"}
        )
