from collections.abc import Callable
from pathlib import Path
from typing import Dict, Optional

from kghub_downloader.model import DownloadableResource


ResourceDownloadFunction = Callable[
    [DownloadableResource, Path, bool],
    None
]

ResourceDownloadRegistry = Dict[str, ResourceDownloadFunction]

available_schemes: ResourceDownloadRegistry = {}


def register_scheme(
    name: str,
    registry: Optional[ResourceDownloadRegistry] = None
) -> Callable[[ResourceDownloadFunction], ResourceDownloadFunction]:
    # Use global registry if no dictionary is pass as an argument
    if registry is None:
        registry = available_schemes

    def with_added_scheme(fn: ResourceDownloadFunction):
        registry[name] = fn
        return fn
    return with_added_scheme
