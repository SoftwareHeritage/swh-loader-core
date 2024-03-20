# Copyright (C) 2022-2024 Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import attr
import iso8601
from packaging.version import parse as parse_version

from swh.loader.core.utils import Person, release_name
from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.model.model import ObjectType, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface


@attr.s
class PuppetPackageInfo(BasePackageInfo):
    name = attr.ib(type=str)
    """Name of the package"""

    filename = attr.ib(type=str)
    """Archive (tar.gz) file name"""

    version = attr.ib(type=str)
    """Current version"""

    last_modified = attr.ib(type=datetime)
    """Module last update date as release date"""


def extract_intrinsic_metadata(dir_path: Path) -> Dict[str, Any]:
    """Extract intrinsic metadata from metadata.json file at dir_path.

    Each Puppet module version has a metadata.json file at the root of the archive.

    See ``https://puppet.com/docs/puppet/7/modules_metadata.html`` for metadata specifications.

    Args:
        dir_path: A directory on disk where a metadata.json file must be present

    Returns:
        A dict mapping from json parser
    """
    meta_json_path = dir_path / "metadata.json"
    metadata: Dict[str, Any] = json.loads(meta_json_path.read_text())
    return metadata


class PuppetLoader(PackageLoader[PuppetPackageInfo]):
    visit_type = "puppet"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        artifacts: List[Dict[str, Any]],
        **kwargs,
    ):
        super().__init__(storage=storage, url=url, **kwargs)
        self.url = url
        self.artifacts: Dict[str, Dict] = {
            artifact["version"]: artifact for artifact in artifacts
        }

    def get_versions(self) -> Sequence[str]:
        """Get all released versions of a Puppet module

        Returns:
            A sequence of versions

            Example::

                ["0.1.1", "0.10.2"]
        """
        versions = list(self.artifacts.keys())
        versions.sort(key=parse_version)
        return versions

    def get_default_version(self) -> str:
        """Get the newest release version of a Puppet module

        Returns:
            A string representing a version

            Example::

                "0.10.2"
        """
        return self.get_versions()[-1]

    def get_package_info(self, version: str) -> Iterator[Tuple[str, PuppetPackageInfo]]:
        """Get release name and package information from version

        Args:
            version: Package version (e.g: "0.1.0")

        Returns:
            Iterator of tuple (release_name, p_info)
        """
        data = self.artifacts[version]
        assert data["filename"].endswith(f"-{version}.tar.gz")
        pkgname: str = data["filename"].split(f"-{version}.tar.gz")[0]
        url: str = data["url"]
        filename: str = data["filename"]
        last_modified: datetime = iso8601.parse_date(data["last_update"])

        p_info = PuppetPackageInfo(
            name=pkgname,
            filename=filename,
            url=url,
            version=version,
            last_modified=last_modified,
            checksums=data["checksums"],
        )
        yield release_name(version), p_info

    def build_release(
        self, p_info: PuppetPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        # compute extracted module directory name
        dirname = p_info.filename.split(".tar.gz")[0]

        # Extract intrinsic metadata from uncompressed_path/{dirname}/metadata.json
        intrinsic_metadata = extract_intrinsic_metadata(
            Path(uncompressed_path) / f"{dirname}"
        )

        version: str = intrinsic_metadata["version"]
        assert version == p_info.version

        author = Person.from_fullname(intrinsic_metadata["author"].encode())

        message = (
            f"Synthetic release for Puppet source package {p_info.name} "
            f"version {version}\n"
        )

        return Release(
            name=version.encode(),
            author=author,
            date=TimestampWithTimezone.from_datetime(p_info.last_modified),
            message=message.encode(),
            target_type=ObjectType.DIRECTORY,
            target=directory,
            synthetic=True,
        )
