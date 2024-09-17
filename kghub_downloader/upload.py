"""Functions for uploading resources to a mirror."""

from pathlib import Path
from typing import Optional

import boto3  # type: ignore
from botocore.exceptions import NoCredentialsError  # type: ignore
from google.cloud import storage  # type: ignore


def mirror_to_bucket(local_file: Path, bucket_url: str, remote_file: Path) -> Optional[bool]:
    """Mirror a local file to an S3 bucket."""
    bucket_split = bucket_url.split("/")
    bucket_name = bucket_split[2]
    with open(local_file, "rb"):
        if bucket_url.startswith("gs://"):

            # Remove any trailing slashes (Google gets confused)
            bucket_url = bucket_url.rstrip("/")

            # Connect to GCS Bucket
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)

            # Upload blob from local file
            if len(bucket_split) > 3:
                bucket_path = "/".join(bucket_split[3:])
            else:
                bucket_path = None

            print(f"Bucket name: {bucket_name}")
            print(f"Bucket filepath: {bucket_path}")

            blob = bucket.blob(f"{bucket_path}/{remote_file}") if bucket_path else bucket.blob(remote_file)

            print(f"Uploading {local_file} to remote mirror: " "gs://{blob.name}/")
            blob.upload_from_filename(local_file)

        elif bucket_url.startswith("s3://"):
            # Create an S3 client
            s3 = boto3.client("s3")

            try:
                # Upload the file
                # ! This will only work if the user has the AWS IAM user
                # ! access keys set up as environment variables.
                s3.upload_file(local_file, bucket_name, remote_file)
                print(f"File {local_file} uploaded to " "{bucket_name}/{remote_file}")
                return True
            except FileNotFoundError:
                print(f"The file {local_file} was not found")
                return False
            except NoCredentialsError:
                print("Credentials not available")
                return False

        else:
            raise ValueError("Currently, only Google Cloud and S3 storage is supported.")

    return None
