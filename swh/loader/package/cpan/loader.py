# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple

import attr
import iso8601
from packaging.version import parse as parse_version
import yaml

from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.loader.package.utils import (
    EMPTY_AUTHOR,
    Person,
    cached_method,
    get_url_body,
    release_name,
)
from swh.model.model import ObjectType, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface


@attr.s
class CpanPackageInfo(BasePackageInfo):

    name = attr.ib(type=str)
    """Name of the package"""

    filename = attr.ib(type=str)
    """Archive (tar.gz) file name"""

    version = attr.ib(type=str)
    """Current version"""

    last_modified = attr.ib(type=datetime)
    """File last modified date as release date."""

    author = attr.ib(type=Person)
    """Author"""


def extract_intrinsic_metadata(dir_path: Path) -> Dict[str, Any]:
    """Extract intrinsic metadata from META.json file at dir_path.

    Each Perl package version has a META.json file at the root of the archive,
    or a META.yml for older version.

    See https://perldoc.perl.org/CPAN::Meta for META specifications.

    Args:
        dir_path: A directory on disk where a META.json|.yml can be found

    Returns:
        A dict mapping from yaml parser
    """
    meta_json_path = dir_path / "META.json"
    metadata: Dict[str, Any] = {}
    if meta_json_path.exists():
        metadata = json.loads(meta_json_path.read_text())

    meta_yml_path = dir_path / "META.yml"
    if meta_yml_path.exists():
        metadata = yaml.safe_load(meta_yml_path.read_text())

    return metadata


class CpanLoader(PackageLoader[CpanPackageInfo]):
    visit_type = "cpan"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        **kwargs,
    ):

        super().__init__(storage=storage, url=url, **kwargs)
        self.url = url

    @cached_method
    def info_versions(self) -> Dict:
        """Return the package versions (fetched from
        ``https://fastapi.metacpan.org/v1/release/versions/{pkgname}``)

        Api documentation https://cpan.haskell.org/api
        """
        pkgname = self.url.split("/")[-1]
        url = f"https://fastapi.metacpan.org/v1/release/versions/{pkgname}"
        data = json.loads(get_url_body(url=url, headers={"Accept": "application/json"}))
        return {release["version"]: release for release in data["releases"]}

    def get_versions(self) -> Sequence[str]:
        """Get all released versions of a Perl package

        Returns:
            A sequence of versions

            Example::

                ["0.1.1", "0.10.2"]
        """
        versions = list(self.info_versions().keys())
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
        data = self.info_versions()[version]
        pkgname: str = self.url.split("/")[-1]
        url: str = data["download_url"]
        filename: str = url.split("/")[-1]
        # The api does not provide an explicit timezone, defaults to UTC
        last_modified = iso8601.parse_date(data["date"])

        if "author" in data:
            author = Person.from_fullname(data["author"].encode())
        else:
            author = EMPTY_AUTHOR

        p_info = CpanPackageInfo(
            name=pkgname,
            filename=filename,
            url=url,
            version=version,
            last_modified=last_modified,
            author=author,
        )
        yield release_name(version), p_info

    def build_release(
        self, p_info: CpanPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:

        # Extract intrinsic metadata from uncompressed_path/META.json|.yml
        intrinsic_metadata = extract_intrinsic_metadata(
            Path(uncompressed_path) / f"{p_info.name}-{p_info.version}"
        )

        name: str = intrinsic_metadata["name"]
        assert name == p_info.name
        version: str = str(intrinsic_metadata["version"])
        assert version == p_info.version

        description = intrinsic_metadata["abstract"]

        # author data from http endpoint are less complete than from META
        if "author" in intrinsic_metadata:
            author_data = intrinsic_metadata["author"]
            if type(author_data) is list:
                author = author_data[0]
            else:
                author = author_data
            author = Person.from_fullname(author.encode())
        else:
            author = p_info.author

        message = (
            f"Synthetic release for Perl source package {name} "
            f"version {version}\n\n"
            f"{description}\n"
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
