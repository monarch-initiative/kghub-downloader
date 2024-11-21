"""The model definition of a resource able to be downloaded by the downloader."""

import os
import pathlib
import re
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, FilePath

valid_url_schemes = [
    "http",
    "gs",
    "gdrive",  # FIXME: document
    "git",
    "s3",
    "ftp",
]


class DownloadOptions(BaseModel):
    """Options for downloading a resource."""

    snippet_only: bool = False
    ignore_cache: bool = False
    progress: bool = False
    fail_on_error: bool = True
    verbose: bool = False


class DownloadableResource(BaseModel):
    """A resource able to be downloaded."""

    url: str = Field(pattern=r"^" + "|".join(valid_url_schemes))
    api: Optional[Union[Literal["elasticsearch"]]] = None
    tag: Optional[str] = None
    local_name: Optional[str] = None
    glob: Optional[str] = None

    # ElasticSearch parameters. Should probably be split into a nested config.
    query_file: Optional[FilePath] = None
    index: Optional[str] = None

    @property
    def path(self) -> pathlib.Path:
        """
        The filename of the output file.

        If not set explicitly via the local_name option, will be set automatically from the resource's URL.
        """
        filename = self.local_name or self.url.split("/")[-1]
        return pathlib.Path(filename)

    @property
    def is_compressed_file(self):
        """
        Checks whether a file is compressed.

        Used to check whether a snippet of the resource can be downloaded.
        """
        return self.path.suffix in ["zip", "gz"]

    @property
    def expanded_url(self) -> str:
        """Parses a URL for any environment variables enclosed in {curly braces}."""
        pattern = r".*?\{(.*?)\}"
        url = self.url
        match = re.findall(pattern, url)
        for i in match:
            secret = os.getenv(i)
            if secret is None:
                raise ValueError(
                    f"Environment Variable: {i} is not set. Please set the "
                    "variable using export or similar, and try again."
                )
            url = url.replace("{" + i + "}", secret)
        return url
