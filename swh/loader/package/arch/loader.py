# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information
from distutils.version import LooseVersion
from pathlib import Path
import re
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import attr

from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.loader.package.utils import release_name
from swh.model.model import ObjectType, Person, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface


@attr.s
class ArchPackageInfo(BasePackageInfo):

    name = attr.ib(type=str)
    """Name of the package"""

    version = attr.ib(type=str)
    """Current version"""

    last_modified = attr.ib(type=str)
    """File last modified date as release date"""


def extract_intrinsic_metadata(dir_path: Path) -> Dict[str, Any]:
    """Extract intrinsic metadata from .PKGINFO file at dir_path.

    Each Arch linux package has a .PKGINFO file at the root of the archive.

    Args:
        dir_path: A directory on disk where a package has been extracted

    Returns:
        A dict mapping
    """
    pkginfo_path = Path(dir_path, ".PKGINFO")
    rex = re.compile(r"^(\w+)\s=\s(.*)$", re.M)
    with pkginfo_path.open("rb") as content:
        parsed = rex.findall(content.read().decode())
        data = {entry[0].lower(): entry[1] for entry in parsed}
        if "url" in data.keys():
            data["project_url"] = data["url"]
    return data


class ArchLoader(PackageLoader[ArchPackageInfo]):
    visit_type = "arch"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        artifacts: List[Dict[str, Any]],
        arch_metadata: List[Dict[str, Any]],
        **kwargs,
    ):

        super().__init__(storage=storage, url=url, **kwargs)
        self.url = url
        self.artifacts: Dict[str, Dict] = {
            artifact["version"]: artifact for artifact in artifacts
        }
        self.arch_metadata: Dict[str, Dict] = {
            metadata["version"]: metadata for metadata in arch_metadata
        }

    def get_versions(self) -> Sequence[str]:
        """Get all released versions of an Arch Linux package

        Returns:
            A sequence of versions

            Example::

                ["0.1.1", "0.10.2"]
        """
        versions = list(self.artifacts.keys())
        versions.sort(key=LooseVersion)
        return versions

    def get_default_version(self) -> str:
        """Get the newest release version of an Arch Linux package

        Returns:
            A string representing a version

            Example::

                "0.1.2"
        """
        return self.get_versions()[-1]

    def get_package_info(self, version: str) -> Iterator[Tuple[str, ArchPackageInfo]]:
        """Get release name and package information from version

        Args:
            version: arch version (e.g: "0.1.0")

        Returns:
            Iterator of tuple (release_name, p_info)
        """
        artifact = self.artifacts[version]
        metadata = self.arch_metadata[version]
        assert version == artifact["version"] == metadata["version"]

        p_info = ArchPackageInfo(
            name=metadata["name"],
            filename=artifact["filename"],
            url=artifact["url"],
            version=version,
            last_modified=metadata["last_modified"],
        )
        yield release_name(version, artifact["filename"]), p_info

    def build_release(
        self, p_info: ArchPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        intrinsic_metadata = extract_intrinsic_metadata(Path(uncompressed_path))
        author = Person.from_fullname(intrinsic_metadata["packager"].encode())
        description = intrinsic_metadata["pkgdesc"]

        message = (
            f"Synthetic release for Arch Linux source package {p_info.name} "
            f"version {p_info.version}\n\n"
            f"{description}\n"
        )
        return Release(
            name=p_info.version.encode(),
            author=author,
            date=TimestampWithTimezone.from_iso8601(p_info.last_modified),
            message=message.encode(),
            target_type=ObjectType.DIRECTORY,
            target=directory,
            synthetic=True,
        )
