from kghub_downloader.download_utils import *

from unittest import mock

# proper test
@mock.patch("google.cloud.storage.Client")
def test_mirror(client):
    mirror_to_bucket(
               local_file='test/resources/testfile.txt',
               bucket_url='gs://test-monarch-output/',
               remote_file='test/test.txt'
          )

    bucket = client().bucket
    bucket.assert_called_with("test-monarch-output")

    blob = bucket().blob
    blob.assert_called_with("test/test.txt")
