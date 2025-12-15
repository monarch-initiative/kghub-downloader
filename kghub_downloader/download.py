"""
Downloader functions for URI schemes.

A URI scheme is anything before the first
colon in a URI. The scheme for http://example.com/ is "http". The scheme for
newprotocol:a:b/c/d is "newprotocol".

To register a new scheme, use the "@register_scheme" decorator on a new
function. That function will be called for that scheme with three arguments:
    1. The resource to be downloaded (defined in model.py)
    2. A Path object representing where the downloaded file should go
    3. Whether only a snippet should be downloaded
"""

import ftplib
import json
import os
import sys
from contextlib import contextmanager, nullcontext
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Union

import boto3  # type: ignore
import gdown  # type: ignore
import requests
from google.cloud import storage  # type: ignore
from google.cloud.storage.blob import Blob  # type: ignore
from tqdm import tqdm

from kghub_downloader.model import DownloadableResource, DownloadOptions
from kghub_downloader.schemes import register_scheme

GOOGLE_DRIVE_PREFIX = "https://drive.google.com/uc?id="

SNIPPET_SIZE = 1024 * 5
CHUNK_SIZE = 1024
DEFAULT_USER_AGENT = "Mozilla/5.0"
DEFAULT_TIMEOUT = 10


def log_result(fn):
    """Log the result of a download function."""

    def wrapped(item: DownloadableResource, *args, **kwargs):
        try:
            ret = fn(item, *args, **kwargs)
            tqdm.write(f"OK: Downloaded {item.expanded_url}")
            return ret
        except BaseException as e:
            tqdm.write(f"ERROR: Failed to download {item.expanded_url}")
            raise e

    return wrapped


@contextmanager
def open_with_write_progress(
    item: DownloadableResource,
    outfile_path: Path,
    show_progress: bool,
    size: int = 0,
    open_mode: str = "wb"
):
    """Open the given file and wrap its write method in a tqdm progress bar."""
    outfile_fd = outfile_path.open(open_mode)
    try:
        if show_progress:
            with tqdm.wrapattr(
                outfile_fd,
                "write",
                desc=f"{item.expanded_url}",
                total=size,
                leave=False,
                unit="B",
                unit_scale=True,
            ) as file:
                yield file
        else:
            yield outfile_fd
    finally:
        outfile_fd.close()


@register_scheme("gs")
@log_result
def google_cloud_storage(item: DownloadableResource, outfile_path: Path, options: DownloadOptions) -> None:
    """Download from Google Cloud Storage."""
    url = item.expanded_url
    blob = Blob.from_string(url, client=storage.Client())
    with open_with_write_progress(item, outfile_path, options.progress, blob.size) as outfile:
        blob.download_to_file(outfile)


@register_scheme("gdrive")
@log_result
def google_drive(item: DownloadableResource, outfile_path: Path, options: DownloadOptions) -> None:
    """Download from Google Drive."""
    url = item.expanded_url
    url = GOOGLE_DRIVE_PREFIX + url[7:]
    gdown.download(url, output=str(outfile_path))


@register_scheme("s3")
@log_result
def s3(item: DownloadableResource, outfile_path: Path, options: DownloadOptions) -> None:
    """Download from S3 bucket."""
    url = item.expanded_url
    s3 = boto3.resource("s3")
    bucket_name = url.split("/")[2]
    remote_file = "/".join(url.split("/")[3:])

    s3_object = s3.Object(bucket_name, remote_file)
    object_size = s3_object.content_length

    with open_with_write_progress(item, outfile_path, options.progress, object_size) as outfile:
        s3_object.download_fileobj(outfile)


@register_scheme("ftp")
@log_result
def ftp(item: DownloadableResource, outfile_path: Path, options: DownloadOptions) -> None:
    """Download from an FTP server."""
    url = item.expanded_url

    ftp_username = os.getenv("FTP_USERNAME", None)
    ftp_password = os.getenv("FTP_PASSWORD", "")

    host = url.split("/")[0]
    path = "/".join(url.split("/")[1:])

    ftp = ftplib.FTP(host)  # noqa:S321

    if ftp_username is None:
        ftp.login()
    else:
        ftp.login(ftp_username, ftp_password)

    download_via_ftp(ftp, path, str(outfile_path), item.glob)


@register_scheme("git")
@log_result
def git(item: DownloadableResource, outfile_path: Path, options: DownloadOptions) -> None:
    """Download from Git."""
    url = item.url
    url_split = url.split("/")
    repo_owner = url_split[-3]
    repo_name = url_split[-2]
    asset_name = url_split[-1]
    asset_url = None
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
    # Get the list of releases
    response = requests.get(api_url, timeout=10)
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
            (release for release in releases if release["tag_name"] == item.tag),
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
    response = requests.get(asset_url, stream=True, timeout=10)
    response.raise_for_status()
    size = int(response.headers.get("Content-Length", 0))
    with open_with_write_progress(item, outfile_path, options.progress, size) as outfile:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            outfile.write(chunk)


@register_scheme("http")
@register_scheme("https")
@log_result
def http(item: DownloadableResource, outfile_path: Path, options: DownloadOptions) -> None:
    """Download via HTTP. Google Drive URLs will be downloaded specially."""
    url = item.expanded_url

    if url.startswith(GOOGLE_DRIVE_PREFIX):
        gdown.download(url, output=str(outfile_path))
        return

    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=10, verify=item.verify_ssl)
    response.raise_for_status()

    size = int(response.headers.get("Content-Length", 0))
    if options.snippet_only and size > SNIPPET_SIZE:
        size = SNIPPET_SIZE

    with open_with_write_progress(item, outfile_path, options.progress, size) as outfile:
        size = 0
        for chunk in response.iter_content(CHUNK_SIZE):
            outfile.write(chunk)
            if options.snippet_only:
                size += CHUNK_SIZE
                if size >= SNIPPET_SIZE:
                    response.close()
                    break

    # Remove last line from output if snippet was downloaded
    if options.snippet_only:
        with open(str(outfile_path), "r+") as fd:
            data = fd.readlines()
            fd.seek(0)
            fd.write("\n".join(data[:-1]))
            fd.truncate()


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
    """Recursively download files from an FTP server matching the glob pattern."""
    try:
        # Change to the current directory on the FTP server
        ftp_server.cwd(current_dir)

        # List items in the current directory
        items = ftp_server.nlst()

        # Initialize tqdm progress bar
        with tqdm(total=len(items), desc=f"Downloading from {current_dir} via ftp") as pbar:
            for item in items:
                # Check if the item is a directory
                if is_directory(ftp_server, item):
                    # Recursively download from the found directory
                    download_via_ftp(ftp_server, item, os.path.join(local_dir, item), glob_pattern)
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
    except ftplib.error_perm as e:
        # Handle permission errors
        print(f"Permission denied: {e}")


def _extract_ids_from_list(data_list: List[Any]) -> List[str]:
    """Helper to extract IDs from a list."""
    return [str(item) for item in data_list]


def _extract_ids_from_dict(data_dict: Dict[str, Any]) -> List[str]:
    """Helper to extract IDs from a dict where values are lists."""
    all_ids = []
    for value in data_dict.values():
        if isinstance(value, list):
            all_ids.extend(_extract_ids_from_list(value))
    return all_ids


def _traverse_json_path(data: Union[Dict[str, Any], List[Any]], parts: List[str]) -> Any:
    """Helper to traverse JSON data using a list of path parts."""
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, dict):
            # If part not found, try to extract from nested dicts/lists
            all_ids = []
            for key, value in current.items():
                if isinstance(value, list):
                    all_ids.extend(_extract_ids_from_list(value))
                elif isinstance(value, dict) and part in value:
                    if isinstance(value[part], list):
                        all_ids.extend(_extract_ids_from_list(value[part]))
                    else:
                        all_ids.append(str(value[part]))
            return all_ids
        else:
            return []
    return current


def extract_ids_from_json(data: Union[Dict[str, Any], List[Any]], id_path: str) -> List[str]:
    """
    Extract IDs from JSON data using a simplified JSONPath-like notation.
    
    This function supports extracting identifiers from various JSON structures:
    - Flat arrays: ["id1", "id2", "id3"]
    - Objects with arrays: {"source1": ["id1", "id2"], "source2": ["id3"]}
    - Nested structures with dot notation paths
    
    Args:
        data: The JSON data (dict or list) to extract IDs from
        id_path: Optional dot-separated path to navigate nested structures.
                If empty, extracts all IDs from arrays in the top level.
                
    Returns:
        List of string identifiers extracted from the JSON data
        
    Examples:
        >>> extract_ids_from_json(["a", "b", "c"], "")
        ["a", "b", "c"]
        
        >>> extract_ids_from_json({"src1": ["a", "b"], "src2": ["c"]}, "")
        ["a", "b", "c"]
        
        >>> extract_ids_from_json({"results": {"models": ["x", "y"]}}, "results.models")
        ["x", "y"]
    """
    if not id_path:
        if isinstance(data, list):
            return _extract_ids_from_list(data)
        elif isinstance(data, dict):
            return _extract_ids_from_dict(data)
        else:
            return [str(data)]

    parts = id_path.split(".")
    current = _traverse_json_path(data, parts)

    if isinstance(current, list):
        return _extract_ids_from_list(current)
    elif isinstance(current, dict):
        return _extract_ids_from_dict(current)
    elif isinstance(current, str):
        return [current]
    elif current is not None:
        return [str(current)]
    else:
        return []


@register_scheme("index")
@log_result
def index_based_download(item: DownloadableResource, outfile_path: Path, options: DownloadOptions) -> None:
    """
    Download multiple files based on an index URL containing identifiers and a URL pattern template.
    
    This function fetches a JSON index file, extracts identifiers from it, and downloads individual
    files using a URL pattern template where {ID} is replaced with each identifier.
    
    Args:
        item: DownloadableResource containing the configuration:
            - index_url: URL to fetch the JSON index containing identifiers
            - url_pattern: URL template with {ID} placeholder for individual file downloads
            - id_path: Optional JSONPath-like string to extract IDs from nested JSON structures
            - local_name: Optional filename template for determining file extensions
        outfile_path: Path to the output directory where files will be saved
        options: DownloadOptions containing:
            - progress: Whether to show progress bars
            - verbose: Whether to show detailed logging
            - fail_on_error: Whether to stop on first error or continue downloading
    
    Returns:
        None: Files are saved to disk in the specified output directory
    
    Raises:
        ValueError: If index_url or url_pattern are not provided
        ValueError: If the index JSON cannot be parsed
        ValueError: If no IDs can be extracted from the index data
        requests.exceptions.RequestException: If index or file downloads fail
        
    Examples:
        Basic usage with flat JSON array:
            index_url: "https://example.com/ids.json" -> ["id1", "id2", "id3"]
            url_pattern: "https://example.com/files/{ID}.yaml"
            
        Nested JSON structure (like GO-CAM):
            index_url: "https://s3.amazonaws.com/provider-to-model.json"
            -> {"source1": ["id1", "id2"], "source2": ["id3"]}
            id_path: "" (extracts all IDs from all arrays)
            url_pattern: "https://example.com/models/{ID}.yaml"
    """
    if not item.index_url:
        raise ValueError("index_url is required for index-based downloads")
    if not item.url_pattern:
        raise ValueError("url_pattern is required for index-based downloads")
    
    index_response = requests.get(item.index_url, timeout=10, verify=item.verify_ssl)
    index_response.raise_for_status()
    
    try:
        index_data = index_response.json()
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse index JSON from {item.index_url}: {e}")
    
    ids = extract_ids_from_json(index_data, item.id_path or "")
    
    if not ids:
        raise ValueError(f"No IDs found in index data using path: {item.id_path}")
    
    outfile_path.mkdir(parents=True, exist_ok=True)
    
    failed_downloads = []
    
    progress_enabled = getattr(options, "progress", True)
    progress_ctx = tqdm(total=len(ids), desc=f"Downloading indexed files") if progress_enabled else nullcontext()
    with progress_ctx as pbar:
        for id_value in ids:
            try:
                file_url = item.url_pattern.replace("{ID}", str(id_value))
                
                local_filename = f"{id_value}.yaml"
                if item.local_name:
                    extension = item.local_name.split(".")[-1] if "." in item.local_name else "yaml"
                    local_filename = f"{id_value}.{extension}"
                
                local_file_path = outfile_path / local_filename
                
                response = requests.get(
                    file_url,
                    headers={"User-Agent": DEFAULT_USER_AGENT},
                    stream=True,
                    timeout=DEFAULT_TIMEOUT,
                    verify=item.verify_ssl
                )
                response.raise_for_status()
                
                with open(local_file_path, "wb") as f:
                    for chunk in response.iter_content(CHUNK_SIZE):
                        f.write(chunk)
                
                if options.verbose:
                    tqdm.write(f"Downloaded: {file_url} -> {local_file_path}")
                    
            except requests.RequestException as e:
                if options.fail_on_error:
                    raise e
                else:
                    failed_downloads.append((id_value, str(e)))
                    if options.verbose:
                        tqdm.write(f"Failed to download {id_value}: {e}")
            
            if progress_enabled and pbar:
                pbar.update(1)
    
    if failed_downloads and not options.fail_on_error:
        tqdm.write(f"Failed to download {len(failed_downloads)} files out of {len(ids)}")
        if options.verbose:
            for id_value, error in failed_downloads:
                tqdm.write(f"  {id_value}: {error}")
