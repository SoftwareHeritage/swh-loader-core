# Copyright (C) 2022-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import base64
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple

import attr
from packaging.version import parse as parse_version
import requests
from requests.structures import CaseInsensitiveDict

from swh.loader.core.utils import (
    DEFAULT_PARAMS,
    EMPTY_AUTHOR,
    Person,
    get_url_body,
    release_name,
)
from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.model.hashutil import hash_to_hex
from swh.model.model import ObjectType, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


@attr.s
class HackagePackageInfo(BasePackageInfo):
    name = attr.ib(type=str)
    """Name of the package"""

    version = attr.ib(type=str)
    """Current version"""

    last_modified = attr.ib(type=str)
    """File last modified date as release date"""

    author = attr.ib(type=Person)
    """Author"""


def extract_intrinsic_metadata(dir_path: Path, pkgname: str) -> Dict[str, Any]:
    """Extract intrinsic metadata from {pkgname}.cabal file at dir_path.

    Each Haskell package version has a {pkgname}.cabal file at the root of the archive.

    See https://cabal.readthedocs.io/en/3.4/cabal-package.html#package-properties for
    package properties specifications.

    Args:
        dir_path: A directory on disk where a {pkgname}.cabal must be present

    Returns:
        A dict mapping with 'name', 'version' and 'author'
    """
    cabal_path = dir_path / f"{pkgname}.cabal"
    content = cabal_path.read_text()

    # replace ':\n' with":" to manage case where key and value are not on the same line
    content = content.replace(":\n", ":")

    rex = r"^(name|version|author):(.+)"
    data = re.findall(rex, content, re.MULTILINE | re.IGNORECASE)
    result = {k.lower().strip(): v.strip() for k, v in data}

    return result


class HackageLoader(PackageLoader[HackagePackageInfo]):
    visit_type = "hackage"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        **kwargs,
    ):
        super().__init__(storage=storage, url=url, **kwargs)
        self.url = url

    def head_url_headers(self, url: str) -> CaseInsensitiveDict:
        """Returns headers from an HEAD requests"""
        response = requests.head(url, **DEFAULT_PARAMS)
        response.raise_for_status()
        return response.headers

    def _raw_info(self, url: str, **extra_params) -> bytes:
        return get_url_body(url=url, **extra_params)

    def info_versions(self) -> Dict:
        """Return the package versions (fetched from
        https://hackage.haskell.org/package/{pkgname})

        Api documentation https://hackage.haskell.org/api
        """
        return json.loads(
            self._raw_info(url=self.url, headers={"Accept": "application/json"})
        )

    def info_revisions(self, url) -> Dict:
        """Return the package version revisions (fetched from
        https://hackage.haskell.org/package/{pkgname}-{version}/revisions/)

        Api documentation https://hackage.haskell.org/api
        """
        return json.loads(
            self._raw_info(url=url, headers={"Accept": "application/json"})
        )

    def get_versions(self) -> Sequence[str]:
        """Get all released versions of an Haskell package

        Returns:
            A sequence of versions

            Example::

                ["0.1.1", "0.10.2"]
        """
        versions = list(self.info_versions().keys())
        versions.sort(key=parse_version)
        return versions

    def get_default_version(self) -> str:
        """Get the newest release version of an Haskell package

        Returns:
            A string representing a version

            Example::

                "0.10.2"
        """
        return self.get_versions()[-1]

    def get_package_info(
        self, version: str
    ) -> Iterator[Tuple[str, HackagePackageInfo]]:
        """Get release name and package information from version

        Args:
            version: Package version (e.g: "0.1.0")

        Returns:
            Iterator of tuple (release_name, p_info)
        """
        pkgname: str = self.url.split("/")[-1]
        url: str = (
            f"https://hackage.haskell.org/package/"
            f"{pkgname}-{version}/{pkgname}-{version}.tar.gz"
        )
        filename: str = url.split("/")[-1]

        # Retrieve version revisions
        revisions_url: str = (
            f"https://hackage.haskell.org/package/{pkgname}-{version}/revisions/"
        )
        revisions = self.info_revisions(revisions_url)
        last_modified = max(item["time"] for item in revisions)

        author = EMPTY_AUTHOR
        # Here we get a 'user' which in most case corresponds to the maintainer.
        # We use that value as 'author' in case it is missing from intrinsic metadata
        if "user" in revisions[-1]:
            author = Person.from_fullname(revisions[-1]["user"].encode())

        # Get md5 checksums with a HEAD request to archive url
        headers = self.head_url_headers(url=url)
        checksums = {}
        if headers and headers.get("Content-MD5"):
            md5 = base64.b64decode(headers["Content-MD5"].encode(), validate=True)
            try:
                checksums = {"md5": hash_to_hex(md5)}
            except UnicodeDecodeError:
                logger.warning("Can not decode md5 checksum %r for %r" % (md5, url))

        p_info = HackagePackageInfo(
            name=pkgname,
            filename=filename,
            url=url,
            version=version,
            last_modified=last_modified,
            author=author,
            checksums=checksums,
        )
        yield release_name(version), p_info

    def build_release(
        self, p_info: HackagePackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        # Extract intrinsic metadata from uncompressed_path/{pkgname}-{version}.cabal
        intrinsic_metadata = extract_intrinsic_metadata(
            Path(uncompressed_path) / f"{p_info.name}-{p_info.version}", p_info.name
        )

        author_str = intrinsic_metadata.get("author")
        author = (
            Person.from_fullname(author_str.encode()) if author_str else p_info.author
        )

        message = (
            f"Synthetic release for Haskell source package {p_info.name} "
            f"version {p_info.version}\n"
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
