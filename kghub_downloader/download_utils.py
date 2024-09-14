import json
import logging
import os
import pathlib
import re
from typing import List, Optional

import compress_json  # type: ignore
import elasticsearch
import elasticsearch.helpers
import yaml
from tqdm.auto import tqdm  # type: ignore

from kghub_downloader.model import DownloadableResource
from kghub_downloader import download, upload

# from compress_json import compress_json


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
                download.google_cloud_storage(item, outfile_path)
            elif url.startswith("s3://"):
                download.s3(item, outfile_path)
            elif url.startswith("ftp"):
                download.ftp(item, outfile_path)
            elif url.startswith("gdrive:"):
                download.google_drive(item, outfile_path)
            elif url.startswith("git://"):
                download.git(item, outfile_path)
            else:
                download.http(item, outfile_path, snippet_only)

        # If mirror, upload to remote storage
        if mirror:
            upload.mirror_to_bucket(outfile_path, mirror, item.path)

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
                f"Environment Variable: {i} is not set. Please set the"
                "variable using export or similar, and try again.")
        url = url.replace("{" + i + "}", secret)
    return url
