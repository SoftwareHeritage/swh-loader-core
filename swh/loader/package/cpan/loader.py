# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from datetime import datetime
import logging
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import attr
import iso8601
from packaging.version import parse as parse_version

from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.loader.package.utils import EMPTY_AUTHOR, Person, release_name
from swh.model.model import ObjectType, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


@attr.s
class CpanPackageInfo(BasePackageInfo):

    name = attr.ib(type=str)
    """Name of the package"""

    version = attr.ib(type=str)
    """Current version"""

    last_modified = attr.ib(type=datetime)
    """File last modified date as release date."""

    author = attr.ib(type=Person)
    """Author"""


class CpanLoader(PackageLoader[CpanPackageInfo]):
    visit_type = "cpan"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        api_base_url: str,
        artifacts: List[Dict[str, Any]],
        module_metadata: List[Dict[str, Any]],
        **kwargs,
    ):

        super().__init__(storage=storage, url=url, **kwargs)
        self.url = url
        self.api_base_url = api_base_url
        self.artifacts: Dict[str, Dict] = {
            artifact["version"]: {k: v for k, v in artifact.items() if k != "version"}
            for artifact in artifacts
        }
        self.module_metadata: Dict[str, Dict] = {
            meta["version"]: meta for meta in module_metadata
        }

    def get_versions(self) -> Sequence[str]:
        """Get all released versions of a Perl package

        Returns:
            A sequence of versions

            Example::

                ["0.1.1", "0.10.2"]
        """
        versions = list(self.artifacts.keys())
        versions.sort(key=parse_version)
        return versions

    def get_default_version(self) -> str:
        """Get the newest release version of a Perl package

        Returns:
            A string representing a version

            Example::

                "0.10.2"
        """
        return self.get_versions()[-1]

    def get_package_info(self, version: str) -> Iterator[Tuple[str, CpanPackageInfo]]:
        """Get release name and package information from version

        Args:
            version: Package version (e.g: "0.1.0")

        Returns:
            Iterator of tuple (release_name, p_info)
        """
        artifact = self.artifacts[version]
        metadata = self.module_metadata[version]

        last_modified = iso8601.parse_date(metadata["date"])
        author = (
            Person.from_fullname(metadata["author"].encode())
            if metadata["author"]
            else EMPTY_AUTHOR
        )

        p_info = CpanPackageInfo(
            name=metadata["name"],
            filename=artifact["filename"],
            url=artifact["url"],
            version=version,
            last_modified=last_modified,
            author=author,
            checksums=artifact["checksums"],
        )
        yield release_name(version), p_info

    def build_release(
        self, p_info: CpanPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:

        message = (
            f"Synthetic release for Perl source package {p_info.name} "
            f"version {p_info.version}\n"
        )

        return Release(
            name=p_info.version.encode(),
            author=p_info.author,
            date=TimestampWithTimezone.from_datetime(p_info.last_modified),
            message=message.encode(),
            target_type=ObjectType.DIRECTORY,
            target=directory,
            synthetic=True,
        )
