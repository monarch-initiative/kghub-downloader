import unittest
from pathlib import Path

from kghub_downloader import schemas, model


class TestSchemaRegister(unittest.TestCase):
    def test_register_schema(self):
        registry = {}

        @schemas.register_schema("ex", registry)
        def downloader(
            item: model.DownloadableResource,
            path: Path,
            snippet_only: bool
        ) -> None:
            return

        self.assertEqual(list(registry.keys()), ["ex"])
