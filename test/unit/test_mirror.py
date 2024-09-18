from unittest import mock

from kghub_downloader.upload import mirror_to_bucket

# ruff: noqa: D100, D103


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


def test_mirror_to_bucket_s3(mock_empty_bucket):
    result = mirror_to_bucket(
        local_file="test/resources/testfile.txt",
        bucket_url="s3://monarch-test/",
        remote_file="kghub_test_upload.txt",
    )

    # Check if the file was created in the bucket
    bucket = mock_empty_bucket.Bucket("monarch-test")
    files_in_bucket = list(bucket.objects.all())
    assert len(files_in_bucket) == 1
    assert files_in_bucket[0].key == "kghub_test_upload.txt"
    assert result is True
