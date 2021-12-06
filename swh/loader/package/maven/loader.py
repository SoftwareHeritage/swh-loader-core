# Copyright (C) 2021  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from datetime import datetime, timezone
import hashlib
import json
import logging
from os import path
import string
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    OrderedDict,
    Sequence,
    Tuple,
)
from urllib.parse import urlparse

import attr
import iso8601
import requests

from swh.loader.package.loader import (
    BasePackageInfo,
    PackageLoader,
    PartialExtID,
    RawExtrinsicMetadataCore,
)
from swh.loader.package.utils import EMPTY_AUTHOR, release_name
from swh.model.model import (
    MetadataAuthority,
    MetadataAuthorityType,
    ObjectType,
    RawExtrinsicMetadata,
    Release,
    Sha1Git,
    TimestampWithTimezone,
)
from swh.storage.interface import StorageInterface

logger = logging.getLogger(__name__)

EXTID_TYPE = "maven-jar"
EXTID_VERSION = 0


@attr.s
class MavenPackageInfo(BasePackageInfo):
    time = attr.ib(type=datetime)
    """Timestamp of the last update of jar file on the server."""
    gid = attr.ib(type=str)
    """Group ID of the maven artifact"""
    aid = attr.ib(type=str)
    """Artifact ID of the maven artifact"""
    version = attr.ib(type=str)
    """Version of the maven artifact"""

    # default format for maven artifacts
    MANIFEST_FORMAT = string.Template("$gid $aid $version $url $time")

    def extid(self, manifest_format: Optional[string.Template] = None) -> PartialExtID:
        """Returns a unique intrinsic identifier of this package info

        ``manifest_format`` allows overriding the class' default MANIFEST_FORMAT"""
        manifest_format = manifest_format or self.MANIFEST_FORMAT
        manifest = manifest_format.substitute(
            {
                "gid": self.gid,
                "aid": self.aid,
                "version": self.version,
                "url": self.url,
                "time": str(self.time),
            }
        )
        return (EXTID_TYPE, EXTID_VERSION, hashlib.sha256(manifest.encode()).digest())

    @classmethod
    def from_metadata(cls, a_metadata: Dict[str, Any]) -> "MavenPackageInfo":
        url = a_metadata["url"]
        filename = a_metadata.get("filename")
        time = iso8601.parse_date(a_metadata["time"])
        time = time.astimezone(tz=timezone.utc)
        gid = a_metadata["gid"]
        aid = a_metadata["aid"]
        version = a_metadata["version"]
        return cls(
            url=url,
            filename=filename or path.split(url)[-1],
            time=time,
            gid=gid,
            aid=aid,
            version=version,
            directory_extrinsic_metadata=[
                RawExtrinsicMetadataCore(
                    format="maven-json", metadata=json.dumps(a_metadata).encode(),
                ),
            ],
        )


class MavenLoader(PackageLoader[MavenPackageInfo]):
    """Load source code jar origin's artifact files into swh archive

    """

    visit_type = "maven"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        artifacts: Sequence[Dict[str, Any]],
        extid_manifest_format: Optional[str] = None,
        max_content_size: Optional[int] = None,
    ):
        f"""Loader constructor.

        For now, this is the lister's task output.
        There is one, and only one, artefact (jar or zip) per version, as guaranteed by
        the Maven coordinates system.

        Args:
            url: Origin url
            artifacts: List of single artifact information with keys:

               - **time**: the time of the last update of jar file on the server
                 as an iso8601 date string

               - **url**: the artifact url to retrieve filename

               - **filename**: optionally, the file's name

               - **gid**: artifact's groupId

               - **aid**: artifact's artifactId

               - **version**: artifact's version

            extid_manifest_format: template string used to format a manifest,
                which is hashed to get the extid of a package.
                Defaults to {MavenPackageInfo.MANIFEST_FORMAT!r}

        """
        super().__init__(storage=storage, url=url, max_content_size=max_content_size)
        self.artifacts = artifacts  # assume order is enforced in the lister
        self.version_artifact: OrderedDict[str, Dict[str, Any]]
        self.version_artifact = OrderedDict(
            {str(jar["version"]): jar for jar in artifacts if jar["version"]}
        )

    def get_versions(self) -> Sequence[str]:
        return list(self.version_artifact.keys())

    def get_default_version(self) -> str:
        # Default version is the last item
        return self.artifacts[-1]["version"]

    def get_metadata_authority(self):
        p_url = urlparse(self.url)
        return MetadataAuthority(
            type=MetadataAuthorityType.FORGE,
            url=f"{p_url.scheme}://{p_url.netloc}/",
            metadata={},
        )

    def build_extrinsic_directory_metadata(
        self, p_info: MavenPackageInfo, release_id: Sha1Git, directory_id: Sha1Git,
    ) -> List[RawExtrinsicMetadata]:
        if not p_info.directory_extrinsic_metadata:
            # If this package loader doesn't write metadata, no need to require
            # an implementation for get_metadata_authority.
            return []

        # Get artifacts
        dir_ext_metadata = p_info.directory_extrinsic_metadata[0]
        a_metadata = json.loads(dir_ext_metadata.metadata)
        aid = a_metadata["aid"]
        version = a_metadata["version"]

        # Rebuild POM URL.
        pom_url = path.dirname(p_info.url)
        pom_url = f"{pom_url}/{aid}-{version}.pom"

        r = requests.get(pom_url, allow_redirects=True)
        if r.status_code == 200:
            metadata_pom = r.content
        else:
            metadata_pom = b""

        return super().build_extrinsic_directory_metadata(
            attr.evolve(
                p_info,
                directory_extrinsic_metadata=[
                    RawExtrinsicMetadataCore(
                        format="maven-pom", metadata=metadata_pom,
                    ),
                    dir_ext_metadata,
                ],
            ),
            release_id=release_id,
            directory_id=directory_id,
        )

    def get_package_info(self, version: str) -> Iterator[Tuple[str, MavenPackageInfo]]:
        a_metadata = self.version_artifact[version]
        yield release_name(a_metadata["version"]), MavenPackageInfo.from_metadata(
            a_metadata
        )

    def build_release(
        self, p_info: MavenPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        msg = f"Synthetic release for archive at {p_info.url}\n".encode("utf-8")
        # time is an iso8601 date
        normalized_time = TimestampWithTimezone.from_datetime(p_info.time)
        return Release(
            name=p_info.version.encode(),
            message=msg,
            date=normalized_time,
            author=EMPTY_AUTHOR,
            target=directory,
            target_type=ObjectType.DIRECTORY,
            synthetic=True,
        )

    def extra_branches(self) -> Dict[bytes, Mapping[str, Any]]:
        last_snapshot = self.last_snapshot()
        return last_snapshot.to_dict()["branches"] if last_snapshot else {}
