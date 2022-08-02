# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from datetime import datetime
import json
from pathlib import Path
import string
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import attr
from packaging.version import parse as parse_version
import toml

from swh.loader.package.loader import (
    BasePackageInfo,
    PackageLoader,
    RawExtrinsicMetadataCore,
)
from swh.loader.package.utils import EMPTY_AUTHOR, release_name
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


@attr.s
class CratesPackageInfo(BasePackageInfo):

    name = attr.ib(type=str)
    """Name of the package"""

    version = attr.ib(type=str)
    """Current version"""

    sha256 = attr.ib(type=str)
    """Extid as sha256"""

    last_update = attr.ib(type=datetime)
    """Last update as release date"""

    yanked = attr.ib(type=bool)
    """Whether the package is yanked or not"""

    MANIFEST_FORMAT = string.Template(
        "name $name\nshasum $sha256\nurl $url\nversion $version\nlast_update $last_update"
    )
    EXTID_TYPE = "crates-manifest-sha256"
    EXTID_VERSION = 0


def extract_intrinsic_metadata(dir_path: Path) -> Dict[str, Any]:
    """Extract intrinsic metadata from Cargo.toml file at dir_path.

    Each crate archive has a Cargo.toml at the root of the archive.

    Args:
        dir_path: A directory on disk where a Cargo.toml must be present

    Returns:
        A dict mapping from toml parser
    """
    return toml.load(dir_path / "Cargo.toml")


class CratesLoader(PackageLoader[CratesPackageInfo]):
    """Load Crates package origins into swh archive."""

    visit_type = "crates"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        artifacts: List[Dict[str, Any]],
        crates_metadata: List[Dict[str, Any]],
        **kwargs,
    ):
        """Constructor

        Args:

            url:
                Origin url, (e.g. https://crates.io/api/v1/crates/<package_name>)

            artifacts:
                A list of dict listing all existing released versions for a
                package (Usually set with crates lister `extra_loader_arguments`).
                Each line is a dict that should have an `url`
                (where to download package specific version), a `version`, a
                `filename` and a `checksums['sha256']` entry.

                Example::

                    [
                        {
                            "version": <version>,
                            "url": "https://static.crates.io/crates/<package_name>/<package_name>-<version>.crate",
                            "filename": "<package_name>-<version>.crate",
                            "checksums": {
                                "sha256": "<sha256>",
                            },
                        }
                    ]

            crates_metadata:
                Same as previously but for Crates metadata.
                For now it only has one boolean key `yanked`.

                Example::

                    [
                        {
                            "version": "<version>",
                            "yanked": <yanked>,
                        },
                    ]
        """  # noqa
        super().__init__(storage=storage, url=url, **kwargs)
        self.url = url
        self.artifacts: Dict[str, Dict] = {
            artifact["version"]: artifact for artifact in artifacts
        }
        self.crates_metadata: Dict[str, Dict] = {
            data["version"]: data for data in crates_metadata
        }

    def get_versions(self) -> Sequence[str]:
        """Get all released versions of a crate

        Returns:
            A sequence of versions

            Example::

                ["0.1.1", "0.10.2"]
        """
        versions = list(self.artifacts.keys())
        versions.sort(key=parse_version)
        return versions

    def get_default_version(self) -> str:
        """Get the newest release version of a crate

        Returns:
            A string representing a version

            Example::

                "0.1.2"
        """
        return self.get_versions()[-1]

    def get_metadata_authority(self):
        return MetadataAuthority(
            type=MetadataAuthorityType.FORGE,
            url="https://crates.io/",
        )

    def get_package_info(self, version: str) -> Iterator[Tuple[str, CratesPackageInfo]]:
        """Get release name and package information from version

        Args:
            version: crate version (e.g: "0.1.0")

        Returns:
            Iterator of tuple (release_name, p_info)
        """
        artifact = self.artifacts[version].copy()
        filename = artifact["filename"]
        assert artifact["checksums"]["sha256"]
        sha256 = artifact["checksums"]["sha256"]
        package_name = urlparse(self.url).path.split("/")[-1]
        url = artifact["url"]

        crate_metadata = self.crates_metadata[version].copy()
        yanked = crate_metadata["yanked"]
        last_update = datetime.fromisoformat(crate_metadata["last_update"])

        # Remove "version" from artifact to follow "original-artifacts-json" extrinsic
        # metadata format specifications
        # See https://docs.softwareheritage.org/devel/swh-storage/extrinsic-metadata-specification.html#extrinsic-metadata-formats  # noqa: B950
        del artifact["version"]

        p_info = CratesPackageInfo(
            name=package_name,
            filename=filename,
            url=url,
            version=version,
            sha256=sha256,
            checksums={"sha256": sha256},
            yanked=yanked,
            last_update=last_update,
            directory_extrinsic_metadata=[
                RawExtrinsicMetadataCore(
                    format="crates-package-json",
                    metadata=json.dumps([crate_metadata]).encode(),
                ),
            ],
        )
        yield release_name(version, filename), p_info

    def build_release(
        self, p_info: CratesPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:

        # Extract intrinsic metadata from dir_path/Cargo.toml
        dir_path = Path(uncompressed_path, f"{p_info.name}-{p_info.version}")
        i_metadata = extract_intrinsic_metadata(dir_path)

        author = EMPTY_AUTHOR
        authors = i_metadata.get("package", {}).get("authors")
        if authors and isinstance(authors, list):
            # TODO: here we have a list of author, see T3887
            author = Person.from_fullname(authors[0].encode())

        message = (
            f"Synthetic release for Crate source package {p_info.name} "
            f"version {p_info.version}\n"
        )

        return Release(
            name=p_info.version.encode(),
            date=TimestampWithTimezone.from_datetime(p_info.last_update),
            author=author,
            message=message.encode(),
            target_type=ObjectType.DIRECTORY,
            target=directory,
            synthetic=True,
        )
