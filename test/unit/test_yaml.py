import unittest
from unittest.mock import patch

from pydantic import ValidationError

from kghub_downloader.download_utils import DownloadableResource


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
            self.assertEqual(resource.expanded_url,
                             "http://example.com/expanded")

    def test_invalid_url_expansion(self):
        with (
            patch.dict("os.environ", clear=True) as environ,
            self.assertRaises(ValueError)
        ):
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
                url="illegal-schema://example.com/",
                tag="tag",
                local_name="local_name",
            )
