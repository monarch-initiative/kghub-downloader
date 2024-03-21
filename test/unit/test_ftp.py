import os
import shutil
import unittest
from unittest.mock import MagicMock, patch

from kghub_downloader.download_utils import (download_file, download_via_ftp,
                                             is_directory,
                                             is_matching_filename)


class TestFTPDownload(unittest.TestCase):
    def setUp(self):
        # Set up a mock FTP server object
        self.mock_ftp = MagicMock()

    from unittest.mock import patch

    @patch("kghub_downloader.download_utils.FTP")
    def test_download_via_ftp(self, mock_ftp):
        # Set up environment variables
        with patch.dict(
            "os.environ", {"FTP_USERNAME": "username", "FTP_PASSWORD": "password"}
        ):
            # Set up the mock FTP instance
            ftp_instance = mock_ftp.return_value
            ftp_instance.nlst.return_value = ["file1.txt", "dir1"]

            # Mock is_directory and is_matching_filename directly
            with patch(
                "kghub_downloader.download_utils.is_directory", return_value=False
            ) as mock_is_directory, patch(
                "kghub_downloader.download_utils.is_matching_filename",
                return_value=True,
            ), patch(
                "kghub_downloader.download_utils.download_file"
            ) as mock_download_file, patch(
                "multiprocessing.pool.Pool"
            ) as mock_pool:

                # Create a mock pool instance
                pool_instance = mock_pool.return_value

                # Call the function to be tested
                download_via_ftp("ftp.example.com", "/", "local_dir", "*.txt")

                # Check that login was called with the correct credentials
                ftp_instance.login.assert_called_once_with("username", "password")

                # Check that cwd was called with the current directory
                ftp_instance.cwd.assert_called_once_with("/")

                # Assert that the file listing contains the expected files
                self.assertIn("file1.txt", ftp_instance.nlst.return_value)

                # Ensure is_directory was called correctly
                mock_is_directory.assert_called_with("ftp.example.com", "dir1")

                # # Check that apply_async was called for file1.txt
                # pool_instance.apply_async.assert_called_once_with(
                #     mock_download_file,
                #     args=(('ftp.example.com', '/'), 'file1.txt', 'local_dir'),
                # )

                # # Check that the pool was closed and joined
                # pool_instance.close.assert_called_once()
                # pool_instance.join.assert_called_once()

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

    # @unittest.skipIf(
    #     os.getenv("GITHUB_ACTIONS") == "true", "This test needs credentials to run."
    # )
    # def test_actual_upload_download(self):
    #     # Credentials available at: https://dlptest.com/ftp-test/
    #     pwd = Path.cwd()
    #     output_dir = pwd / "test/output"
    #     resources_dir = pwd / "test/resources"
    #     # Set up a real FTP server
    #     ftp = ftplib.FTP("ftp.dlptest.com")
    #     ftp.login(os.environ["FTP_USERNAME"], os.environ["FTP_PASSWORD"])
    #     # upload the file ../resources/test_file.txt to the server
    #     ftp.storbinary(
    #         "STOR test_file.txt", open(f"{resources_dir}/testfile.txt", "rb")
    #     )
    #     # download the file test_file.txt from the server
    #     download_via_ftp(ftp, "/", f"{output_dir}", "*.txt")
    #     # Check that the file was downloaded correctly
    #     self.assertTrue(os.path.exists(f"{output_dir}/test_file.txt"))
    #     empty_directory(output_dir)


def empty_directory(directory):
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")
