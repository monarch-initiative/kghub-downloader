import unittest
from unittest.mock import patch

from pydantic import ValidationError

from kghub_downloader.model import DownloadableResource


class TestYAMLValidate(unittest.TestCase):
    def test_valid_url(self):
        resource = DownloadableResource(
            url="http://example.com/",
            tag="tag",
            local_name="local_name",
        )
        self.assertEqual(resource.url, "http://example.com/")

    def test_url_expansion(self):
        with patch.dict("os.environ", {"ENVVAR": "expanded"}, clear=True):
            resource = DownloadableResource(
                url="http://example.com/{ENVVAR}",
                tag="tag",
                local_name="local_name",
            )
            self.assertEqual(resource.expanded_url, "http://example.com/expanded")

    def test_invalid_url_expansion(self):
        with patch.dict("os.environ", clear=True) as environ, self.assertRaises(ValueError):
            if "ENVVAR" in environ:
                del environ["ENVVAR"]
            resource = DownloadableResource(
                url="http://example.com/{ENVVAR}",
                tag="tag",
                local_name="local_name",
            )
            resource.expanded_url

    def test_invalid_url(self):
        with self.assertRaises(ValidationError):
            DownloadableResource(
                url="illegal-scheme://example.com/",
                tag="tag",
                local_name="local_name",
            )

    def test_index_url_scheme(self):
        resource = DownloadableResource(
            url="index://test",
            index_url="https://example.com/index.json",
            url_pattern="https://example.com/files/{ID}.yaml",
            local_name="test_files"
        )
        self.assertEqual(resource.url, "index://test")
        self.assertEqual(resource.index_url, "https://example.com/index.json")
        self.assertEqual(resource.url_pattern, "https://example.com/files/{ID}.yaml")

    def test_verify_ssl_default_true(self):
        resource = DownloadableResource(
            url="http://example.com/",
        )
        self.assertTrue(resource.verify_ssl)

    def test_verify_ssl_can_be_disabled(self):
        resource = DownloadableResource(
            url="http://example.com/",
            verify_ssl=False,
        )
        self.assertFalse(resource.verify_ssl)
