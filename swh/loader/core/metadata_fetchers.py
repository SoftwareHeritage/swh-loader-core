# Copyright (C) 2022 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import functools
from typing import Dict, List, Optional, Set, Type

import pkg_resources
from typing_extensions import Protocol, runtime_checkable

from swh.model.model import Origin, RawExtrinsicMetadata

CredentialsType = Optional[Dict[str, Dict[str, List[Dict[str, str]]]]]


@runtime_checkable
class MetadataFetcherProtocol(Protocol):
    """Interface provided by :class:`swh.loader.metadata.base.BaseMetadataFetcher`
    to loaders, via setuptools entrypoints."""

    SUPPORTED_LISTERS: Set[str]
    FETCHER_NAME: str

    def __init__(
        self,
        origin: Origin,
        credentials: CredentialsType,
        lister_name: str,
        lister_instance_name: str,
    ):
        ...

    def get_origin_metadata(self) -> List[RawExtrinsicMetadata]:
        ...

    def get_parent_origins(self) -> List[Origin]:
        ...


@functools.lru_cache()
def _fetchers() -> List[Type[MetadataFetcherProtocol]]:
    classes = []
    for entry_point in pkg_resources.iter_entry_points("swh.loader.metadata"):
        classes.append(entry_point.load())

    return classes


def get_fetchers_for_lister(lister_name: str) -> List[Type[MetadataFetcherProtocol]]:
    return [cls for cls in _fetchers() if lister_name in cls.SUPPORTED_LISTERS]
