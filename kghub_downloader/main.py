"""CLI interface for kghub-downloader."""

from typing import Annotated, List, Optional

import typer

from kghub_downloader.download_utils import download_from_yaml
from kghub_downloader.model import DownloadOptions

typer_app = typer.Typer()


@typer_app.command()
def main(
    yaml_file: Annotated[
        str,
        typer.Argument(help="List of files to download in YAML format"),
    ] = "download.yaml",
    output_dir: Annotated[
        str,
        typer.Option(help="Path to output directory"),
    ] = ".",
    ignore_cache: Annotated[
        bool,
        typer.Option(help="Ignoring already downloaded files and download again"),
    ] = False,
    progress: Annotated[
        bool,
        typer.Option(help="Show progress for individual downloads"),
    ] = True,
    fail_on_error: Annotated[
        bool,
        typer.Option(help="Do not attempt to download more files if one raises an error"),
    ] = False,
    snippet_only: Annotated[
        bool,
        typer.Option(help="Only download a snippet of the file. [HTTP(S) resources only.")
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(help="Show verbose output"),
    ] = False,
    tags: Annotated[
        Optional[List[str]],
        typer.Option(help="Optional list of tags to limit downloading to"),
    ] = None,
    mirror: Annotated[
        Optional[str],
        typer.Option(help="Optional remote storage URL to mirror download to. Supported buckets: Google Cloud Storage"),
    ] = None,
):
    """Download a set of files defined in a YAML file."""
    options = DownloadOptions(
        snippet_only=snippet_only,
        ignore_cache=ignore_cache,
        progress=progress,
        fail_on_error=fail_on_error,
        verbose=verbose,
    )

    download_from_yaml(
        yaml_file=yaml_file,
        output_dir=output_dir,
        download_options=options,
        tags=tags,
        mirror=mirror,
    )


if __name__ == "__main__":
    typer_app()
