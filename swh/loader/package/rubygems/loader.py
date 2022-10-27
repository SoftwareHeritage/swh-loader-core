# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import json
import logging
import os
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

import attr

from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.loader.package.utils import cached_method, get_url_body, release_name
from swh.model import from_disk
from swh.model.model import ObjectType, Person, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


@attr.s
class RubyGemsPackageInfo(BasePackageInfo):
    name = attr.ib(type=str)
    """Name of the package"""

    version = attr.ib(type=str)
    """Current version"""

    built_at = attr.ib(type=Optional[TimestampWithTimezone])
    """Version build date"""

    authors = attr.ib(type=List[Person])
    """Authors"""


class RubyGemsLoader(PackageLoader[RubyGemsPackageInfo]):
    """Load ``.gem`` files from ``RubyGems.org`` into the SWH archive."""

    visit_type = "rubygems"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        max_content_size: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(storage, url, max_content_size=max_content_size, **kwargs)
        # Lister URLs are in the ``https://rubygems.org/gems/{pkgname}`` format
        assert url.startswith("https://rubygems.org/gems/"), (
            "Expected rubygems.org url, got '%s'" % url
        )
        self.gem_name = url[len("https://rubygems.org/gems/") :]
        # API docs at ``https://guides.rubygems.org/rubygems-org-api/``
        self.api_base_url = "https://rubygems.org/api/v1"
        # Mapping of version number to corresponding metadata from the API
        self.versions_info: Dict[str, Dict[str, Any]] = {}

    def get_versions(self) -> Sequence[str]:
        """Return all versions for the gem being loaded.

        Also stores the detailed information for each version since everything
        is present in this API call."""
        versions_info = get_url_body(
            f"{self.api_base_url}/versions/{self.gem_name}.json"
        )
        versions = []

        for version_info in json.loads(versions_info):
            number = version_info["number"]
            self.versions_info[number] = version_info
            versions.append(number)

        return versions

    @cached_method
    def get_default_version(self) -> str:
        latest = get_url_body(
            f"{self.api_base_url}/versions/{self.gem_name}/latest.json"
        )
        return json.loads(latest)["version"]

    def _load_directory(
        self, dl_artifacts: List[Tuple[str, Mapping[str, Any]]], tmpdir: str
    ) -> Tuple[str, from_disk.Directory]:
        """Override the directory loading to point it to the actual code.

        Gem files are uncompressed tarballs containing:
            - ``metadata.gz``: the metadata about this gem
            - ``data.tar.gz``: the code and possible binary artifacts
            - ``checksums.yaml.gz``: checksums
        """
        logger.debug("Unpacking gem file to point to the actual code")
        uncompressed_path = self.uncompress(dl_artifacts, dest=tmpdir)
        source_code_tarball = os.path.join(uncompressed_path, "data.tar.gz")

        return super()._load_directory([(source_code_tarball, {})], tmpdir)

    def get_package_info(
        self, version: str
    ) -> Iterator[Tuple[str, RubyGemsPackageInfo]]:

        info = self.versions_info[version]

        authors = info["authors"].split(", ")
        p_info = RubyGemsPackageInfo(
            url=f"https://rubygems.org/downloads/{self.gem_name}-{version}.gem",
            # See format of gem files in ``_load_directory``
            filename=f"{self.gem_name}-{version}.tar",
            version=version,
            built_at=TimestampWithTimezone.from_iso8601(info["built_at"]),
            name=self.gem_name,
            authors=[Person.from_fullname(person.encode()) for person in authors],
        )
        yield release_name(version), p_info

    def build_release(
        self, p_info: RubyGemsPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        msg = (
            f"Synthetic release for RubyGems source package {p_info.name} "
            f"version {p_info.version}\n"
        )

        return Release(
            name=p_info.version.encode(),
            message=msg.encode(),
            date=p_info.built_at,
            # TODO multiple authors (T3887)
            author=p_info.authors[0],
            target_type=ObjectType.DIRECTORY,
            target=directory,
            synthetic=True,
        )
