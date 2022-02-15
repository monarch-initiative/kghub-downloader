import json
import logging
import os
import pathlib
from os import path
from urllib.error import URLError
from urllib.request import Request, urlopen

import compress_json  # type: ignore
import elasticsearch
import elasticsearch.helpers
import yaml
from compress_json import compress_json
from tqdm.auto import tqdm  # type: ignore
from google.cloud import storage
from google.cloud.storage.blob import Blob
from typing import List


def download_from_yaml(yaml_file: str, output_dir: str,
                       ignore_cache: bool = False,
                       tags: List = None) -> None:
    """Given an download info from an download.yaml file, download all files

    Args:
        yaml_file: A string pointing to the download.yaml file, to be parsed for things to download.
        output_dir: A string pointing to where to write out downloaded files.
        ignore_cache: Ignore cache and download files even if they exist [false]
        tags: Limit to only downloads with this tag
    Returns:
        None.
    """

    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    with open(yaml_file) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
        for item in tqdm(data, desc="Downloading files"):
            if tags:
                if "tag" not in item or not item["tag"] or item["tag"] not in tags:
                    logging.warning("Skipping {} ".format(item))
                    continue

            if 'url' not in item:
                logging.warning("Couldn't find url for source in {}".format(item))
                continue
            outfile = os.path.join(
                output_dir,
                item['local_name']
                if 'local_name' in item
                else item['url'].split("/")[-1]
            )
            logging.info("Retrieving %s from %s" % (outfile, item['url']))

            if 'local_name' in item:
                local_file_dir = path.join(output_dir, path.dirname(item['local_name']))
                if not path.exists(local_file_dir):
                    logging.info(f"Creating local directory {local_file_dir}")
                    pathlib.Path(local_file_dir).mkdir(parents=True, exist_ok=True)

            if path.exists(outfile):
                if ignore_cache:
                    logging.info("Deleting cached version of {}".format(outfile))
                    os.remove(outfile)
                else:
                    logging.info("Using cached version of {}".format(outfile))
                    continue

            if 'api' in item:
                download_from_api(item, outfile)
            if 'url' in item and item['url'].startswith("gs://"):
                Blob.from_string(item['url'], client=storage.Client()).download_to_filename(outfile)
            else:
                req = Request(item['url'], headers={'User-Agent': 'Mozilla/5.0'})
                try:
                    with urlopen(req) as response, open(outfile, 'wb') as out_file:  # type: ignore
                        data = response.read()  # a `bytes` object
                        out_file.write(data)
                except URLError:
                    logging.error(f"Failed to download: {item['url']}")
                    raise

    return None


def download_from_api(yaml_item, outfile) -> None:
    """

    Args:
        yaml_item: item to be download, parsed from yaml
        outfile: where to write out file

    Returns:

    """
    if yaml_item['api'] == 'elasticsearch':
        es_conn = elasticsearch.Elasticsearch(hosts=[yaml_item['url']])
        query_data = compress_json.local_load(os.path.join(os.getcwd(), yaml_item['query_file']))
        output = open(outfile, 'w')
        records = elastic_search_query(es_conn, index=yaml_item['index'], query=query_data)
        json.dump(records, output)
        return None
    else:
        raise RuntimeError(f"API {yaml_item['api']} not supported")


def elastic_search_query(es_connection,
                         index,
                         query,
                         scroll: str = u'1m',
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
    results = elasticsearch.helpers.scan(client=es_connection,
                                         index=index,
                                         scroll=scroll,
                                         request_timeout=request_timeout,
                                         preserve_order=preserve_order,
                                         query=query)

    for item in tqdm(results, desc="querying for index: " + index):
        records.append(item)

    return records
