import os
import unittest
from os.path import exists
from pathlib import Path

import pytest

from kghub_downloader import download, model
from kghub_downloader.download_utils import download_from_yaml
from kghub_downloader.model import DownloadOptions

# ruff: noqa: D100, D101, D102

output_files = {
    "https": Path("test/output/zfin/fish_phenotype.txt"),
    "google_cloud_storage": Path("test/output/google_storage_test.yaml"),
    "google_drive_1": Path("test/output/gdrive_test_1.txt"),
    "google_drive_2": Path("test/output/gdrive_test_2.txt"),
    "s3": Path("test/output/s3_test.yaml"),
    "git": Path("test/output/git_test.zip"),
}


class TestDownload(unittest.TestCase):
    def setUp(self):
        for file in output_files.values():
            if file.exists():
                if file.is_dir():
                    import shutil
                    shutil.rmtree(file)
                else:
                    file.unlink()
            if not file.parent.exists():
                file.parent.mkdir(parents=True)

    def _assert_file_exists(self, file_path: Path):
        self.assertTrue(file_path.exists(), f"File {file_path} does not exist")
        self.assertTrue(file_path.stat().st_size > 0, f"File {file_path} is empty")

    def test_http(self):
        resource = model.DownloadableResource(url="https://zfin.org/downloads/phenoGeneCleanData_fish.txt")
        output_file = output_files["https"]
        download.http(resource, output_file, DownloadOptions())
        self._assert_file_exists(output_file)

    @unittest.skipIf(not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"), "Google Cloud credentials not available")
    def test_google_cloud_storage(self):
        resource = model.DownloadableResource(url="gs://monarch-test/kghub_downloader_test_file.yaml")
        output_file = output_files["google_cloud_storage"]
        download.google_cloud_storage(resource, output_file, DownloadOptions())
        self._assert_file_exists(output_file)

    def test_google_drive(self):
        resource = model.DownloadableResource(url="gdrive:10ojJffrPSl12OMcu4gyx0fak2CNu6qOs")
        output_file = output_files["google_drive_1"]
        download.google_drive(resource, output_file, DownloadOptions())
        self._assert_file_exists(output_file)

    @pytest.mark.usefixtures('mock_s3_test_file')
    def test_s3(self):
        resource = model.DownloadableResource(url="s3://monarch-test/kghub_downloader_test_file.yaml")
        output_file = output_files["s3"]
        download.s3(resource, output_file, DownloadOptions())
        self._assert_file_exists(output_file)

    def test_git(self):
        resource = model.DownloadableResource(url="git://Knowledge-Graph-Hub/kg-microbe/testfile.zip")
        output_file = output_files["git"]
        download.git(resource, output_file, DownloadOptions())
        self._assert_file_exists(output_file)

    @pytest.mark.usefixtures('mock_s3_test_file')
    @unittest.skipIf(not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"), "Google Cloud credentials not available")
    def test_yaml_spec_download(self):
        download_from_yaml(yaml_file="example/download.yaml", output_dir="test/output")
        for file in output_files.values():
            self._assert_file_exists(file)

    def test_tag(self):
        files = ["test/output/zfin/fish_phenotype.txt", "test/output/test_file.yaml"]
        tagged_files = ["test/output/gdrive_test_1.txt"]

        for file in files:
            if exists(file):
                os.remove(file)

        download_from_yaml(yaml_file="example/download.yaml", output_dir="test/output", tags=["testing"])

        for file in tagged_files:
            self._assert_file_exists(Path(file))

        for file in files:
            if file not in tagged_files:
                self.assertFalse(os.path.exists(file))
