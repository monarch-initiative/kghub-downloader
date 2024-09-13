import ftplib
import json
import logging
import os
import pathlib
import re
from fnmatch import fnmatch
from ftplib import error_perm
from multiprocessing.sharedctypes import Value
import sys
from typing import List, Optional, Literal, Union
from urllib.error import URLError
from urllib.request import Request, urlopen

import boto3
import compress_json  # type: ignore
import elasticsearch
import elasticsearch.helpers
import gdown
import requests
import yaml
from botocore.exceptions import NoCredentialsError
from google.cloud import storage
from google.cloud.storage.blob import Blob
from pydantic import BaseModel, Field, FilePath
from tqdm.auto import tqdm  # type: ignore

# from compress_json import compress_json

valid_url_schemas = [
    "http",
    "gs",
    "gdrive",  # FIXME: document
    "git",
    "s3",
    "ftp",
]

URLSchemaField = Field(
    pattern=r"^" + '|'.join(valid_url_schemas)
)


class DownloadableResource(BaseModel):
    url: str = Field(
        pattern=r"^" + '|'.join(valid_url_schemas)
    )
    api: Optional[Union[Literal['elasticsearch']]] = None
    tag: Optional[str] = None
    local_name: Optional[str] = None
    glob: Optional[str] = None

    # ElasticSearch parameters. Should probably be split into a nested config.
    query_file: Optional[FilePath] = None
    index: Optional[str] = None

    @property
    def path(self) -> pathlib.Path:
        filename = self.local_name or self.url.split("/")[-1]
        return pathlib.Path(filename)

    @property
    def is_compressed_file(self):
        return self.path.suffix in ["zip", "gz"]

    @property
    def expanded_url(self) -> str:
        """Parses a URL for any environment variables enclosed in {curly braces}"""
        pattern = r".*?\{(.*?)\}"
        url = self.url
        match = re.findall(pattern, url)
        for i in match:
            secret = os.getenv(i)
            if secret is None:
                raise ValueError(
                    f"Environment Variable: {i} is not set. Please set the variable using export or similar, and try again."
                )
            url = url.replace("{" + i + "}", secret)
        return url


GDOWN_MAP = {"gdrive": "https://drive.google.com/uc?id="}


def download_from_yaml(
    yaml_file: str,
    output_dir: str,
    ignore_cache: Optional[bool] = False,
    snippet_only: Optional[bool] = False,
    tags: Optional[List] = None,
    mirror: Optional[str] = None,
) -> None:
    """Download files listed in a download.yaml file

    Args:
        yaml_file: A string pointing to the download.yaml file, to be parsed for things to download.
        output_dir: A string pointing to where to write out downloaded files.
        ignore_cache: Ignore cache and download files even if they exist [false]
        snippet_only: Downloads only the first 5 kB of each uncompressed source, for testing and file checks
        tags: Limit to only downloads with this tag
        mirror: Optional remote storage URL to mirror download to. Supported buckets: Google Cloud Storage
    Returns:
        None.
    """

    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)

    with open(yaml_file) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    resources: List[DownloadableResource] = [
        DownloadableResource(**x) for x in data
    ]

    # Limit to only tagged downloads, if tags are passed in
    if tags:
        resources = [item for item in resources if item.tag in tags]

    for item in tqdm(resources, desc="Downloading files"):
        url = item.expanded_url
        outfile_path = output_dir / item.path
        outfile_dir = outfile_path.parent

        logging.info("Retrieving %s from %s" % (item.path, url))

        # Can't truncate compressed file
        if snippet_only and item.is_compressed_file:
            logging.error(
                "Asked to download snippets; can't snippet {}".format(item)
            )
            continue

        if not outfile_dir.exists():
            logging.info(f"Creating local directory {outfile_dir}")
            outfile_dir.mkdir(parents=True, exist_ok=True)

        if outfile_path.exists():
            if ignore_cache:
                logging.info(f"Deleting cached version of {outfile_path}")
                outfile_path.remove()
            else:
                logging.info("Using cached version of {outfile_path")
                continue

        # Download file
        if item.api is not None:
            download_from_api(item, outfile_path.name)
            continue

        # Can remove this if block, but I will do it in a further commit for a
        # clean diff
        if url:
            if url.startswith("gs://"):
                Blob.from_string(url, client=storage.Client()).download_to_filename(
                    outfile_path.name
                )
            elif url.startswith("s3://"):
                s3 = boto3.client("s3")
                bucket_name = url.split("/")[2]
                remote_file = "/".join(url.split("/")[3:])
                s3.download_file(bucket_name, remote_file, outfile_path.name)
            elif url.startswith("ftp"):
                ftp_username = (
                    os.getenv("FTP_USERNAME") if os.getenv("FTP_USERNAME") else None
                )
                ftp_password = (
                    os.getenv("FTP_PASSWORD") if os.getenv("FTP_PASSWORD") else None
                )
                host = url.split("/")[0]
                path = "/".join(url.split("/")[1:])
                ftp = ftplib.FTP(host)
                ftp.login(ftp_username, ftp_password)
                download_via_ftp(ftp, path, outfile_path.name, item.glob)
            elif any(
                url.startswith(str(i))
                for i in list(GDOWN_MAP.keys()) + list(GDOWN_MAP.values())
            ):
                # Check if url starts with a key or a value
                for key, value in GDOWN_MAP.items():
                    if url.startswith(str(value)):
                        # If value, then download the file directly
                        gdown.download(url, output=outfile_path.name)
                        break
                    elif url.startswith(str(key)):
                        # If key, replace key by value and then download
                        new_url = url.replace(str(key) + ":", str(value))
                        gdown.download(new_url, output=outfile_path.name)
                        break
                else:
                    # If the loop completes without breaking (i.e., no match found), throw an error
                    raise ValueError("Invalid URL")
            elif url.startswith("git://"):
                url_split = url.split("/")
                repo_owner = url_split[-3]
                repo_name = url_split[-2]
                asset_name = url_split[-1]
                asset_url = None
                api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
                # Get the list of releases
                response = requests.get(api_url)
                response.raise_for_status()
                releases = response.json()

                if not releases:
                    print("No releases found for this repository.")
                    sys.exit(1)

                # Check if a specific tag is provided
                if item.tag is not None:
                    # Find the release with the specified tag
                    tagged_release = next(
                        (
                            release
                            for release in releases
                            if release["tag_name"] == item.tag
                        ),
                        None,
                    )
                    if tagged_release:
                        for asset in tagged_release.get("assets", []):
                            if asset["name"] == asset_name:
                                asset_url = asset["browser_download_url"]
                                break

                # If no asset found in the specified tag or no tag provided, check other releases
                if not asset_url:
                    for release in releases:
                        for asset in release.get("assets", []):
                            if asset["name"] == asset_name:
                                asset_url = asset["browser_download_url"]
                                break
                        if asset_url:
                            break

                if not asset_url:
                    print(f"Asset '{asset_name}' not found in any release.")
                    sys.exit(1)

                # Download the asset
                response = requests.get(asset_url, stream=True)
                response.raise_for_status()
                with open(outfile_path.name, "wb") as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                print(f"Downloaded {asset_name}")

            else:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                try:
                    with urlopen(req) as response:  # type: ignore
                        if snippet_only:
                            data = response.read(
                                5120
                            )  # first 5 kB of a `bytes` object
                        else:
                            data = response.read()  # a `bytes` object

                    with open(outfile_path.name, "wb") as out_file:
                        out_file.write(data)
                    if snippet_only:  # Need to clean up the outfile
                        in_file = open(outfile_path.name, "r+")
                        in_lines = in_file.read()
                        in_file.close()
                        splitlines = in_lines.split("\n")
                        outstring = "\n".join(splitlines[:-1])
                        cleanfile = open(outfile_path.name, "w+")
                        for i in range(len(outstring)):
                            cleanfile.write(outstring[i])
                        cleanfile.close()
                except URLError:
                    logging.error(f"Failed to download: {url}")
                    raise

        # If mirror, upload to remote storage
        if mirror:
            mirror_to_bucket(
                local_file=outfile_path.name, bucket_url=mirror, remote_file=item.path.name
            )

    return None


def mirror_to_bucket(local_file, bucket_url, remote_file) -> None:
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

            blob = (
                bucket.blob(f"{bucket_path}/{remote_file}")
                if bucket_path
                else bucket.blob(remote_file)
            )

            print(f"Uploading {local_file} to remote mirror: gs://{blob.name}/")
            blob.upload_from_filename(local_file)

        elif bucket_url.startswith("s3://"):
            # Create an S3 client
            s3 = boto3.client("s3")

            try:
                # Upload the file
                # ! This will only work if the user has the AWS IAM user
                # ! access keys set up as environment variables.
                s3.upload_file(local_file, bucket_name, remote_file)
                print(f"File {local_file} uploaded to {bucket_name}/{remote_file}")
                return True
            except FileNotFoundError:
                print(f"The file {local_file} was not found")
                return False
            except NoCredentialsError:
                print("Credentials not available")
                return False

        else:
            raise ValueError(
                "Currently, only Google Cloud and S3 storage is supported."
            )

    return None


def download_from_api(yaml_item, outfile) -> None:
    """

    Args:
        yaml_item: item to be download, parsed from yaml
        outfile: where to write out file

    Returns:

    """
    if yaml_item.api == "elasticsearch":
        es_conn = elasticsearch.Elasticsearch(hosts=[yaml_item.url])
        # FIXME: Validate query file and index parameters exist
        query_data = compress_json.local_load(
            os.path.join(os.getcwd(), yaml_item.query_file)
        )
        records = elastic_search_query(
            es_conn, index=yaml_item.index, query=query_data
        )
        with open(outfile, "w") as output:
            json.dump(records, output)
        return None
    else:
        raise RuntimeError(f"API {yaml_item.api} not supported")


def elastic_search_query(
    es_connection,
    index,
    query,
    scroll: str = "1m",
    request_timeout: int = 60,
    preserve_order: bool = True,
):
    """Fetch records from the given URL and query parameters.

    Args:
        es_connection: elastic search connection
        index: the elastic search index for query
        query: query
        scroll: scroll parameter passed to elastic search
        request_timeout: timeout parameter passed to elastic search
        preserve_order: preserve order param passed to elastic search
    Returns:
        All records for query
    """
    records = []
    results = elasticsearch.helpers.scan(
        client=es_connection,
        index=index,
        scroll=scroll,
        request_timeout=request_timeout,
        preserve_order=preserve_order,
        query=query,
    )

    for item in tqdm(results, desc="querying for index: " + index):
        records.append(item)

    return records


def parse_url(url: str):
    """Parses a URL for any environment variables enclosed in {curly braces}"""
    pattern = r".*?\{(.*?)\}"
    match = re.findall(pattern, url)
    for i in match:
        secret = os.getenv(i)
        if secret is None:
            raise ValueError(
                f"Environment Variable: {i} is not set. Please set the variable using export or similar, and try again."
            )
        url = url.replace("{" + i + "}", secret)
    return url


def download_via_ftp(ftp_server, current_dir, local_dir, glob_pattern=None):
    """Recursively download files from an FTP server matching the glob pattern."""
    try:
        # Change to the current directory on the FTP server
        ftp_server.cwd(current_dir)

        # List items in the current directory
        items = ftp_server.nlst()

        # Initialize tqdm progress bar
        with tqdm(
            total=len(items), desc=f"Downloading from {current_dir} via ftp"
        ) as pbar:
            for item in items:
                # Check if the item is a directory
                if is_directory(ftp_server, item):
                    # Recursively download from the found directory
                    download_via_ftp(
                        ftp_server, item, os.path.join(local_dir, item), glob_pattern
                    )
                    # Go back to the parent directory
                    ftp_server.cwd("..")
                else:
                    # Check if the file matches the pattern
                    if is_matching_filename(item, glob_pattern):
                        # Download the file
                        local_filepath = os.path.join(local_dir, item)
                        os.makedirs(os.path.dirname(local_filepath), exist_ok=True)
                        with open(local_filepath, "wb") as f:
                            ftp_server.retrbinary(f"RETR {item}", f.write)
                # Update the progress bar after each item is processed
                pbar.update(1)
    except error_perm as e:
        # Handle permission errors
        print(f"Permission denied: {e}")


def is_directory(ftp_server, name):
    """Check if the given name is a directory on the FTP server."""
    current = ftp_server.pwd()
    try:
        ftp_server.cwd(name)  # Try changing to the directory
        return True
    except error_perm:
        return False
    finally:
        ftp_server.cwd(current)  # Always change back to the original directory


def is_matching_filename(filename, glob_pattern):
    """Check if the filename matches the glob pattern."""
    return fnmatch(filename, glob_pattern) if glob_pattern else True
