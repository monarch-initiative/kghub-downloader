import csv
import json
import logging
import os
import pathlib
import re

# from compress_json import compress_json
from typing import List, Optional
from urllib import parse
from urllib.error import URLError
from urllib.request import Request, urlopen

import compress_json  # type: ignore
import elasticsearch
import elasticsearch.helpers
import gdown
import pandas as pd
import requests
import yaml
from google.cloud import storage
from google.cloud.storage.blob import Blob
from tqdm.auto import tqdm  # type: ignore

GDOWN_MAP = {"gdrive": "https://drive.google.com/uc?id="}

""",
    fields: Optional[List] = None,
    keywords: Optional[List] = None,
    size: Optional[int] = None,
    batch_size: Optional[int] = None"""


def download_from_yaml(
    yaml_file: str,
    output_dir: str,
    ignore_cache: Optional[bool] = False,
    snippet_only: Optional[bool] = False,
    tags: Optional[List] = None,
    mirror: Optional[str] = None,
) -> None:
    """
    Download files listed in a download.yaml file

    Args:
    ----
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
            ###########
            if "url" not in item:
                logging.error("Couldn't find url for source in {}".format(item))
                continue

            if snippet_only and (item["local_name"])[-3:] in [
                "zip",
                ".gz",
            ]:  # Can't truncate compressed files
                logging.error("Asked to download snippets; can't snippet {}".format(item))
                continue

            local_name = (
                item["local_name"]
                if "local_name" in item and item["local_name"]
                else item["url"].split("/")[-1]
            )

            outfile = os.path.join(output_dir, local_name)

            logging.info("Retrieving %s from %s" % (outfile, item["url"]))

            if "local_name" in item:
                local_file_dir = os.path.join(output_dir, os.path.dirname(item["local_name"]))
                if not os.path.exists(local_file_dir):
                    logging.info(f"Creating local directory {local_file_dir}")
                    pathlib.Path(local_file_dir).mkdir(parents=True, exist_ok=True)

            if os.path.exists(outfile):
                if ignore_cache:
                    logging.info("Deleting cached version of {}".format(outfile))
                    os.remove(outfile)
                else:
                    logging.info("Using cached version of {}".format(outfile))
                    if "local_name" in item and item["local_name"] != "uniprot_genome_features":
                        continue

            # Download file
            if "local_name" in item and item["local_name"] != "uniprot_genome_features":
                if "api" in item:
                    download_from_api(item, outfile)
                if "url" in item:
                    url = parse_url(item["url"])
                    if url.startswith("gs://"):
                        Blob.from_string(url, client=storage.Client()).download_to_filename(outfile)
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
                                    data = response.read(5120)  # first 5 kB of a `bytes` object
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
            elif "local_name" in item and item["local_name"] == "uniprot_genome_features":
                outfile = outfile.split(item["local_name"])[0]
                outfile = outfile + "ncbitaxon_removed_subset.json"
                url = parse_url(item["url"])
                if url.startswith("gs://"):
                    Blob.from_string(url, client=storage.Client()).download_to_filename(outfile)
                download_from_api(item, outfile)

            # If mirror, upload to remote storage
            if mirror:
                mirror_to_bucket(local_file=outfile, bucket_url=mirror, remote_file=local_name)

    return None


def mirror_to_bucket(local_file, bucket_url, remote_file) -> None:
    with open(local_file, "rb"):
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

            blob = (
                bucket.blob(f"{bucket_path}/{remote_file}")
                if bucket_path
                else bucket.blob(remote_file)
            )

            print(f"Uploading {local_file} to remote mirror: gs://{blob.name}/")
            blob.upload_from_filename(local_file)

        elif bucket_url.startswith("s3://"):
            raise ValueError("Currently, only Google Cloud storage is supported.")
            # bashCommand = f"aws s3 cp {outfile} {mirror}"
            # subprocess.run(bashCommand.split())

        else:
            raise ValueError("Currently, only Google Cloud storage is supported.")

    return None


def download_from_api(yaml_item, outfile) -> None:
    """

    Args:
    ----
        yaml_item: item to be download, parsed from yaml
        outfile: where to write out file

    Returns:
    -------

    """
    if yaml_item["api"] == "elasticsearch":
        es_conn = elasticsearch.Elasticsearch(hosts=[yaml_item["url"]])
        query_data = compress_json.local_load(os.path.join(os.getcwd(), yaml_item["query_file"]))
        output = open(outfile, "w")
        records = elastic_search_query(es_conn, index=yaml_item["index"], query=query_data)
        json.dump(records, output)
        return None
    elif yaml_item["api"] == "rest":
        if yaml_item["test"]:
            ncbi_organisms = ["1", "100", "1000", "1591", "885", "84112", "1308"]
        else:
            ncbi_organisms = parse_ncbitaxon_json(
                outfile.rsplit("/", 1)[0] + "/" + "ncbitaxon_removed_subset.json"
            )

        outyamls = outfile.rsplit("/", 1)[0] + "/" + yaml_item["local_name"]
        os.makedirs(outyamls, exist_ok=True)

        get_uniprot_values_organism(
            ncbi_organisms,
            yaml_item["base_url"],
            yaml_item["fields"],
            yaml_item["keywords"],
            yaml_item["size"],
            yaml_item["batch_size"],
            outyamls,
        )

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
    """
    Fetch records from the given URL and query parameters.

    Args:
    ----
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


def parse_ncbitaxon_json(input_file):
    with open(input_file, "r") as f:
        contents = json.loads(f.read())

        organism_ids = [
            i["id"].split("NCBITaxon_")[1]
            for i in contents["graphs"][0]["nodes"]
            if "NCBITaxon_" in i["id"]
        ]

    return organism_ids


def get_uniprot_values_organism(
    organism_ids, base_url, fields, keywords, size, batch_size, outyamls
):
    values = []

    # File to keep track of organism id's with no Uniprot data
    empty_org_file = outyamls + "/empty_organism_queries.tsv"
    empty_org_file_header = "Organism_ID"
    if os.path.exists(empty_org_file):
        df = pd.read_csv(empty_org_file)
        empty_orgs = df[empty_org_file_header].tolist()
        empty_orgs = list(map(str, empty_orgs))

    elif not os.path.exists(empty_org_file):
        empty_orgs = []

    e = open(empty_org_file, "w")
    org_writer = csv.writer(e, delimiter="\t")
    org_writer.writerow([empty_org_file_header])
    if len(empty_orgs) > 0:
        for i in empty_orgs:
            org_writer.writerow([i])
    e.close()

    print(
        "querying uniprot for enzymes per organism ("
        + str(len(organism_ids))
        + ") by batch size ("
        + str(batch_size)
        + ")"
    )
    with tqdm(total=len(organism_ids), desc="Processing files") as progress:
        # Batch orgs to append to file
        batch_orgs = []
        for i in range(0, len(organism_ids), batch_size):
            values, b = _get_uniprot_batch_organism(
                organism_ids,
                base_url,
                i,
                fields,
                keywords,
                size,
                batch_size,
                values,
                outyamls,
                empty_orgs,
            )
            batch_orgs = batch_orgs + b

            progress.set_description(
                f"Downloading organism data from Uniprot, final file of batch: {organism_ids[min(i + batch_size, len(organism_ids))-1]}.json"
            )
            # After each iteration, call the update method to advance the progress bar.
            progress.update()

            if len(batch_orgs) > 0 and len(batch_orgs) % 100 == 0:
                # Write to file and reset list of empty orgs
                batch_orgs = write_to_empty_orgs(batch_orgs, empty_org_file)

        write_to_empty_orgs(batch_orgs, empty_org_file)


def write_to_empty_orgs(batch_orgs, empty_org_file):
    e = open(empty_org_file, "a")
    org_writer = csv.writer(e, delimiter="\t")
    for o in batch_orgs:
        org_writer.writerow([o])
    # Reset batch orgs to append to file
    batch_orgs = []
    e.close()

    return batch_orgs


def check_for_file_existence_in_batch(batch, outyamls, empty_orgs):
    for org in batch.copy():
        org_file = outyamls + "/" + org + ".json"
        if os.path.exists(org_file) or org in empty_orgs:
            batch.remove(org)
    return batch


def _get_uniprot_batch_organism(
    organism_ids, base_url, i, fields, keywords, size, batch_size, values, outyamls, empty_orgs
):
    """Get batch of Uniprot data."""
    # Organisms in this batch found with empty queries
    confirmed_empty_orgs = []
    batch = organism_ids[i : min(i + batch_size, len(organism_ids))]
    nonexistent_batch = check_for_file_existence_in_batch(batch, outyamls, empty_orgs)

    if len(nonexistent_batch) > 0:
        query = "%20OR%20".join(["organism_id:" + organism_id for organism_id in nonexistent_batch])
        if len(keywords) > 0:
            k = "&keywords=" + "+".join(keywords)
        else:
            k = ""

        url = (
            base_url
            + "/search?query="
            + query
            + "&format=tsv&"
            + "size="
            + str(size)
            + k
            + "&fields="
            + "%2C".join([parse.quote(field) for field in fields])
        )

        # All values after paging for specific batch of organism_ids
        values = _get_uniprot_batch_reference_proteome(url)

        for org in nonexistent_batch:
            org_file = outyamls + "/" + org + ".json"
            org_values = [j for j in values if j["Organism (ID)"] == org]
            if len(org_values) > 0:
                with open(org_file, "w") as f:
                    json.dump(org_values, f)
            # Don't write file if no content in query, keep track of which organism_id's are empty
            elif len(org_values) == 0:
                confirmed_empty_orgs.append(org)

    return values, confirmed_empty_orgs


def _get_uniprot_batch_reference_proteome(url):
    values = []

    get_jobs(url, values)

    return values


def get_jobs(url, values):
    session = requests.Session()

    paging = True

    first_page = session.get(url)
    first_response = parse_response(first_page, values)

    while paging == True:
        if "next" in first_page.links:
            next_url = first_page.links["next"]["url"]
            next_page = session.get(next_url)
            next_response = parse_response(next_page, values)
            first_page = next_page
        else:
            paging = False
            break


def parse_response(res, values):
    headers = None

    for line in res.iter_lines():
        line = line.decode("utf-8")
        tokens = line.strip().split("\t")

        if headers is None:
            headers = tokens
        else:
            res = dict(zip(headers, tokens))
            values.append(res)

    return values
