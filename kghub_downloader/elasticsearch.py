"""Code for downloading resources via Elasticsearch."""

import json
import os

import compress_json  # type: ignore
import elasticsearch
import elasticsearch.helpers
from tqdm.auto import tqdm

from kghub_downloader.model import DownloadableResource


def download_from_elastic_search(yaml_item: DownloadableResource, outfile: str) -> None:
    """
    Download a resource from Elasticsearch.

    Args:
        yaml_item: item to be download, parsed from yaml
        outfile: where to write out file

    Returns:
        None

    """
    es_conn = elasticsearch.Elasticsearch(hosts=[yaml_item.url])

    if yaml_item.query_file is None:
        raise ValueError("No elasticsearch query file was provided in item " "configuration")

    if yaml_item.index is None:
        raise ValueError("No elasticsearch index was provided in item" "configuration")

    # FIXME: Validate query file and index parameters exist
    query_data = compress_json.local_load(os.path.join(os.getcwd(), yaml_item.query_file))
    records = elastic_search_query(es_conn, index=yaml_item.index, query=query_data)

    with open(outfile, "w") as output:
        json.dump(records, output)

    return None


def elastic_search_query(
    es_connection: elasticsearch.Elasticsearch,
    index: str,
    query: str,
    scroll: str = "1m",
    request_timeout: int = 60,
    preserve_order: bool = True,
):
    """
    Fetch records from the given URL and query parameters.

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
