from collections.abc import Callable
from pathlib import Path
from typing import Dict, Optional

from kghub_downloader.model import DownloadableResource


ResourceDownloadFunction = Callable[
    [DownloadableResource, Path, bool],
    None
]

ResourceDownloadRegistry = Dict[str, ResourceDownloadFunction]

available_schemas: ResourceDownloadRegistry = {}


def register_schema(
    name: str,
    registry: Optional[ResourceDownloadRegistry] = None
) -> Callable[[ResourceDownloadFunction], ResourceDownloadFunction]:
    # Use global registry if no dictionary is pass as an argument
    if registry is None:
        registry = available_schemas

    def with_added_schema(fn: ResourceDownloadFunction):
        registry[name] = fn
        return fn
    return with_added_schema
