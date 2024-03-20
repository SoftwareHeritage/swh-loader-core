# Copyright (C) 2022-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import logging
import os
import string
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

import attr
from packaging.version import parse as parse_version

from swh.loader.core.utils import get_url_body, release_name
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
class RubyGemsPackageInfo(BasePackageInfo):
    name = attr.ib(type=str)
    """Name of the package"""

    version = attr.ib(type=str)
    """Current version"""

    built_at = attr.ib(type=Optional[TimestampWithTimezone])
    """Version build date"""

    authors = attr.ib(type=List[Person])
    """Authors"""

    sha256 = attr.ib(type=str)
    """Extid as sha256"""

    MANIFEST_FORMAT = string.Template(
        "name $name\nshasum $sha256\nurl $url\nversion $version\nlast_update $built_at"
    )
    EXTID_TYPE = "rubygems-manifest-sha256"
    EXTID_VERSION = 0


class RubyGemsLoader(PackageLoader[RubyGemsPackageInfo]):
    """Load ``.gem`` files from ``RubyGems.org`` into the SWH archive."""

    visit_type = "rubygems"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        artifacts: List[Dict[str, Any]],
        rubygem_metadata: List[Dict[str, Any]],
        max_content_size: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(storage, url, max_content_size=max_content_size, **kwargs)
        # Lister URLs are in the ``https://rubygems.org/gems/{pkgname}`` format
        assert url.startswith("https://rubygems.org/gems/"), (
            "Expected rubygems.org url, got '%s'" % url
        )
        # Convert list of artifacts and rubygem_metadata to a mapping of version
        self.artifacts: Dict[str, Dict] = {
            artifact["version"]: artifact for artifact in artifacts
        }
        self.rubygem_metadata: Dict[str, Dict] = {
            data["version"]: data for data in rubygem_metadata
        }

    def get_versions(self) -> Sequence[str]:
        """Return all versions sorted for the gem being loaded"""
        versions = list(self.artifacts.keys())
        versions.sort(key=parse_version)
        return versions

    def get_default_version(self) -> str:
        """Get the newest release version of a gem"""
        return self.get_versions()[-1]

    def get_metadata_authority(self):
        return MetadataAuthority(
            type=MetadataAuthorityType.FORGE,
            url="https://rubygems.org/",
        )

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
        return super()._load_directory(
            [(source_code_tarball, {})], os.path.join(tmpdir, "data")
        )

    def get_package_info(
        self, version: str
    ) -> Iterator[Tuple[str, RubyGemsPackageInfo]]:
        artifact = self.artifacts[version]
        rubygem_metadata = self.rubygem_metadata[version]
        filename = artifact["filename"]
        gem_name = filename.split(f"-{version}.gem")[0]
        authors = rubygem_metadata["authors"].split(", ")
        checksums = artifact["checksums"]

        # Get extrinsic metadata
        extrinsic_metadata_url = rubygem_metadata["extrinsic_metadata_url"]
        extrinsic_metadata = get_url_body(extrinsic_metadata_url)

        p_info = RubyGemsPackageInfo(
            url=artifact["url"],
            filename=filename,
            version=version,
            built_at=TimestampWithTimezone.from_iso8601(rubygem_metadata["date"]),
            name=gem_name,
            authors=[Person.from_fullname(person.encode()) for person in authors],
            checksums=checksums,  # sha256 checksum
            sha256=checksums["sha256"],  # sha256 for EXTID
            directory_extrinsic_metadata=[
                RawExtrinsicMetadataCore(
                    format="rubygem-release-json",
                    metadata=extrinsic_metadata,
                ),
            ],
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
