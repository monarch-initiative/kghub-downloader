import os
import pathlib
import re
from typing import Optional, Literal, Union

from pydantic import BaseModel, Field, FilePath

valid_url_schemas = [
    "http",
    "gs",
    "gdrive",  # FIXME: document
    "git",
    "s3",
    "ftp",
]


class DownloadableResource(BaseModel):
    url: str = Field(
        pattern=r"^" + '|'.join(valid_url_schemas)
    )
    api: Optional[Union[Literal['elasticsearch']]] = None
    tag: Optional[str] = None
    local_name: Optional[str] = None
    glob: Optional[str] = None

    # ElasticSearch parameters. Should probably be split into a nested config.
    query_file: Optional[FilePath] = None
    index: Optional[str] = None

    @property
    def path(self) -> pathlib.Path:
        filename = self.local_name or self.url.split("/")[-1]
        return pathlib.Path(filename)

    @property
    def is_compressed_file(self):
        return self.path.suffix in ["zip", "gz"]

    @property
    def expanded_url(self) -> str:
        """Parses a URL for any environment variables enclosed in {curly braces}"""
        pattern = r".*?\{(.*?)\}"
        url = self.url
        match = re.findall(pattern, url)
        for i in match:
            secret = os.getenv(i)
            if secret is None:
                raise ValueError(
                    f"Environment Variable: {i} is not set. Please set the variable using export or similar, and try again."
                )
            url = url.replace("{" + i + "}", secret)
        return url
