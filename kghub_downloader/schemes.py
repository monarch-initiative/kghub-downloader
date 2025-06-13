"""Helper code to register URI schemes to a downloader function."""

from collections.abc import Callable
from pathlib import Path
from typing import Dict, Optional

from kghub_downloader.model import DownloadableResource, DownloadOptions

ResourceDownloadFunction = Callable[[DownloadableResource, Path, DownloadOptions], None]

ResourceDownloadRegistry = Dict[str, ResourceDownloadFunction]

available_schemes: ResourceDownloadRegistry = {}


def register_scheme(
    name: str, registry: Optional[ResourceDownloadRegistry] = None
) -> Callable[[ResourceDownloadFunction], ResourceDownloadFunction]:
    """
    Register a URI scheme with a downloader function. Should be used as a function decorator.

    Args:
        name: The string of the URI scheme (e.g. "http" or "s3").
        registry: An optional dictionary where the decorated function will be associated with the scheme. If no value
            is passed, a global dictionary will be used.

    """
    # Use global registry if no dictionary is pass as an argument
    if registry is None:
        registry = available_schemes

    def with_added_scheme(fn: ResourceDownloadFunction):
        """Register a function in the passed registry and return it unchanged."""
        registry[name] = fn
        return fn

    return with_added_scheme
