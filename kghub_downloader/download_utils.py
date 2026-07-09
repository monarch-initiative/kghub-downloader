"""The main functionality for downloading resources, as defined by the class in model.py."""

import logging
import pathlib
import time
import traceback
from typing import List, Optional
from urllib.parse import urlparse

import yaml
from tqdm.auto import tqdm

from kghub_downloader import schemes, upload
from kghub_downloader.elasticsearch import download_from_elastic_search
from kghub_downloader.model import DownloadableResource, DownloadOptions, DownloadReport


def download_from_yaml(
    yaml_file: str,
    output_dir: str,
    download_options: Optional[DownloadOptions] = None,
    tags: Optional[List] = None,
    mirror: Optional[str] = None,
) -> DownloadReport:
    """
    Download files listed in a download.yaml file.

    Args:
        yaml_file: A string pointing to the download.yaml file, to be parsed for things to download.
        output_dir: A string pointing to where to write out downloaded files.
        download_options: An object containing boolean flags that change download behavior
        tags: Limit to only downloads with this tag
        mirror: Optional remote storage URL to mirror download to. Supported buckets: Google Cloud Storage

    Returns:
        A DownloadReport with the absolute paths of files that were downloaded this run,
        skipped (already present, served from cache), or failed (only populated when
        fail_on_error is False; otherwise the first error is raised).

    """
    start_time = time.time()

    if download_options is None:
        download_options = DownloadOptions()

    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)

    with open(yaml_file) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    resources: List[DownloadableResource] = [DownloadableResource(**x) for x in data]

    # Limit to only tagged downloads, if tags are passed in
    if tags:
        resources = [item for item in resources if item.tag in tags]

    report = DownloadReport()

    pbar = tqdm(
        resources,
        position=2,
        leave=False,
        bar_format="Downloading {n_fmt}/{total_fmt} [{bar:20}]",
        ascii=".█",
    )

    for item in resources:
        pbar.update()
        pbar.refresh()
        url = item.expanded_url
        outfile_path = output_dir / item.path
        outfile_dir = outfile_path.parent

        logging.info("Retrieving %s from %s" % (item.path, url))

        # Can't truncate compressed file
        if download_options.snippet_only and item.is_compressed_file:
            logging.error("Asked to download snippets; can't snippet {}".format(item))
            continue

        if not outfile_dir.exists():
            logging.info(f"Creating local directory {outfile_dir}")
            outfile_dir.mkdir(parents=True, exist_ok=True)

        if outfile_path.exists():
            if download_options.ignore_cache:
                logging.info(f"Deleting cached version of {outfile_path}")
                outfile_path.unlink()
            else:
                logging.info(f"Using cached version of {outfile_path}")
                tqdm.write(f"SKIPPING: {outfile_path} already exists")
                report.skipped.append(outfile_path.resolve())
                continue

        # Download file
        if item.api is not None:
            if item.api == "elasticsearch":
                download_from_elastic_search(item, str(outfile_path))
                report.downloaded.append(outfile_path.resolve())
            else:
                raise RuntimeError(f"API {item.api} not supported")
            continue

        parsed_url = urlparse(item.expanded_url)
        download_fn = schemes.available_schemes.get(parsed_url.scheme, None)

        if download_fn is None:
            raise ValueError(f"Invalid URL scheme for url {item.expanded_url}")

        try:
            download_fn(item, outfile_path, download_options)
            report.downloaded.append(outfile_path.resolve())
        except BaseException as e:
            report.failed.append(outfile_path.resolve())
            if outfile_path.exists():
                outfile_path.unlink()

            if download_options.fail_on_error:
                raise e

            # If this was cancelled with Ctrl-C, re-raise the exception and let Typer handle it
            if isinstance(e, KeyboardInterrupt):
                pbar.close()
                raise e

            if download_options.verbose:
                message = traceback.format_exception(e)[-1]
                tqdm.write(f"{message}")

            continue

        if mirror:
            upload.mirror_to_bucket(outfile_path, mirror, item.path)

    pbar.close()
    exec_time = time.time() - start_time

    tqdm.write(
        f"\n\nDownload completed in {exec_time:.2f} seconds.\n\n"
        f"    successful:   {len(report.downloaded)}\n"
        f"    skipped:      {len(report.skipped)}\n"
        f"    unsuccessful: {len(report.failed)}\n"
    )

    show_verbose_message = all(
        (
            not download_options.fail_on_error,
            not download_options.verbose,
            len(report.failed) > 0,
        )
    )

    if show_verbose_message:
        tqdm.write("Some downloads were unsuccessful. Run with --verbose to see errors\n")

    return report
