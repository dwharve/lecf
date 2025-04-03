"""Tests for the BaseManager class."""

from unittest.mock import MagicMock, patch

from lecf.core import BaseManager


class ConcreteManager(BaseManager):
    """Concrete implementation of BaseManager for testing."""

    def __init__(self):
        self._execute_cycle_called = False
        super().__init__("test_service")

    def _setup_interval(self):
        self.check_interval = 60
        self.interval_unit = "minutes"

    def _execute_cycle(self):
        self._execute_cycle_called = True


class TestBaseManager:
    def test_initialization(self):
        manager = ConcreteManager()
        assert manager.service_name == "test_service"
        assert manager.check_interval == 60
        assert manager.interval_unit == "minutes"

    def test_get_schedule_info(self):
        manager = ConcreteManager()
        interval, unit = manager.get_schedule_info()
        assert interval == 60
        assert unit == "minutes"

    @patch("lecf.core.base_manager.logger")
    def test_run_success(self, mock_logger):
        manager = ConcreteManager()
        manager.run()
        assert manager._execute_cycle_called
        mock_logger.debug.assert_any_call("Running test_service cycle")
        mock_logger.debug.assert_any_call("test_service cycle completed")

    @patch("lecf.core.base_manager.logger")
    def test_run_exception(self, mock_logger):
        manager = ConcreteManager()
        manager._execute_cycle = MagicMock(side_effect=Exception("Test error"))

        manager.run()
        mock_logger.error.assert_called_with(
            "Error during test_service cycle",
            extra={"error": "Test error", "error_type": "Exception"},
        )
