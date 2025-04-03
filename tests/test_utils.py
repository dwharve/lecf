"""Tests for utility functions."""

import logging
import os
from unittest.mock import patch

import pytest

from lecf.utils import (
    get_cloudflare_config,
    get_env,
    get_env_bool,
    get_env_int,
    get_env_list,
    setup_logging,
)


class TestEnvironmentFunctions:
    def test_get_env_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert get_env("TEST_VAR", default="default") == "default"

    def test_get_env_value(self):
        with patch.dict(os.environ, {"TEST_VAR": "value"}, clear=True):
            assert get_env("TEST_VAR", default="default") == "value"

    def test_get_env_required(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                get_env("TEST_VAR", required=True)

    def test_get_env_int_valid(self):
        with patch.dict(os.environ, {"TEST_INT": "42"}, clear=True):
            assert get_env_int("TEST_INT") == 42

    def test_get_env_int_invalid(self):
        with patch.dict(os.environ, {"TEST_INT": "not_an_int"}, clear=True):
            with pytest.raises(ValueError):
                get_env_int("TEST_INT")

    def test_get_env_bool_true_values(self):
        true_values = ["true", "yes", "1", "y", "TRUE", "YES", "Y"]
        for val in true_values:
            with patch.dict(os.environ, {"TEST_BOOL": val}, clear=True):
                assert get_env_bool("TEST_BOOL") is True

    def test_get_env_bool_false_values(self):
        false_values = ["false", "no", "0", "n", "False", "NO", "N", "other"]
        for val in false_values:
            with patch.dict(os.environ, {"TEST_BOOL": val}, clear=True):
                assert get_env_bool("TEST_BOOL") is False

    def test_get_env_list(self):
        with patch.dict(os.environ, {"TEST_LIST": "a,b,c"}, clear=True):
            assert get_env_list("TEST_LIST") == ["a", "b", "c"]

    def test_get_env_list_empty(self):
        with patch.dict(os.environ, {"TEST_LIST": ""}, clear=True):
            assert get_env_list("TEST_LIST") == []

    def test_get_env_list_spaces(self):
        with patch.dict(os.environ, {"TEST_LIST": "a, b, c "}, clear=True):
            assert get_env_list("TEST_LIST") == ["a", "b", "c"]

    def test_get_env_list_custom_delimiter(self):
        with patch.dict(os.environ, {"TEST_LIST": "a|b|c"}, clear=True):
            assert get_env_list("TEST_LIST", delimiter="|") == ["a", "b", "c"]


class TestLogging:
    @patch("os.environ", {})
    def test_setup_logging(self):
        logger = setup_logging("test_logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"
        assert len(logger.handlers) > 0
        assert all(isinstance(h, logging.Handler) for h in logger.handlers)

    def test_logging_level_from_env(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=True):
            logger = setup_logging("test_debug_logger")
            assert logger.level == logging.DEBUG


class TestCloudflareConfig:
    def test_get_cloudflare_config_with_required_values(self):
        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test_token"}, clear=True):
            config = get_cloudflare_config()
            assert config["api_token"] == "test_token"
            assert "email" in config

    def test_get_cloudflare_config_missing_token(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                get_cloudflare_config()
