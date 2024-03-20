# Copyright (C) 2023-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from __future__ import annotations

import json
import logging
import os
import string
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse

import attr
from packaging.version import parse as parse_version

from swh.loader.core.utils import EMPTY_AUTHOR, get_url_body, release_name
from swh.loader.package.loader import (
    BasePackageInfo,
    PackageLoader,
    RawExtrinsicMetadataCore,
)
from swh.model import from_disk
from swh.model.model import (
    MetadataAuthority,
    MetadataAuthorityType,
    ObjectType,
    Person,
    Release,
    Sha1Git,
    TimestampWithTimezone,
)
from swh.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


@attr.s
class HexPackageInfo(BasePackageInfo):
    name = attr.ib(type=str)
    """Name of the package related to the release"""

    release_url = attr.ib(type=str)
    """URL to the release metadata (e.g.
    https://hex.pm/api/packages/phoenix/releases/1.7.0-rc.2)"""

    inserted_at = attr.ib(type=str)
    """Release insert time in UTC (e.g. 2015-10-11T06:19:35.171799Z)
    This is slightly later than the package inserted_at time"""

    updated_at = attr.ib(type=str)
    """Release update time in UTC (e.g. 2015-10-11T06:19:35.171799Z)
    This is slightly later than the release inserted_at time because of docs build.
    It can only be updated further within 1 hour of the release"""

    author = attr.ib(type=Person)
    """Author of the release"""

    EXTID_TYPE = "hexpm-sha256"
    MANIFEST_FORMAT = string.Template(
        "name $name\nversion $version\nauthor $author\n"
        "inserted_at $inserted_at\nupdated_at $updated_at"
    )


class HexLoader(PackageLoader[HexPackageInfo]):
    visit_type = "hex"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        releases: Dict[str, Any],
        **kwargs: Any,
    ):
        """Load a Hex package from a given hex.pm URL into the SWH archive."""
        super().__init__(storage, url, **kwargs)
        assert url.startswith("https://hex.pm/packages/"), (
            "Expected hex.pm url, got '%s'" % url
        )
        self.url = url
        self.releases = releases

    def get_versions(self) -> Sequence[str]:
        return list(sorted(self.releases, key=parse_version))

    def get_default_version(self) -> str:
        return self.get_versions()[-1]

    def get_metadata_authority(self):
        parsed_url = urlparse(self.url)
        assert parsed_url.scheme == "https", f"Unexpected origin URL: {self.url}"
        assert parsed_url.hostname == "hex.pm", f"Unexpected origin URL: {self.url}"
        return MetadataAuthority(
            type=MetadataAuthorityType.FORGE,
            url="https://hex.pm/",
        )

    def _load_directory(
        self, dl_artifacts: List[Tuple[str, Mapping[str, Any]]], tmpdir: str
    ) -> Tuple[str, from_disk.Directory]:
        """Override the directory loading to include the actual code.

        The Hex tarballs contain the following:
            - :file:`VERSION`
            - :file:`metadata.config`
            - :file:`contents.tar.gz`
            - :file:`CHECKSUM`
        """
        # Doesn't exist before uncompressing the main artifact:
        uncompressed_path = self.uncompress(dl_artifacts, dest=tmpdir)
        source_code_tarball = os.path.join(uncompressed_path, "contents.tar.gz")
        logger.debug(
            "Using %s as the artifact to be uncompressed",
            source_code_tarball,
        )
        return super()._load_directory(
            [(source_code_tarball, {})], os.path.join(tmpdir, "contents")
        )

    def get_package_info(self, version: str) -> Iterator[Tuple[str, HexPackageInfo]]:
        metadata = self.releases[version]

        pkg_name = metadata["name"]
        release_url = metadata["release_url"]
        tarball_url = metadata["tarball_url"]

        filename = tarball_url.split("/")[-1]

        extrinsic_metadata = get_url_body(release_url)
        extrinsic_metadata_json = json.loads(extrinsic_metadata)

        publisher = extrinsic_metadata_json.get("publisher")
        author = (
            Person.from_dict(
                {
                    "name": publisher["username"].encode(),
                    "email": publisher["email"].encode(),
                }
            )
            if publisher is not None
            else EMPTY_AUTHOR
        )

        branch_name = release_name(version)
        p_info = HexPackageInfo(
            name=pkg_name,
            url=tarball_url,
            release_url=release_url,
            filename=filename,
            version=version,
            inserted_at=extrinsic_metadata_json["inserted_at"],
            updated_at=extrinsic_metadata_json["updated_at"],
            author=author,
            directory_extrinsic_metadata=[
                RawExtrinsicMetadataCore(
                    format="hexpm-release-json", metadata=extrinsic_metadata
                )
            ],
            checksums={"sha256": extrinsic_metadata_json["checksum"]},
        )

        yield branch_name, p_info

    def build_release(
        self, p_info: HexPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        msg = (
            f"Synthetic release for Hex source package {p_info.name} "
            f"version {p_info.version}\n"
        )

        return Release(
            name=p_info.version.encode(),
            message=msg.encode(),
            author=p_info.author,
            date=TimestampWithTimezone.from_iso8601(p_info.updated_at),
            target=directory,
            target_type=ObjectType.DIRECTORY,
            synthetic=True,
        )
