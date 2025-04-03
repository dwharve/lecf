"""Test configuration file for pytest."""

import sys
from unittest.mock import MagicMock

# Create a mock cloudflare module
mock_cloudflare = MagicMock()
mock_cloudflare.Client = MagicMock()
mock_cloudflare.Cloudflare = mock_cloudflare.Client  # Alias as in the real module
mock_cloudflare.exceptions = MagicMock()
mock_cloudflare.exceptions.CloudFlareAPIError = Exception

# Mock the types module
mock_cloudflare.types = MagicMock()

# Add the mock to sys.modules
sys.modules["cloudflare"] = mock_cloudflare
