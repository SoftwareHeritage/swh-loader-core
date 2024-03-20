# Copyright (C) 2021-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import logging
import os
import shutil
from subprocess import PIPE, run
from typing import Any, Dict, Iterator, List, Optional, Tuple

import attr

from swh.loader.core.utils import cached_method
from swh.loader.package.loader import (
    BasePackageInfo,
    PackageLoader,
    RawExtrinsicMetadataCore,
)
from swh.model.model import (
    MetadataAuthority,
    MetadataAuthorityType,
    ObjectType,
    Person,
    Release,
    Sha1Git,
)
from swh.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


@attr.s
class OpamPackageInfo(BasePackageInfo):
    author = attr.ib(type=Person)
    committer = attr.ib(type=Person)


def opam() -> str:
    """Get the path to the opam executable.

    Raises:
      EnvironmentError if no opam executable is found
    """
    ret = shutil.which("opam")
    if not ret:
        raise EnvironmentError("No opam executable found in path {os.environ['PATH']}")

    return ret


class OpamLoader(PackageLoader[OpamPackageInfo]):
    """Load all versions of a given package in a given opam repository.

    The state of the opam repository is stored in a directory called an opam root. This
    folder is a requisite for the opam binary to actually list information on package.
    It will be automatically initialized or updated if it does not exist or if an opam
    repository must be added to the default switch.

    The remaining ingestion uses the opam binary to give the versions of the given
    package. Then, for each version, the loader uses the opam binary to list the tarball
    url to fetch and ingest.

    """

    visit_type = "opam"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        opam_root: str,
        opam_instance: str,
        opam_url: str,
        opam_package: str,
        **kwargs: Any,
    ):
        super().__init__(storage=storage, url=url, **kwargs)

        self.opam_root = opam_root
        self.opam_instance = opam_instance
        self.opam_url = opam_url
        self.opam_package = opam_package

    def get_package_dir(self) -> str:
        return (
            f"{self.opam_root}/repo/{self.opam_instance}/packages/{self.opam_package}"
        )

    def get_package_name(self, version: str) -> str:
        return f"{self.opam_package}.{version}"

    def get_package_file(self, version: str) -> str:
        return f"{self.get_package_dir()}/{self.get_package_name(version)}/opam"

    def get_metadata_authority(self):
        return MetadataAuthority(type=MetadataAuthorityType.FORGE, url=self.opam_url)

    def _opam_init(self):
        repo_path = os.path.join(self.opam_root, "repo", self.opam_instance)
        # opam >= 2.1 bundles packages metadata in a tarball
        if not os.path.exists(repo_path) and not os.path.exists(repo_path + ".tar.gz"):
            # perform opam init if repository cannot be found in opam root
            if not os.path.exists(self.opam_root) or not os.listdir(self.opam_root):
                # opam root is missing or empty, do a full init
                logger.debug(
                    "Initializing opam root with %s repository", self.opam_instance
                )
                run(
                    [
                        opam(),
                        "init",
                        "--reinit",
                        "--bare",
                        "--no-setup",
                        "--root",
                        self.opam_root,
                        self.opam_instance,
                        self.opam_url,
                    ],
                    check=True,
                )
            else:
                # opam root exists and is populated, we just add another repository in it
                # if it's already setup, it's a noop
                logger.debug("Adding %s repository to opam root", self.opam_instance)
                run(
                    [
                        opam(),
                        "repository",
                        "add",
                        "--set-default",
                        "--root",
                        self.opam_root,
                        self.opam_instance,
                        self.opam_url,
                    ],
                    check=True,
                )
        # for production loaders, no need to initialize the opam root
        # folder. It must be present though so check for it, if not present, raise
        if not os.path.isfile(os.path.join(self.opam_root, "config")):
            # so if not correctly setup, raise immediately
            raise ValueError("Invalid opam root")

    @cached_method
    def _compute_versions(self) -> List[str]:
        """Compute the versions using opam internals

        Raises:
            ValueError in case the lister is not able to determine the list of versions

        Returns:
            The list of versions for the package

        """
        versions_str = self.get_enclosed_single_line_field("all-versions", version=None)
        if not versions_str:
            raise ValueError(
                f"can't get versions for package {self.opam_package} "
                f"(at url {self.origin.url})"
            )
        return versions_str.split()

    def get_versions(self) -> List[str]:
        """First initialize the opam root directory if needed then start listing the
        package versions.

        Raises:
            ValueError in case the lister is not able to determine the list of
            versions or if the opam root directory is invalid.

        """
        self._opam_init()
        return self._compute_versions()

    def get_default_version(self) -> str:
        """Return the most recent version of the package as default."""
        return self._compute_versions()[-1]

    def _opam_show_args(self, version: Optional[str]):
        package = self.get_package_name(version) if version else self.opam_package

        return [
            opam(),
            "show",
            "--color",
            "never",
            "--safe",
            "--normalise",
            "--root",
            self.opam_root,
            package,
        ]

    def get_enclosed_single_line_field(
        self, field: str, version: Optional[str]
    ) -> Optional[str]:
        result = run(
            self._opam_show_args(version) + ["--field", field],
            check=True,
            stdout=PIPE,
            text=True,
        )

        lines = result.stdout.splitlines()

        # Sanitize the result if any (remove trailing \n and enclosing ")
        return lines[0].strip().strip('"') if lines else None

    def get_enclosed_fields(
        self, fields: List[str], version: Optional[str]
    ) -> Dict[str, str]:
        result = run(
            self._opam_show_args(version) + ["--field", ",".join(fields)],
            check=True,
            stdout=PIPE,
            text=True,
        )

        ret = {}
        for line in result.stdout.splitlines():
            line_split = line.split(maxsplit=1)
            if len(line_split) > 1:
                ret[line_split[0]] = line_split[1].strip().strip('"')
        return ret

    def get_package_info(self, version: str) -> Iterator[Tuple[str, OpamPackageInfo]]:
        fields = self.get_enclosed_fields(
            ["url.src:", "url.checksum:", "authors:", "maintainer:"], version
        )
        url = fields.get("url.src:")
        if not url:
            raise ValueError(
                f"can't get field url.src: for version {version} of package"
                f" {self.opam_package} (at url {self.origin.url}) from `opam show`"
            )

        checksums_str = fields.get("url.checksum:")
        checksums = {}
        if checksums_str:
            for c in checksums_str.strip("[]").split(" "):
                algo, hash = c.strip('"').split("=")
                checksums[algo] = hash

        authors_field = fields.get("authors:")
        fullname = b"" if authors_field is None else str.encode(authors_field)
        author = Person.from_fullname(fullname)

        maintainer_field = fields.get("maintainer:")
        fullname = b"" if maintainer_field is None else str.encode(maintainer_field)
        committer = Person.from_fullname(fullname)

        metadata = run(
            self._opam_show_args(version) + ["--raw"], check=True, stdout=PIPE
        ).stdout

        yield self.get_package_name(version), OpamPackageInfo(
            url=url,
            filename=None,
            author=author,
            committer=committer,
            version=version,
            directory_extrinsic_metadata=[
                RawExtrinsicMetadataCore(
                    metadata=metadata,
                    format="opam-package-definition",
                )
            ],
            checksums=checksums,
        )

    def build_release(
        self,
        p_info: OpamPackageInfo,
        uncompressed_path: str,
        directory: Sha1Git,
    ) -> Optional[Release]:
        msg = (
            f"Synthetic release for OPAM source package {self.opam_package} "
            f"version {p_info.version}\n"
        )
        return Release(
            name=p_info.version.encode(),
            author=p_info.author,
            message=msg.encode(),
            date=None,
            target=directory,
            target_type=ObjectType.DIRECTORY,
            synthetic=True,
        )
