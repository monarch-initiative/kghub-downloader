import ftplib
import logging
import os
import sys
from fnmatch import fnmatch
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import boto3
import gdown
import requests
from google.cloud import storage
from google.cloud.storage.blob import Blob
from tqdm.auto import tqdm  # type: ignore

from kghub_downloader.model import DownloadableResource
from kghub_downloader.schemas import register_schema


GOOGLE_DRIVE_PREFIX = "https://drive.google.com/uc?id="


@register_schema("gs")
def google_cloud_storage(item: DownloadableResource,
                         outfile_path: Path, snippet_only: bool) -> None:
    url = item.expanded_url
    Blob.from_string(
        url, client=storage.Client()
    ).download_to_filename(outfile_path.name)


@register_schema("gdrive")
def google_drive(item: DownloadableResource,
                 outfile_path: Path, snippet_only: bool) -> None:
    url = item.expanded_url
    if url.startswith("gdrive:"):
        url = GOOGLE_DRIVE_PREFIX + url[7:]
    gdown.download(url, output=outfile_path.name)


@register_schema("s3")
def s3(item: DownloadableResource, outfile_path: Path,
       snippet_only: bool) -> None:
    url = item.expanded_url
    s3 = boto3.client("s3")
    bucket_name = url.split("/")[2]
    remote_file = "/".join(url.split("/")[3:])
    s3.download_file(bucket_name, remote_file, outfile_path.name)


@register_schema("ftp")
def ftp(item: DownloadableResource, outfile_path: Path,
        snippet_only: bool) -> None:
    url = item.expanded_url

    ftp_username = os.getenv("FTP_USERNAME", None)
    ftp_password = os.getenv("FTP_PASSWORD", "")

    host = url.split("/")[0]
    path = "/".join(url.split("/")[1:])
    ftp = ftplib.FTP(host)

    if ftp_username is None:
        ftp.login()
    else:
        ftp.login(ftp_username, ftp_password)

    download_via_ftp(ftp, path, outfile_path.name, item.glob)


@register_schema("git")
def git(item: DownloadableResource, outfile_path: Path,
        snippet_only: bool) -> None:
    url = item.url
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
        # FIXME: Raise error here rather than exiting
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

    # If no asset found in the specified tag or no tag provided, check other
    # releases
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
        # FIXME: Raise error here rather than exiting
        sys.exit(1)

    # Download the asset
    response = requests.get(asset_url, stream=True)
    response.raise_for_status()
    with open(outfile_path.name, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)
    print(f"Downloaded {asset_name}")


@register_schema("http")
@register_schema("https")
def http(item: DownloadableResource, outfile_path: Path,
         snippet_only: bool) -> None:
    url = item.expanded_url

    if url.startswith(GOOGLE_DRIVE_PREFIX):
        return google_drive(item, outfile_path, snippet_only)

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


def is_directory(ftp_server, name):
    """Check if the given name is a directory on the FTP server."""
    current = ftp_server.pwd()
    try:
        ftp_server.cwd(name)  # Try changing to the directory
        return True
    except ftplib.error_perm:
        return False
    finally:
        ftp_server.cwd(current)  # Always change back to the original directory


def is_matching_filename(filename, glob_pattern):
    """Check if the filename matches the glob pattern."""
    return fnmatch(filename, glob_pattern) if glob_pattern else True


def download_via_ftp(ftp_server, current_dir, local_dir, glob_pattern=None):
    """
    Recursively download files from an FTP server matching the glob pattern.
    """
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
                        ftp_server, item, os.path.join(local_dir, item),
                        glob_pattern
                    )
                    # Go back to the parent directory
                    ftp_server.cwd("..")
                else:
                    # Check if the file matches the pattern
                    if is_matching_filename(item, glob_pattern):
                        # Download the file
                        local_filepath = os.path.join(local_dir, item)
                        os.makedirs(os.path.dirname(local_filepath),
                                    exist_ok=True)
                        with open(local_filepath, "wb") as f:
                            ftp_server.retrbinary(f"RETR {item}", f.write)
                # Update the progress bar after each item is processed
                pbar.update(1)
    except ftplib.error_perm as e:
        # Handle permission errors
        print(f"Permission denied: {e}")
