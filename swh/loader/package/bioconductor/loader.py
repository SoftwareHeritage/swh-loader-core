# Copyright (C) 2023-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from __future__ import annotations

import json
import logging
import string
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple

import attr
from packaging.version import parse as parse_version

from swh.loader.core.utils import cached_method, release_name
from swh.loader.package.cran.loader import extract_intrinsic_metadata, parse_date
from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.model.model import ObjectType, Person, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


@attr.s
class BioconductorPackageInfo(BasePackageInfo):
    name = attr.ib(type=str)
    intrinsic_version = attr.ib(type=str)
    """Intrinsic version of the package, independent from the distribution (e.g. 1.18.0-5)"""
    last_update_date = attr.ib(type=Optional[str], default=None)
    """Last update date of the package. (e.g. 2023-04-25)"""
    checksums_str = attr.ib(type=str, default=None)

    EXTID_TYPE = "bioconductor-md5"
    MANIFEST_FORMAT = string.Template("$name $intrinsic_version $checksums_str")

    @classmethod
    def from_metadata(
        cls, a_metadata: Dict[str, Any], version: str
    ) -> BioconductorPackageInfo:
        filename = a_metadata["tar_url"].split("/")[-1]
        assert filename.endswith(".tar.gz")

        return cls(
            name=a_metadata["package"],  # annotation
            url=a_metadata["tar_url"],  # url of the .tar.gz file
            filename=filename,  # a4_1.46.0.tar.gz
            version=version,  # 3.16/bioc/1.46.0
            intrinsic_version=a_metadata["version"],  # 1.46.0
            last_update_date=a_metadata.get("last_update_date"),  # 2023-04-25 or None
            checksums=a_metadata.get("checksums", {}),  # {"md5": ...} or None
            checksums_str=json.dumps(a_metadata.get("checksums", {}), sort_keys=True),
        )


class BioconductorLoader(PackageLoader[BioconductorPackageInfo]):
    visit_type = "bioconductor"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        packages: Dict[str, Dict[str, Any]],
        **kwargs: Any,
    ):
        """Bioconductor Loader implementation.

        Args:
            url: Origin url (e.g. https://bioconductor.org/packages/a4)
            packages: versioned packages and associated artifacts, example::

              {
                "3.16/bioc/1.46.0": {
                    "package": "a4",
                    "release": "3.16",
                    "tar_url": (
                        "https://bioconductor.org/packages/3.16/bioc"
                        "/src/contrib/a4_1.46.0.tar.gz"
                    ),
                    "version": "1.46.0",
                    "category": "bioc",
                    "last_update_date": "2022-11-01",
                    "checksums": {
                        "md5": "4fe2823df78513c79777d009196856fd"
                    }
                },
                # ...
              }

        """
        super().__init__(storage=storage, url=url, **kwargs)
        self.url = url
        self.packages = packages

    @cached_method
    def get_versions(self) -> Sequence[str]:
        """Sort package versions in ascending order and return them."""
        return list(
            sorted(
                self.packages, key=lambda p: parse_version(self.packages[p]["version"])
            )
        )

    def get_default_version(self) -> str:
        """Get the latest release version of a bioconductor package"""
        return self.get_versions()[-1]

    def get_package_info(
        self, version: str
    ) -> Iterator[Tuple[str, BioconductorPackageInfo]]:
        yield (
            release_name(version),
            BioconductorPackageInfo.from_metadata(self.packages[version], version),
        )

    def build_release(
        self,
        p_info: BioconductorPackageInfo,
        uncompressed_path: str,
        directory: Sha1Git,
    ) -> Optional[Release]:
        msg = (
            f"Synthetic release for Bioconductor source package {p_info.name} "
            f"version {p_info.intrinsic_version}\n"
        )

        metadata = extract_intrinsic_metadata(uncompressed_path)
        date = parse_date(metadata.get("Packaged", "").split(";", 1)[0])
        author = Person.from_fullname(metadata.get("Maintainer", "").encode())

        if date is None and p_info.last_update_date:
            date = TimestampWithTimezone.from_iso8601(p_info.last_update_date)

        return Release(
            name=p_info.intrinsic_version.encode(),
            message=msg.encode(),
            author=author,
            date=date,
            target=directory,
            target_type=ObjectType.DIRECTORY,
            synthetic=True,
        )
