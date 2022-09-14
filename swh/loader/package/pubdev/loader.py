# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information
import json
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple

import attr
from packaging.version import parse as parse_version
import yaml

from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.loader.package.utils import (
    EMPTY_AUTHOR,
    Person,
    api_info,
    cached_method,
    release_name,
)
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

    description = attr.ib(type=str)
    """Description"""


def extract_intrinsic_metadata(dir_path: Path) -> Dict[str, Any]:
    """Extract intrinsic metadata from pubspec.yaml file at dir_path.

    Each pub.dev package version has a pubspec.yaml file at the root of the archive.

    See https://dart.dev/tools/pub/pubspec for pubspec specifications.

    Args:
        dir_path: A directory on disk where a pubspec.yaml must be present

    Returns:
        A dict mapping from yaml parser
    """
    pubspec_path = dir_path / "pubspec.yaml"
    return yaml.safe_load(pubspec_path.read_text())


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

    def _raw_info(self) -> bytes:
        return api_info(self.package_info_url)

    @cached_method
    def info(self) -> Dict:
        """Return the project metadata information (fetched from pub.dev registry)"""
        # Use strict=False in order to correctly manage case where \n is present in a string
        info = json.loads(self._raw_info(), strict=False)
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
        versions.sort(key=parse_version)
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

        if "authors" in v["pubspec"]:
            # TODO: here we have a list of author, see T3887
            author = Person.from_fullname(v["pubspec"]["authors"][0].encode())
        elif "author" in v["pubspec"] and v["pubspec"]["author"] is not None:
            author = Person.from_fullname(v["pubspec"]["author"].encode())
        else:
            author = EMPTY_AUTHOR

        description = v["pubspec"]["description"]

        p_info = PubDevPackageInfo(
            name=name,
            filename=filename,
            url=url,
            version=version,
            last_modified=last_modified,
            author=author,
            description=description,
        )
        yield release_name(version), p_info

    def build_release(
        self, p_info: PubDevPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:

        # Extract intrinsic metadata from uncompressed_path/pubspec.yaml
        intrinsic_metadata = extract_intrinsic_metadata(Path(uncompressed_path))

        name: str = intrinsic_metadata["name"]
        version: str = intrinsic_metadata["version"]
        assert version == p_info.version

        # author from intrinsic_metadata should not take precedence over the one
        # returned by the api, see https://dart.dev/tools/pub/pubspec#authorauthors
        author: Person = p_info.author

        if "description" in intrinsic_metadata and intrinsic_metadata["description"]:
            description = intrinsic_metadata["description"]
        else:
            description = p_info.description

        message = (
            f"Synthetic release for pub.dev source package {name} "
            f"version {version}\n\n"
            f"{description}\n"
        )

        return Release(
            name=version.encode(),
            author=author,
            date=TimestampWithTimezone.from_iso8601(p_info.last_modified),
            message=message.encode(),
            target_type=ObjectType.DIRECTORY,
            target=directory,
            synthetic=True,
        )
