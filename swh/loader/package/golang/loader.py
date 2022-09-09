# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import json
import logging
from typing import Iterator, Optional, Sequence, Tuple

import attr

from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.loader.package.utils import EMPTY_AUTHOR, api_info, release_name
from swh.model.model import ObjectType, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


@attr.s
class GolangPackageInfo(BasePackageInfo):
    name = attr.ib(type=str)
    timestamp = attr.ib(type=Optional[TimestampWithTimezone])


class GolangLoader(PackageLoader[GolangPackageInfo]):
    """Load Golang module zip file into SWH archive."""

    visit_type = "golang"
    GOLANG_PKG_DEV_URL = "https://pkg.go.dev"
    GOLANG_PROXY_URL = "https://proxy.golang.org"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        max_content_size: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(storage, url, max_content_size=max_content_size, **kwargs)
        # The lister saves human-usable URLs, so we translate them to proxy URLs
        # for use in the loader.
        # This URL format is detailed in https://go.dev/ref/mod#goproxy-protocol
        assert url.startswith(
            self.GOLANG_PKG_DEV_URL
        ), "Go package URL (%s) not from %s" % (url, self.GOLANG_PKG_DEV_URL)
        self.name = url[len(self.GOLANG_PKG_DEV_URL) + 1 :]
        self.url = url.replace(self.GOLANG_PKG_DEV_URL, self.GOLANG_PROXY_URL)

    def get_versions(self) -> Sequence[str]:
        return api_info(f"{self.url}/@v/list").decode().splitlines()

    def get_default_version(self) -> str:
        latest = api_info(f"{self.url}/@latest")
        return json.loads(latest)["Version"]

    def _raw_info(self, version: str) -> dict:
        url = f"{self.url}/@v/{version}.info"
        return json.loads(api_info(url))

    def get_package_info(self, version: str) -> Iterator[Tuple[str, GolangPackageInfo]]:
        # Encode the name because creating nested folders can become problematic
        encoded_name = self.name.replace("/", "__")
        filename = f"{encoded_name}-{version}.zip"
        timestamp = TimestampWithTimezone.from_iso8601(self._raw_info(version)["Time"])
        p_info = GolangPackageInfo(
            url=f"{self.url}/@v/{version}.zip",
            filename=filename,
            version=version,
            timestamp=timestamp,
            name=self.name,
        )
        yield release_name(version), p_info

    def build_release(
        self, p_info: GolangPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        msg = (
            f"Synthetic release for Golang source package {p_info.name} "
            f"version {p_info.version}\n"
        )

        return Release(
            name=p_info.version.encode(),
            message=msg.encode(),
            date=p_info.timestamp,
            author=EMPTY_AUTHOR,  # Go modules offer very little metadata
            target_type=ObjectType.DIRECTORY,
            target=directory,
            synthetic=True,
        )
