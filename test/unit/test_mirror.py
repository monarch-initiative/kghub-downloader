import os
from unittest import mock

import boto3
import moto
import pytest

from kghub_downloader.download_utils import mirror_to_bucket


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


@pytest.fixture(scope="session")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture(scope="function")
def empty_bucket(aws_credentials):
    moto_fake = moto.mock_aws()
    try:
        moto_fake.start()
        conn = boto3.resource("s3")
        conn.create_bucket(Bucket="monarch-test")  # or the name of the bucket you use
        yield conn
    finally:
        moto_fake.stop()


def test_mirror_to_bucket_s3(empty_bucket):
    # Call the function under test
    result = mirror_to_bucket(
        local_file="test/resources/testfile.txt",
        bucket_url="s3://monarch-test/",
        remote_file="kghub_test_upload.txt",
    )

    # Check if the file was created in the bucket
    bucket = empty_bucket.Bucket("monarch-test")
    files_in_bucket = list(bucket.objects.all())
    assert len(files_in_bucket) == 1
    assert files_in_bucket[0].key == "kghub_test_upload.txt"
    assert result is True
