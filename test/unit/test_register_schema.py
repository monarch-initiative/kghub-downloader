import unittest
from pathlib import Path

from kghub_downloader import model, schemes


class TestSchemeRegister(unittest.TestCase):
    def test_register_scheme(self):
        registry = {}

        @schemes.register_scheme("ex", registry)
        def downloader(item: model.DownloadableResource, path: Path, snippet_only: bool) -> None:
            return

        self.assertEqual(list(registry.keys()), ["ex"])
