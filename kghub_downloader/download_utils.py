import ftplib
import json
import logging
import os
import pathlib
import re
from fnmatch import fnmatch
from ftplib import error_perm
from multiprocessing.sharedctypes import Value
from typing import List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

import boto3
import compress_json  # type: ignore
import elasticsearch
import elasticsearch.helpers
import gdown
import yaml
from botocore.exceptions import NoCredentialsError
from google.cloud import storage
from google.cloud.storage.blob import Blob
from tqdm.auto import tqdm  # type: ignore

# from compress_json import compress_json


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
        glob: Optional glob pattern to limit downloading to
    Returns:
        None.
    """

    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    with open(yaml_file) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
        # Limit to only tagged downloads, if tags are passed in
        if tags:
            data = [
                item
                for item in data
                if "tag" in item and item["tag"] and item["tag"] in tags
            ]

        for item in tqdm(data, desc="Downloading files"):
            if "url" not in item:
                logging.error("Couldn't find url for source in {}".format(item))
                continue
            if snippet_only and (item["local_name"])[-3:] in [
                "zip",
                ".gz",
            ]:  # Can't truncate compressed files
                logging.error(
                    "Asked to download snippets; can't snippet {}".format(item)
                )
                continue

            local_name = (
                item["local_name"]
                if "local_name" in item and item["local_name"]
                else item["url"].split("/")[-1]
            )
            outfile = os.path.join(output_dir, local_name)

            logging.info("Retrieving %s from %s" % (outfile, item["url"]))

            if "local_name" in item:
                local_file_dir = os.path.join(
                    output_dir, os.path.dirname(item["local_name"])
                )
                if not os.path.exists(local_file_dir):
                    logging.info(f"Creating local directory {local_file_dir}")
                    pathlib.Path(local_file_dir).mkdir(parents=True, exist_ok=True)

            if os.path.exists(outfile):
                if ignore_cache:
                    logging.info("Deleting cached version of {}".format(outfile))
                    os.remove(outfile)
                else:
                    logging.info("Using cached version of {}".format(outfile))
                    continue

            # Download file
            if "api" in item:
                download_from_api(item, outfile)
            if "url" in item:
                url = parse_url(item["url"])
                if url.startswith("gs://"):
                    Blob.from_string(url, client=storage.Client()).download_to_filename(
                        outfile
                    )
                elif url.startswith("s3://"):
                    s3 = boto3.client("s3")
                    bucket_name = url.split("/")[2]
                    remote_file = "/".join(url.split("/")[3:])
                    s3.download_file(bucket_name, remote_file, outfile)
                elif url.startswith("ftp"):
                    glob = None
                    if "glob" in item:
                        glob = item["glob"]
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
                    download_via_ftp(ftp, path, outfile, glob)
                elif any(
                    url.startswith(str(i))
                    for i in list(GDOWN_MAP.keys()) + list(GDOWN_MAP.values())
                ):
                    # Check if url starts with a key or a value
                    for key, value in GDOWN_MAP.items():
                        if url.startswith(str(value)):
                            # If value, then download the file directly
                            gdown.download(url, output=outfile)
                            break
                        elif url.startswith(str(key)):
                            # If key, replace key by value and then download
                            new_url = url.replace(str(key) + ":", str(value))
                            gdown.download(new_url, output=outfile)
                            break
                    else:
                        # If the loop completes without breaking (i.e., no match found), throw an error
                        raise ValueError("Invalid URL")
                else:
                    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    try:
                        with urlopen(req) as response, open(outfile, "wb") as out_file:  # type: ignore
                            if snippet_only:
                                data = response.read(
                                    5120
                                )  # first 5 kB of a `bytes` object
                            else:
                                data = response.read()  # a `bytes` object
                            out_file.write(data)
                            if snippet_only:  # Need to clean up the outfile
                                in_file = open(outfile, "r+")
                                in_lines = in_file.read()
                                in_file.close()
                                splitlines = in_lines.split("\n")
                                outstring = "\n".join(splitlines[:-1])
                                cleanfile = open(outfile, "w+")
                                for i in range(len(outstring)):
                                    cleanfile.write(outstring[i])
                                cleanfile.close()
                    except URLError:
                        logging.error(f"Failed to download: {url}")
                        raise

            # If mirror, upload to remote storage
            if mirror:
                mirror_to_bucket(
                    local_file=outfile, bucket_url=mirror, remote_file=local_name
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
    if yaml_item["api"] == "elasticsearch":
        es_conn = elasticsearch.Elasticsearch(hosts=[yaml_item["url"]])
        query_data = compress_json.local_load(
            os.path.join(os.getcwd(), yaml_item["query_file"])
        )
        output = open(outfile, "w")
        records = elastic_search_query(
            es_conn, index=yaml_item["index"], query=query_data
        )
        json.dump(records, output)
        return None
    else:
        raise RuntimeError(f"API {yaml_item['api']} not supported")


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
