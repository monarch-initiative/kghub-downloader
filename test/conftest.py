"""Fixtures for s3."""

import os

import boto3  # type: ignore
import moto
import pytest


@pytest.fixture(scope="function")
def mock_aws_credentials():
    """Fixture to mock AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"  # noqa: S105
    os.environ["AWS_SECURITY_TOKEN"] = "testing"  # noqa: S105
    os.environ["AWS_SESSION_TOKEN"] = "testing"  # noqa: S105
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture(scope="function")
def mock_empty_bucket(mock_aws_credentials):
    """Fixture to mock an empty AWS bucket."""
    moto_fake = moto.mock_aws()
    try:
        moto_fake.start()
        conn = boto3.resource("s3")
        conn.create_bucket(Bucket="monarch-test")  # or the name of the bucket you use
        yield conn
    finally:
        moto_fake.stop()

@pytest.fixture(scope="function")
def mock_s3_test_file(mock_empty_bucket):
    """Fixture to populate the mock S3 bucket with a test file."""
    s3 = boto3.client("s3")
    s3.put_object(Body="test data", Bucket="monarch-test", Key="kghub_downloader_test_file.yaml")
    yield
    s3.delete_object(Bucket="monarch-test", Key="kghub_downloader_test_file.yaml")
