# Copyright (C) 2022-2025  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import string
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import attr
import iso8601

from swh.loader.core.utils import (
    EMPTY_AUTHOR,
    Person,
    cached_method,
    get_url_body,
    release_name,
)
from swh.loader.package.loader import (
    BasePackageInfo,
    PackageLoader,
    RawExtrinsicMetadataCore,
)
from swh.model.model import (
    MetadataAuthority,
    MetadataAuthorityType,
    ObjectType,
    Release,
    Sha1Git,
    TimestampWithTimezone,
)
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

    sha256_checksum = attr.ib(type=str)

    EXTID_TYPE = "puppet-module-sha256"
    MANIFEST_FORMAT = string.Template("$name $version $filename $sha256_checksum")

    @classmethod
    def from_metadata(
        cls,
        url: str,
        module_name: str,
        filename: str,
        version: str,
        last_modified: datetime,
        extrinsic_metadata: Dict[str, Any],
    ) -> PuppetPackageInfo:

        metadata = extrinsic_metadata.get(version, {})
        dir_extrinsic_metadata = (
            [
                RawExtrinsicMetadataCore(
                    format="puppet-module-json",
                    metadata=json.dumps(metadata).encode(),
                )
            ]
            if metadata
            else []
        )
        checksums = {
            k[5:]: metadata[k] for k in ("file_md5", "file_sha256") if k in metadata
        }

        return cls(
            url=url,
            name=module_name,
            filename=filename,
            version=version,
            last_modified=last_modified,
            sha256_checksum=metadata.get("file_sha256", ""),
            directory_extrinsic_metadata=dir_extrinsic_metadata,
            checksums=checksums,
        )


def extract_intrinsic_metadata(dir_path: Path) -> Dict[str, Any]:
    """Extract intrinsic metadata from metadata.json file at dir_path.

    Each Puppet module version has a metadata.json file at the root of the archive.

    See ``https://puppet.com/docs/puppet/7/modules_metadata.html`` for
    metadata specifications.

    Args:
        dir_path: A directory on disk where a puppet package was unpacked

    Returns:
        A dict mapping from json parser
    """
    meta_json_path = next(dir_path.glob("**/metadata.json"))
    return json.loads(meta_json_path.read_text())


class PuppetLoader(PackageLoader[PuppetPackageInfo]):
    visit_type = "puppet"

    FORGEAPI_BASE_URL = "https://forgeapi.puppet.com"
    METADATA_URL = FORGEAPI_BASE_URL + "/v3/releases?module={module}"

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
        split_url = url.split("/")
        self.module_name = "-".join(split_url[-2:])

    @cached_method
    def extrinsic_metadata(self) -> Dict:
        """Return the project metadata information (fetched from Puppet forge API)"""
        metadata = {}
        url: Optional[str] = self.METADATA_URL.format(module=self.module_name)
        while url:
            page = json.loads(get_url_body(url, session=self.session))
            for release in page["results"]:
                metadata[release["version"]] = release
            url = (
                self.FORGEAPI_BASE_URL + page["pagination"]["next"]
                if page["pagination"]["next"]
                else None
            )
        return metadata

    def get_metadata_authority(self):
        return MetadataAuthority(
            type=MetadataAuthorityType.FORGE,
            url="https://forge.puppet.com/",
        )

    def get_versions(self) -> Sequence[str]:
        """Get all released versions of a Puppet module

        Returns:
            A sequence of versions

            Example::

                ["0.1.1", "0.10.2"]
        """
        return list(self.artifacts)

    def get_package_info(self, version: str) -> Iterator[Tuple[str, PuppetPackageInfo]]:
        """Get release name and package information from version

        Args:
            version: Package version (e.g: "0.1.0")

        Returns:
            Iterator of tuple (release_name, p_info)
        """
        data = self.artifacts[version]
        url = data["url"]
        filename = data["filename"]
        last_modified = iso8601.parse_date(data["last_update"])

        p_info = PuppetPackageInfo.from_metadata(
            url=url,
            module_name=self.module_name,
            filename=filename,
            version=version,
            last_modified=last_modified,
            extrinsic_metadata=self.extrinsic_metadata(),
        )
        yield release_name(version), p_info

    def build_release(
        self, p_info: PuppetPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        # Extract intrinsic metadata from uncompressed_path/{dirname}/metadata.json
        intrinsic_metadata = extract_intrinsic_metadata(Path(uncompressed_path))

        version: str = intrinsic_metadata["version"]
        assert version == p_info.version

        _author = intrinsic_metadata.get("author")
        if isinstance(_author, list) and _author:
            author_name = _author[0]
        else:
            author_name = _author
        author = (
            Person.from_fullname(author_name.encode()) if author_name else EMPTY_AUTHOR
        )

        message = (
            f"Synthetic release for Puppet source package {p_info.name} "
            f"version {version}\n"
        )

        if isinstance(_author, list) and len(_author) > 1:
            message += "\n"
            for person in _author[1:]:
                message += f"Co-authored-by: {person}\n"

        return Release(
            name=version.encode(),
            author=author,
            date=TimestampWithTimezone.from_datetime(p_info.last_modified),
            message=message.encode(),
            target_type=ObjectType.DIRECTORY,
            target=directory,
            synthetic=True,
        )
