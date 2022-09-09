# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from distutils.version import StrictVersion
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import attr
import toml
from typing_extensions import TypedDict

from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.loader.package.utils import api_info, cached_method, release_name
from swh.model.model import ObjectType, Person, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface


class ExtrinsicPackageMetadata(TypedDict):
    """Data structure for package extrinsic metadata pulled from http api endpoint.

    We set only the keys we need according to what is available when querying
    https://crates.io/api/v1/crates/<name>, where `name` is the name of the crate
    package (see JSON response example at https://crates.io/api/v1/crates/hg-core).

    Usage example:

    .. code-block:: python

        e_metadata = ExtrinsicPackageMetadata(**self.info())

    """  # noqa

    categories: List[Dict[Any, Any]]
    """Related categories"""

    crate: Dict[Any, Any]
    """Crate project information"""

    keywords: List[Any]
    """Keywords"""

    versions: List[Dict[Any, Any]]
    """A list of released versions for a crate"""


class ExtrinsicVersionPackageMetadata(TypedDict):
    """Data structure for specific package version extrinsic metadata, pulled
    from http api endpoint.

    Similar to `ExtrinsicPackageMetadata` in its usage, but we flatten the data
    related to a specific version.
    """

    crate: str
    """The package name"""

    crate_size: int
    """The package size"""

    created_at: str
    """First released at"""

    downloads: str
    """Number of downloads"""

    license: str
    """Package license"""

    num: str
    """Package version"""

    published_by: Dict[Any, Any]
    """Publishers information"""

    updated_at: str
    """Last update"""

    yanked: bool
    """Is that version yanked? (yanked means release-level deprecation)"""


class IntrinsicPackageMetadata(TypedDict):
    """Data structure for specific package version intrinsic metadata.

    Data is extracted from the crate package's .toml file. Then the data of the
    'package' entry is flattened.

    Cargo.toml file content example:

    .. code-block:: toml

        [package]
        name = "hg-core"
        version = "0.0.1"
        authors = ["Georges Racinet <georges.racinet@octobus.net>"]
        description = "Mercurial pure Rust core library, with no assumption on
        Python bindings (FFI)"
        homepage = "https://mercurial-scm.org"
        license = "GPL-2.0-or-later"
        repository = "https://www.mercurial-scm.org/repo/hg"

        [lib]
        name = "hg"
        [dev-dependencies.rand]
        version = "~0.6"

        [dev-dependencies.rand_pcg]
        version = "~0.1"

    :param toml: toml object
    """

    name: str
    """The package name"""

    version: str
    """Package version"""

    authors: List[str]
    """Authors"""

    description: str
    """Package and release description"""

    homepage: str
    """Homepage of the project"""

    license: str
    """Package license"""

    repository: str
    """Source code repository"""


@attr.s
class CratesPackageInfo(BasePackageInfo):

    name = attr.ib(type=str)
    """Name of the package"""

    version = attr.ib(type=str)
    """Current version"""

    e_metadata: Dict[str, Any] = attr.ib(factory=ExtrinsicPackageMetadata)
    """Extrinsic package metadata, common to all versions"""

    e_metadata_version: Dict[str, Any] = attr.ib(
        factory=ExtrinsicVersionPackageMetadata
    )
    """Extrinsic package metadata specific to a version"""

    i_metadata: Dict[str, Any] = attr.ib(factory=IntrinsicPackageMetadata)
    """Intrinsic metadata of the current package version"""


def extract_intrinsic_metadata(dir_path: Path) -> Dict[str, Any]:
    """Extract intrinsic metadata from Cargo.toml file at dir_path.

    Each crate archive has a Cargo.toml at the root of the archive.

    Args:
        dir_path: A directory on disk where a Cargo.toml must be present

    Returns:
        A dict mapping from toml parser
    """
    return toml.load(dir_path / "Cargo.toml")


def extract_author(p_info: CratesPackageInfo) -> Person:
    """Extract package author from intrinsic metadata and return it as a
    `Person` model.

    Args:
        p_info: CratesPackageInfo that should contains i_metadata entries

    Returns:
        Only one author (Person) of the package. Currently limited by internal detail
        of the swh stack (see T3887).
    """
    authors = p_info.i_metadata["authors"]
    fullname = authors[0]  # TODO: here we have a list of author, see T3887
    return Person.from_fullname(fullname.encode())


def extract_description(p_info: CratesPackageInfo) -> str:
    """Extract package description from intrinsic metadata and return it as a
    string.

    Args:
        p_info: CratesPackageInfo that should contains i_metadata and entries

    Returns:
        Package description from metadata.
    """
    return p_info.i_metadata["description"]


class CratesLoader(PackageLoader[CratesPackageInfo]):
    """Load Crates package origins into swh archive."""

    visit_type = "crates"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        artifacts: List[Dict[str, Any]],
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
                (where to download package specific version) and a `version` entry.


                Example::

                    [
                        {
                            "version": <version>,
                            "url": "https://static.crates.io/crates/<package_name>/<package_name>-<version>.crate",
                        }
                    ]
        """  # noqa
        super().__init__(storage=storage, url=url, **kwargs)
        self.url = url
        self.artifacts: Dict[str, Dict] = {
            artifact["version"]: artifact for artifact in artifacts
        }

    @cached_method
    def _raw_info(self) -> bytes:
        """Get crate metadata (fetched from http api endpoint set as self.url)

        Returns:
            Content response as bytes. Content response is a json document.
        """
        return api_info(self.url)

    @cached_method
    def info(self) -> Dict:
        """Parse http api json response and return the crate metadata information
        as a Dict."""
        return json.loads(self._raw_info())

    def get_versions(self) -> Sequence[str]:
        """Get all released versions of a crate

        Returns:
            A sequence of versions

            Example::

                ["0.1.1", "0.10.2"]
        """
        versions = list(self.artifacts.keys())
        versions.sort(key=StrictVersion)
        return versions

    def get_default_version(self) -> str:
        """Get the newest release version of a crate

        Returns:
            A string representing a version

            Example::

                "0.1.2"
        """
        return self.get_versions()[-1]

    def get_package_info(self, version: str) -> Iterator[Tuple[str, CratesPackageInfo]]:
        """Get release name and package information from version

        Args:
            version: crate version (e.g: "0.1.0")

        Returns:
            Iterator of tuple (release_name, p_info)
        """
        artifact = self.artifacts[version]
        filename = artifact["filename"]
        package_name = urlparse(self.url).path.split("/")[-1]
        url = artifact["url"]

        # Get extrinsic metadata from http api
        e_metadata = ExtrinsicPackageMetadata(**self.info())  # type: ignore[misc]

        # Extract crate info for current version (One .crate file for a given version)
        (crate_version,) = [
            crate for crate in e_metadata["versions"] if crate["num"] == version
        ]
        e_metadata_version = ExtrinsicVersionPackageMetadata(  # type: ignore[misc]
            **crate_version
        )

        p_info = CratesPackageInfo(
            name=package_name,
            filename=filename,
            url=url,
            version=version,
            e_metadata=e_metadata,
            e_metadata_version=e_metadata_version,
        )
        yield release_name(version, filename), p_info

    def build_release(
        self, p_info: CratesPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        # Extract intrinsic metadata from dir_path/Cargo.toml
        name = p_info.name
        version = p_info.version
        dir_path = Path(uncompressed_path, f"{name}-{version}")
        i_metadata_raw = extract_intrinsic_metadata(dir_path)
        # Get only corresponding key of IntrinsicPackageMetadata
        i_metadata_keys = [k for k in IntrinsicPackageMetadata.__annotations__.keys()]
        # We use data only from "package" entry
        i_metadata = {
            k: v for k, v in i_metadata_raw["package"].items() if k in i_metadata_keys
        }
        p_info.i_metadata = IntrinsicPackageMetadata(**i_metadata)  # type: ignore[misc]

        author = extract_author(p_info)
        description = extract_description(p_info)
        message = (
            f"Synthetic release for Crate source package {p_info.name} "
            f"version {p_info.version}\n\n"
            f"{description}\n"
        )
        # The only way to get a value for updated_at is through extrinsic metadata
        updated_at = p_info.e_metadata_version.get("updated_at")

        return Release(
            name=version.encode(),
            author=author,
            date=TimestampWithTimezone.from_iso8601(updated_at),
            message=message.encode(),
            target_type=ObjectType.DIRECTORY,
            target=directory,
            synthetic=True,
        )
