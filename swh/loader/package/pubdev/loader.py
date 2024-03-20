# Copyright (C) 2022-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information
import json
from typing import Dict, Iterator, Optional, Sequence, Tuple

import attr
from packaging.version import parse as parse_version

from swh.loader.core.utils import (
    EMPTY_AUTHOR,
    Person,
    cached_method,
    get_url_body,
    release_name,
)
from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.model.model import ObjectType, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface


@attr.s
class PubDevPackageInfo(BasePackageInfo):
    name = attr.ib(type=str)
    """Name of the package"""

    version = attr.ib(type=str)
    """Current version"""

    last_modified = attr.ib(type=str)
    """Last modified date as release date"""

    author = attr.ib(type=Person)
    """Author"""


class PubDevLoader(PackageLoader[PubDevPackageInfo]):
    visit_type = "pubdev"

    PUBDEV_BASE_URL = "https://pub.dev/"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        **kwargs,
    ):
        super().__init__(storage=storage, url=url, **kwargs)
        self.url = url
        assert url.startswith(self.PUBDEV_BASE_URL)
        self.package_info_url = url.replace(
            self.PUBDEV_BASE_URL, f"{self.PUBDEV_BASE_URL}api/"
        )

    @cached_method
    def info(self) -> Dict:
        """Return the project metadata information (fetched from pub.dev registry)"""
        # Use strict=False in order to correctly manage case where \n is present in a string
        info = json.loads(get_url_body(self.package_info_url), strict=False)
        # Arrange versions list as a new dict with `version` as key
        versions = {v["version"]: v for v in info["versions"]}
        info["versions"] = versions
        return info

    def get_versions(self) -> Sequence[str]:
        """Get all released versions of a PubDev package

        Returns:
            A sequence of versions

            Example::

                ["0.1.1", "0.10.2"]
        """
        versions = list(self.info()["versions"].keys())
        versions.sort(
            key=lambda version: parse_version(version.split("-", maxsplit=1)[0])
        )
        return versions

    def get_default_version(self) -> str:
        """Get the newest release version of a PubDev package

        Returns:
            A string representing a version

            Example::

                "0.1.2"
        """
        latest = self.info()["latest"]
        return latest["version"]

    def get_package_info(self, version: str) -> Iterator[Tuple[str, PubDevPackageInfo]]:
        """Get release name and package information from version

        Package info comes from extrinsic metadata (from self.info())

        Args:
            version: Package version (e.g: "0.1.0")

        Returns:
            Iterator of tuple (release_name, p_info)
        """
        v = self.info()["versions"][version]
        assert v["version"] == version

        url = v["archive_url"]
        name = v["pubspec"]["name"]
        filename = f"{name}-{version}.tar.gz"
        last_modified = v["published"]
        checksums = {"sha256": v["archive_sha256"]} if v.get("archive_sha256") else {}

        authors = v.get("pubspec", {}).get("authors")
        if authors and isinstance(authors, list):
            # TODO: here we have a list of author, see T3887
            author = Person.from_fullname(authors[0].encode())
        elif v.get("pubspec", {}).get("author"):
            author = Person.from_fullname(v["pubspec"]["author"].encode())
        else:
            author = EMPTY_AUTHOR

        p_info = PubDevPackageInfo(
            name=name,
            filename=filename,
            url=url,
            version=version,
            last_modified=last_modified,
            author=author,
            checksums=checksums,
        )
        yield release_name(version), p_info

    def build_release(
        self, p_info: PubDevPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        message = (
            f"Synthetic release for pub.dev source package {p_info.name} "
            f"version {p_info.version}\n"
        )

        return Release(
            name=p_info.version.encode(),
            author=p_info.author,
            date=TimestampWithTimezone.from_iso8601(p_info.last_modified),
            message=message.encode(),
            target_type=ObjectType.DIRECTORY,
            target=directory,
            synthetic=True,
        )
