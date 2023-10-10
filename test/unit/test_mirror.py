from kghub_downloader.download_utils import *

from unittest import mock

# proper test
@mock.patch("google.cloud.storage.Client")
def test_mirror(client):
    mirror_to_bucket(
        local_file="test/resources/testfile.txt",
        bucket_url="gs://monarch-test/",
        remote_file="kghub_test_upload.txt",
    )

    bucket = client().bucket
    bucket.assert_called_with("monarch-test")

    blob = bucket().blob
    blob.assert_called_with("kghub_test_upload.txt")
