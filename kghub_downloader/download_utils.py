"""The main functionality for downloading resources, as defined by the class in model.py."""

import logging
import pathlib
from typing import List, Optional
from urllib.parse import urlparse

import yaml
from tqdm.auto import tqdm  # type: ignore

from kghub_downloader import schemes, upload
from kghub_downloader.elasticsearch import download_from_elastic_search
from kghub_downloader.model import DownloadableResource

# from compress_json import compress_json


def download_from_yaml(
    yaml_file: str,
    output_dir: str,
    ignore_cache: Optional[bool] = False,
    snippet_only: bool = False,
    tags: Optional[List] = None,
    mirror: Optional[str] = None,
) -> None:
    """
    Download files listed in a download.yaml file.

    Args:
        yaml_file: A string pointing to the download.yaml file, to be parsed for things to download.
        output_dir: A string pointing to where to write out downloaded files.
        ignore_cache: Ignore cache and download files even if they exist.  [false]
        snippet_only: Downloads only the first 5 kB of each uncompressed source, for testing and file checks
        tags: Limit to only downloads with this tag
        mirror: Optional remote storage URL to mirror download to. Supported buckets: Google Cloud Storage
    Returns:
        None.

    """
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)

    with open(yaml_file) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    resources: List[DownloadableResource] = [DownloadableResource(**x) for x in data]

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
            logging.error("Asked to download snippets; can't snippet {}".format(item))
            continue

        if not outfile_dir.exists():
            logging.info(f"Creating local directory {outfile_dir}")
            outfile_dir.mkdir(parents=True, exist_ok=True)

        if outfile_path.exists():
            if ignore_cache:
                logging.info(f"Deleting cached version of {outfile_path}")
                outfile_path.unlink()
            else:
                logging.info("Using cached version of {outfile_path")
                continue

        # Download file
        if item.api is not None:
            if item.api == "elasticsearch":
                download_from_elastic_search(item, str(outfile_path))
            else:
                raise RuntimeError(f"API {item.api} not supported")
            continue

        parsed_url = urlparse(item.expanded_url)
        download_fn = schemes.available_schemes.get(parsed_url.scheme, None)

        if download_fn is None:
            raise ValueError(f"Invalid URL scheme for url {item.expanded_url}")

        try:
            download_fn(item, outfile_path, snippet_only)
        except BaseException as e:
            if outfile_path.exists():
                outfile_path.unlink()

            raise e

        # If mirror, upload to remote storage
        if mirror:
            upload.mirror_to_bucket(outfile_path, mirror, item.path)

    return None
