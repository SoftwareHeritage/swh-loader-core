# Copyright (C) 2022-2024  The Software Heritage developers
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
import yaml

from swh.loader.core.utils import EMPTY_AUTHOR, Person, get_url_body, release_name
from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.model.model import ObjectType, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface


@attr.s
class CondaPackageInfo(BasePackageInfo):
    name = attr.ib(type=str)
    """Name of the package"""

    filename = attr.ib(type=str)
    """Archive (tar.gz) file name"""

    version = attr.ib(type=str)
    """Complete version and distribution name used as branch name. Ex: 'linux-64/0.1.1-py37'
    """

    release_version = attr.ib(type=str)
    """Version number used as release name. Ex: '0.1.1-py37-linux-64'
    """

    last_modified: Optional[datetime] = attr.ib()
    """File last modified date as release date"""


def extract_intrinsic_metadata(dir_path: Path) -> Dict[str, Any]:
    """Extract intrinsic metadata from file at dir_path.

    Each Conda package version may have an info/about.json file in the
    archive. If missing we try to get metadata from info/recipe/meta.yaml

    See https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/pkg-specs.html?highlight=meta.yaml#info-about-json  # noqa: B950
    for package specifications.

    Args:
        dir_path: A directory on disk where a metadata file can be found

    Returns:
        A dict mapping from yaml parser
    """
    metadata: Dict[str, Any] = {}

    meta_json_path = dir_path / "info" / "about.json"
    meta_yml_path = dir_path / "info" / "recipe" / "meta.yaml"

    if meta_json_path.exists():
        try:
            metadata = json.loads(meta_json_path.read_text())
        except json.JSONDecodeError:
            pass

    if meta_yml_path.exists() and not metadata:
        try:
            metadata = yaml.safe_load(meta_yml_path.read_text())
        except yaml.YAMLError:
            pass

    return metadata


class CondaLoader(PackageLoader[CondaPackageInfo]):
    visit_type = "conda"

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

    def _raw_info(self, url: str, **extra_params) -> bytes:
        return get_url_body(url=url, **extra_params)

    def get_versions(self) -> Sequence[str]:
        """Get all released versions of a Conda package

        Returns:
            A sequence of versions

            Example::

                ["0.1.1", "0.10.2"]
        """
        versions = list(self.artifacts.keys())
        versions.sort(
            key=lambda version_key: parse_version(
                version_key.split("/", 1)[1].split("-", 1)[0]
            )
        )
        return versions

    def get_default_version(self) -> str:
        """Get the newest release version of a Conda package

        Returns:
            A string representing a version

            Example::

                "0.10.2"
        """
        return self.get_versions()[-1]

    def get_package_info(self, version: str) -> Iterator[Tuple[str, CondaPackageInfo]]:
        """Get release name and package information from version

        Args:
            version: Package version (e.g: "0.1.0")

        Returns:
            Iterator of tuple (release_name, p_info)
        """
        data = self.artifacts[version]
        pkgname: str = self.url.split("/")[-1]
        url: str = data["url"]
        filename: str = data["filename"]

        last_modified = None
        if data.get("date"):
            last_modified = iso8601.parse_date(data["date"])

        arch, version_and_build = data["version"].split("/", 1)

        p_info = CondaPackageInfo(
            name=pkgname,
            filename=filename,
            url=url,
            version=version,
            release_version=f"{version_and_build}-{arch}",
            last_modified=last_modified,
            checksums=data["checksums"],
        )
        yield release_name(version), p_info

    def build_release(
        self, p_info: CondaPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        # Extract intrinsic metadata from archive to get description and author
        metadata = extract_intrinsic_metadata(Path(uncompressed_path))

        author = EMPTY_AUTHOR
        maintainers = metadata.get("extra", {}).get("recipe-maintainers")
        if maintainers and isinstance(maintainers, list) and any(maintainers):
            # TODO: here we have a list of author, see T3887
            author = Person.from_fullname(maintainers[0].encode())

        message = (
            f"Synthetic release for Conda source package {p_info.name} "
            f"version {p_info.version}\n"
        )

        last_modified = (
            TimestampWithTimezone.from_datetime(p_info.last_modified)
            if p_info.last_modified
            else None
        )

        return Release(
            name=p_info.release_version.encode(),
            author=author,
            date=last_modified,
            message=message.encode(),
            target_type=ObjectType.DIRECTORY,
            target=directory,
            synthetic=True,
        )
