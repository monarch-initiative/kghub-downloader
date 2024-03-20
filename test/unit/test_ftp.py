import ftplib
import os
import unittest
from ftplib import error_perm
from pathlib import Path
from unittest.mock import MagicMock, patch

from kghub_downloader.download_utils import (
    download_via_ftp,
    is_directory,
    is_matching_filename,
)


class TestFTPDownload(unittest.TestCase):
    def setUp(self):
        # Set up a mock FTP server object
        self.mock_ftp = MagicMock()

    @patch("ftplib.FTP")  # Mock the FTP class
    def test_download_files(self, mock_ftp):
        # Set up the mock FTP instance
        ftp_instance = mock_ftp.return_value
        ftp_instance.nlst.side_effect = [
            ["file1.txt", "dir1"],  # Root directory listing
            ["file2.txt", "file3.txt"],  # dir1 directory listing
        ]
        ftp_instance.pwd.side_effect = ["/", "/dir1"]
        ftp_instance.cwd.side_effect = lambda x: x

        # Mock is_directory to return True for directories and False for files
        with patch(
            "kghub_downloader.download_utils.is_directory",
            side_effect=lambda ftp, name: name == "dir1",
        ):
            # Mock os.makedirs to prevent actual directory creation
            with patch("os.makedirs") as makedirs_mock:
                # Mock open to prevent actual file writing
                with patch(
                    "builtins.open", new_callable=unittest.mock.mock_open()
                ) as mock_file:
                    # Call the function to be tested
                    download_via_ftp(ftp_instance, "/", "local_dir", "*.txt")

                    # Check that makedirs was called for the local directory structure
                    makedirs_mock.assert_called_with("local_dir/dir1", exist_ok=True)

                    # Check that the file was opened for writing
                    mock_file.assert_any_call("local_dir/file1.txt", "wb")
                    mock_file.assert_any_call("local_dir/dir1/file2.txt", "wb")
                    mock_file.assert_any_call("local_dir/dir1/file3.txt", "wb")

                    # Check that the correct number of files were attempted to be downloaded
                    self.assertEqual(mock_file.call_count, 3)

    def test_is_directory_true(self):
        # Mock the pwd and cwd methods for a directory
        self.mock_ftp.pwd.return_value = "/"
        self.mock_ftp.cwd.side_effect = lambda x: x

        # Assert that is_directory returns True for a directory
        self.assertTrue(is_directory(self.mock_ftp, "some_directory"))

    def test_is_matching_filename(self):
        # Test with matching pattern
        self.assertTrue(is_matching_filename("file.txt", "*.txt"))

        # Test with non-matching pattern
        self.assertFalse(is_matching_filename("file.jpg", "*.txt"))

        # Test with no pattern provided (should always return True)
        self.assertTrue(is_matching_filename("file.jpg", None))

    @unittest.skipIf(
        os.getenv("GITHUB_ACTIONS") == "true", "This test needs credentials to run."
    )
    def test_actual_upload_download(self):
        # Credentials available at: https://dlptest.com/ftp-test/
        pwd = Path.cwd()
        output_dir = pwd / "test/output"
        resources_dir = pwd / "test/resources"
        # Set up a real FTP server
        ftp = ftplib.FTP("ftp.dlptest.com")
        ftp.login(os.environ["FTP_USERNAME"], os.environ["FTP_PASSWORD"])
        # upload the file ../resources/test_file.txt to the server
        ftp.storbinary(
            "STOR test_file.txt", open(f"{resources_dir}/testfile.txt", "rb")
        )
        # download the file test_file.txt from the server
        download_via_ftp(ftp, "/", f"{output_dir}", "*.txt")
        # Check that the file was downloaded correctly
        self.assertTrue(os.path.exists(f"{output_dir}/test_file.txt"))
        os.remove(f"{output_dir}/test_file.txt")
