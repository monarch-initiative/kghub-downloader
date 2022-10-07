import os, pathlib, re
import logging

import json, yaml
import compress_json  # type: ignore
#from compress_json import compress_json

from multiprocessing.sharedctypes import Value

from urllib.error import URLError
from urllib.request import Request, urlopen


import elasticsearch
import elasticsearch.helpers

from tqdm.auto import tqdm  # type: ignore
from google.cloud import storage
from google.cloud.storage.blob import Blob
from typing import List, Optional


def download_from_yaml(yaml_file: str,
                       output_dir: str,
                       ignore_cache: Optional[bool] = False,
                       snippet_only=False,
                       tags: Optional[List] = None,
                       mirror: Optional[str] = None
                       ) -> None:
    """Given an download info from an download.yaml file, download all files

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

        # Limit to only tagged downloads, if tags are passed in
        if tags:
            data = [item for item in data if "tag" in item and item["tag"] and item["tag"] in tags]

        for item in tqdm(data, desc="Downloading files"):
            if 'url' not in item:
                logging.error("Couldn't find url for source in {}".format(item))
                continue
            if snippet_only and (item['local_name'])[-3:] in ["zip",".gz"]: # Can't truncate compressed files
                logging.error("Asked to download snippets; can't snippet {}".format(item))
                continue

            local_name = item['local_name'] if 'local_name' in item and item['local_name'] else item['url'].split("/")[-1]
            outfile = os.path.join(output_dir, local_name)

            logging.info("Retrieving %s from %s" % (outfile, item['url']))

            if 'local_name' in item:
                local_file_dir = os.path.join(output_dir, os.path.dirname(item['local_name']))
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
            if 'api' in item:
                download_from_api(item, outfile)
            if 'url' in item:
                url = parse_url(item['url'])
                if url.startswith("gs://"):
                    Blob.from_string(url, client=storage.Client()).download_to_filename(outfile)
                else:
                    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    try:
                        with urlopen(req) as response, open(outfile, 'wb') as out_file:  # type: ignore
                            if snippet_only:
                                data = response.read(5120)  # first 5 kB of a `bytes` object
                            else:
                                data = response.read()  # a `bytes` object
                            out_file.write(data)
                            if snippet_only: #Need to clean up the outfile
                                in_file = open(outfile, 'r+')
                                in_lines = in_file.read()
                                in_file.close()
                                splitlines=in_lines.split("\n")
                                outstring="\n".join(splitlines[:-1])
                                cleanfile = open(outfile,'w+')
                                for i in range(len(outstring)):
                                    cleanfile.write(outstring[i])
                                cleanfile.close()
                    except URLError:
                        logging.error(f"Failed to download: {url}")
                        raise
            
            # If mirror, upload to remote storage
            if mirror:
                mirror_to_bucket(local_file=outfile, 
                                 bucket_url=mirror,
                                 remote_file=local_name
                            )


    return None

def mirror_to_bucket(local_file, bucket_url, remote_file) -> None:
    with open(local_file, 'rb'):
        if bucket_url.startswith("gs://"):
            
            # Remove any trailing slashes (Google gets confused)
            bucket_url = bucket_url.rstrip("/")
            
            # Connect to GCS Bucket
            storage_client = storage.Client()
            bucket_split = bucket_url.split("/")
            bucket_name = bucket_split[2]
            bucket = storage_client.bucket(bucket_name)

            # Upload blob from local file
            if len(bucket_split) > 3:
                bucket_path = "/".join(bucket_split[3:])
            else:
                bucket_path = None

            print(f"Bucket name: {bucket_name}")
            print(f"Bucket filepath: {bucket_path}")
            
            blob = bucket.blob(f"{bucket_path}/{remote_file}") if bucket_path else bucket.blob(remote_file)

            print(f"Uploading {local_file} to remote mirror: gs://{blob.name}/")
            blob.upload_from_filename(local_file)
        
        
        elif bucket_url.startswith("s3://"):
            raise ValueError("Currently, only Google Cloud storage is supported.")
            #bashCommand = f"aws s3 cp {outfile} {mirror}"
            #subprocess.run(bashCommand.split())

        else:
            raise ValueError("Currently, only Google Cloud storage is supported.")

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

def parse_url(url: str):
    """Parses a URL for any environment variables enclosed in {curly braces}"""
    pattern = ".*?\{(.*?)\}"
    match = re.findall(pattern, url)
    for i in match:
        secret = os.getenv(i)
        if secret is None:
            raise ValueError(f"Environment Variable: {i} is not set. Please set the variable using export or similar, and try again.")
        url = url.replace("{"+i+"}", secret)
    return url
