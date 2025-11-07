# Copyright (C) 2021-2025  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from os import path
import string
from typing import Any, Iterator, List, Mapping, Optional, Sequence, Tuple

import attr
from bs4 import BeautifulSoup
import iso8601
import requests
from typing_extensions import TypedDict

from swh.loader.core.utils import EMPTY_AUTHOR, get_url_body, release_name
from swh.loader.exception import NotFound
from swh.loader.package.loader import (
    BasePackageInfo,
    PackageLoader,
    RawExtrinsicMetadataCore,
)
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


class ArtifactDict(TypedDict):
    """Data about a Maven artifact, passed by the Maven Lister."""

    time: str
    """the time of the last update of jar file on the server as an iso8601 date string
    """

    url: str
    """the artifact url to retrieve filename"""

    filename: Optional[str]
    """optionally, the file's name"""

    gid: str
    """artifact's groupId"""

    aid: str
    """artifact's artifactId"""

    version: str
    """artifact's version"""

    base_url: str
    """root URL of the Maven instance"""


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
    base_url = attr.ib(type=str)
    """Root URL of the Maven instance"""

    # default format for maven artifacts
    MANIFEST_FORMAT = string.Template("$gid $aid $version $url $time")

    EXTID_TYPE = "maven-jar"
    EXTID_VERSION = 0

    @classmethod
    def from_metadata(
        cls, a_metadata: ArtifactDict, session: requests.Session
    ) -> MavenPackageInfo:
        time = iso8601.parse_date(a_metadata["time"]).astimezone(tz=timezone.utc)
        url = a_metadata["url"]
        checksums = {}
        for algo in ("sha1", "md5"):
            try:
                checksums[algo] = (
                    get_url_body(url + f".{algo}", session=session)
                    .decode()
                    .split(" ")[0]
                    .rstrip()
                )
                break
            except (requests.HTTPError, NotFound):
                pass
        return cls(
            url=url,
            filename=a_metadata.get("filename") or path.split(url)[-1],
            time=time,
            gid=a_metadata["gid"],
            aid=a_metadata["aid"],
            version=a_metadata["version"],
            base_url=a_metadata["base_url"],
            directory_extrinsic_metadata=[
                RawExtrinsicMetadataCore(
                    format="maven-json",
                    metadata=json.dumps(a_metadata).encode(),
                ),
            ],
            checksums=checksums,
        )


class MavenLoader(PackageLoader[MavenPackageInfo]):
    """Load source code jar origin's artifact files into swh archive"""

    visit_type = "maven"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        artifacts: Sequence[ArtifactDict],
        **kwargs: Any,
    ):
        """Loader constructor.

        For now, this is the lister's task output.
        There is one, and only one, artefact (jar or zip) per version, as guaranteed by
        the Maven coordinates system.

        Args:
            url: Origin url
            artifacts: List of single artifact information

        """
        super().__init__(storage=storage, url=url, **kwargs)
        self.artifacts = artifacts  # assume order is enforced in the lister
        self.version_artifact = {
            jar["version"]: jar for jar in artifacts if jar["version"]
        }

        if artifacts:
            base_urls = {jar["base_url"] for jar in artifacts}
            try:
                (self.base_url,) = base_urls
            except ValueError:
                raise ValueError(
                    "Artifacts originate from more than one Maven instance: "
                    + ", ".join(base_urls)
                ) from None
        else:
            # There is no artifact, so self.metadata_authority won't be called,
            # so self.base_url won't be accessed.
            pass

    def get_versions(self) -> Sequence[str]:
        return list(self.version_artifact)

    def get_metadata_authority(self):
        return MetadataAuthority(type=MetadataAuthorityType.FORGE, url=self.base_url)

    def build_extrinsic_directory_metadata(
        self,
        p_info: MavenPackageInfo,
        release_id: Sha1Git,
        directory_id: Sha1Git,
    ) -> List[RawExtrinsicMetadata]:
        # Rebuild POM URL.
        pom_url = path.dirname(p_info.url)
        pom_url = f"{pom_url}/{p_info.aid}-{p_info.version}.pom"

        r = requests.get(pom_url, allow_redirects=True)
        if r.status_code == 200:
            metadata_pom = r.content
        else:
            metadata_pom = b""

        p_info.directory_extrinsic_metadata.append(
            RawExtrinsicMetadataCore(
                format="maven-pom",
                metadata=metadata_pom,
            )
        )

        return super().build_extrinsic_directory_metadata(
            p_info=p_info,
            release_id=release_id,
            directory_id=directory_id,
        )

    def get_package_info(self, version: str) -> Iterator[Tuple[str, MavenPackageInfo]]:
        a_metadata = self.version_artifact[version]
        rel_name = release_name(a_metadata["version"])
        yield rel_name, MavenPackageInfo.from_metadata(a_metadata, session=self.session)

    def build_release(
        self, p_info: MavenPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        msg = f"Synthetic release for archive at {p_info.url}\n".encode("utf-8")
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

    def download_package(
        self, p_info: MavenPackageInfo, tmpdir: str
    ) -> List[Tuple[str, Mapping]]:
        try:
            return super().download_package(p_info, tmpdir)
        except requests.HTTPError as exc:
            if exc.response.status_code == 404 and "-SNAPSHOT" in exc.response.url:
                # some snapshot version of a maven package can have a jar filename
                # different from the one provided by the maven lister, compute that
                # filename by parsing maven-metadata.xml file if available
                package_file = path.basename(exc.response.url)
                package_base_url = path.dirname(exc.response.url)
                metadata_url = package_base_url + "/maven-metadata.xml"
                try:
                    metadata = get_url_body(metadata_url, session=self.session)
                except Exception:
                    pass
                else:
                    bs = BeautifulSoup(metadata, "xml")
                    real_version = bs.select_one(
                        'classifier:-soup-contains("sources") ~ value'
                    )
                    if real_version:
                        package_version = path.basename(package_base_url)
                        a_metadata = self.version_artifact[package_version]
                        updated_filename = package_file.replace(
                            package_version, real_version.text
                        )
                        updated_package_url = package_base_url + "/" + updated_filename
                        a_metadata["filename"] = updated_filename
                        a_metadata["url"] = updated_package_url
                        a_metadata["version"] = real_version.text
                        self.version_artifact[package_version] = a_metadata
                        info = MavenPackageInfo.from_metadata(
                            a_metadata, session=self.session
                        )
                        p_info.url = info.url
                        p_info.version = info.version
                        p_info.checksums = info.checksums
                        p_info.filename = info.filename
                        p_info.directory_extrinsic_metadata = (
                            info.directory_extrinsic_metadata
                        )
                        return super().download_package(p_info, tmpdir)

            raise exc
