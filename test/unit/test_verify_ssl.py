"""Tests for SSL verification flag functionality."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from kghub_downloader import download, model
from kghub_downloader.model import DownloadOptions


class TestVerifySSL(unittest.TestCase):
    """Tests to verify SSL verification flag is passed correctly to requests."""

    @patch("kghub_downloader.download.requests.get")
    def test_http_verify_ssl_true_by_default(self, mock_get):
        """Test that verify=True is passed by default."""
        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": "100"}
        mock_response.iter_content.return_value = [b"test content"]
        mock_get.return_value = mock_response

        resource = model.DownloadableResource(url="https://example.com/file.txt")
        output_file = Path("/tmp/test_output.txt")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        download.http(resource, output_file, DownloadOptions())

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        self.assertTrue(call_kwargs.get("verify", True))

    @patch("kghub_downloader.download.requests.get")
    def test_http_verify_ssl_false(self, mock_get):
        """Test that verify=False is passed when verify_ssl is False."""
        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": "100"}
        mock_response.iter_content.return_value = [b"test content"]
        mock_get.return_value = mock_response

        resource = model.DownloadableResource(
            url="https://example.com/file.txt",
            verify_ssl=False
        )
        output_file = Path("/tmp/test_output.txt")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        download.http(resource, output_file, DownloadOptions())

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        self.assertFalse(call_kwargs.get("verify"))
