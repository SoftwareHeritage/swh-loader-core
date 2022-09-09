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
from swh.loader.package.utils import EMPTY_AUTHOR, release_name
from swh.model.model import ObjectType, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface


@attr.s
class AurPackageInfo(BasePackageInfo):

    name = attr.ib(type=str)
    """Name of the package"""

    version = attr.ib(type=str)
    """Current version"""

    last_modified = attr.ib(type=str)
    """File last modified date as release date"""


def extract_intrinsic_metadata(dir_path: Path) -> Dict[str, Any]:
    """Extract intrinsic metadata from .SRCINFO file at dir_path.

    Each Aur package has a .SRCINFO file at the root of the archive.

    Args:
        dir_path: A directory on disk where a package has been extracted

    Returns:
        A dict mapping
    """
    assert dir_path.exists()
    # top directory from extracted archive is always named with the package name
    (pkgname,) = [elt.name for elt in dir_path.iterdir() if elt.is_dir()]
    srcinfo_path = Path(dir_path, pkgname, ".SRCINFO")
    rex = re.compile(r"^(\w+)\s=\s(.*)$", re.M)
    with srcinfo_path.open("r") as content:
        # Except first and last line, lines may starts with a tab, remove them
        srcinfo = content.read().replace("\t", "")
        parsed = rex.findall(srcinfo)
        data: Dict[str, Any] = {}
        for (k, v) in parsed:
            if k in data:
                if type(data[k]) is not list:
                    data[k] = [data[k]]
                data[k].append(v)
            else:
                data[k] = v
    return data


class AurLoader(PackageLoader[AurPackageInfo]):
    visit_type = "aur"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        artifacts: List[Dict[str, Any]],
        aur_metadata: List[Dict[str, Any]],
        **kwargs,
    ):

        super().__init__(storage=storage, url=url, **kwargs)
        self.url = url
        self.artifacts: Dict[str, Dict] = {
            artifact["version"]: artifact for artifact in artifacts
        }
        self.aur_metadata: Dict[str, Dict] = {
            meta["version"]: meta for meta in aur_metadata
        }

    def get_versions(self) -> Sequence[str]:
        """Get all released versions of an Aur package

        Returns:
            A sequence of versions

            Example::

                ["0.1.1", "0.10.2"]
        """
        versions = list(self.artifacts)
        versions.sort(key=LooseVersion)
        return versions

    def get_default_version(self) -> str:
        """Get the newest release version of an Aur package

        Returns:
            A string representing a version

            Example::

                "0.1.2"
        """
        return self.get_versions()[-1]

    def get_package_info(self, version: str) -> Iterator[Tuple[str, AurPackageInfo]]:
        """Get release name and package information from version

        Args:
            version: aur version (e.g: "0.1.0")

        Returns:
            Iterator of tuple (release_name, p_info)
        """
        artifact = self.artifacts[version]
        assert version == artifact["version"]
        data = self.aur_metadata[version]

        url = artifact["url"]
        filename = artifact["filename"]

        p_info = AurPackageInfo(
            name=data["pkgname"],
            filename=filename,
            url=url,
            version=version,
            last_modified=data["last_update"],
        )
        yield release_name(version, filename), p_info

    def build_release(
        self, p_info: AurPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        intrinsic_metadata = extract_intrinsic_metadata(Path(uncompressed_path))
        author = EMPTY_AUTHOR
        description: str = ""
        assert intrinsic_metadata["pkgdesc"]

        if type(intrinsic_metadata["pkgdesc"]) is list:
            description = "\n".join(intrinsic_metadata["pkgdesc"])
        else:
            description = intrinsic_metadata["pkgdesc"]

        message = (
            f"Synthetic release for Aur source package {p_info.name} "
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
