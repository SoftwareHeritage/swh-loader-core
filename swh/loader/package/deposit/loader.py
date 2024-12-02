# Copyright (C) 2019-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import datetime
from datetime import timezone
from functools import lru_cache
import json
import logging
import re
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple, Union

import attr
import requests
import sentry_sdk

from swh.core.config import load_from_envvar
from swh.loader.core.loader import DEFAULT_CONFIG
from swh.loader.core.utils import download
from swh.loader.package.loader import (
    BasePackageInfo,
    PackageLoader,
    RawExtrinsicMetadataCore,
)
from swh.model.hashutil import hash_to_hex
from swh.model.model import (
    MetadataAuthority,
    MetadataAuthorityType,
    MetadataFetcher,
    ObjectType,
    Person,
    Release,
    Sha1Git,
    Snapshot,
    TimestampWithTimezone,
)
from swh.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


DepositId = Union[int, str]


def now() -> datetime.datetime:
    return datetime.datetime.now(tz=timezone.utc)


def build_branch_name(version: str) -> str:
    """Build a branch name from a version number.

    There is no "branch name" concept in a deposit, so we artificially create a name
    by prefixing the slugified version number of the repository with `deposit/`.
    This could lead to duplicate branch names, if you need a unique branch name use
    the ``generate_branch_name`` method of the loader as it keeps track of the branches
    names previously issued.

    Args:
        version: a version number

    Returns:
        A branch name
    """
    version = re.sub(r"[^\w\s\.-]", "", version.lower())
    version = re.sub(r"[-\s]+", "-", version).strip("-_.")
    return f"deposit/{version}"


@attr.s
class DepositPackageInfo(BasePackageInfo):
    filename = attr.ib(type=str)  # instead of Optional[str]

    author_date = attr.ib(type=datetime.datetime)
    """codemeta:dateCreated if any, deposit completed_date otherwise"""
    commit_date = attr.ib(type=datetime.datetime)
    """codemeta:datePublished if any, deposit completed_date otherwise"""
    client = attr.ib(type=str)
    id = attr.ib(type=int)
    """Internal ID of the deposit in the deposit DB"""
    collection = attr.ib(type=str)
    """The collection in the deposit; see SWORD specification."""
    author = attr.ib(type=Person)
    committer = attr.ib(type=Person)
    release_notes = attr.ib(type=Optional[str])

    @classmethod
    def from_metadata(
        cls, metadata: Dict[str, Any], url: str, filename: str, version: str
    ) -> "DepositPackageInfo":
        # Note:
        # `date` and `committer_date` are always transmitted by the deposit read api
        # which computes itself the values. The loader needs to use those to create the
        # release.

        raw_metadata: str = metadata["raw_metadata"]
        depo = metadata["deposit"]
        return cls(
            url=url,
            filename=filename,
            version=version,
            author_date=depo["author_date"],
            commit_date=depo["committer_date"],
            client=depo["client"],
            id=depo["id"],
            collection=depo["collection"],
            author=parse_author(depo["author"]),
            committer=parse_author(depo["committer"]),
            release_notes=depo["release_notes"],
            directory_extrinsic_metadata=[
                RawExtrinsicMetadataCore(
                    discovery_date=now(),
                    metadata=raw_metadata.encode(),
                    format="sword-v2-atom-codemeta-v2",
                )
            ],
        )

    def extid(self) -> None:
        # For now, we don't try to deduplicate deposits. There is little point anyway,
        # as it only happens when the exact same tarball was deposited twice.
        return None


class DepositLoader(PackageLoader[DepositPackageInfo]):
    """Load a deposited artifact into swh archive."""

    visit_type = "deposit"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        deposit_id: str,
        deposit_client: "ApiClient",
        default_filename: str = "archive.tar",
        **kwargs: Any,
    ):
        """Constructor

        Args:
            url: Origin url to associate the artifacts/metadata to
            deposit_id: Deposit identity
            deposit_client: Deposit api client

        """
        super().__init__(storage=storage, url=url, **kwargs)

        self.deposit_id = deposit_id
        self.client = deposit_client
        self.default_filename = default_filename
        # Keeps track of the branch names {version: branch_name} to avoid collisions
        self._branches_names: dict[str, str] = dict()

    @classmethod
    def from_configfile(cls, **kwargs: Any):
        """Instantiate a loader from the configuration loaded from the
        SWH_CONFIG_FILENAME envvar, with potential extra keyword arguments if their
        value is not None.

        Args:
            kwargs: kwargs passed to the loader instantiation

        """
        config = dict(load_from_envvar(DEFAULT_CONFIG))
        config.update({k: v for k, v in kwargs.items() if v is not None})
        deposit_client = ApiClient(**config.pop("deposit"))
        return cls.from_config(deposit_client=deposit_client, **config)

    def get_versions(self) -> Sequence[str]:
        """A list of versions from the list of releases.

        Returns:
            A list of versions
        """
        return [
            r["software_version"] for r in self.client.releases_get(self.deposit_id)
        ]

    def get_default_version(self) -> str:
        """The default version is the latest release.

        Returns:
            A version number
        """
        return self.get_versions()[-1]

    def generate_branch_name(self, version: str) -> str:
        """Generate a unique branch name from a version number.

        Previously generated branch names are stored in the ``_branch_names`` property.
        If ``version`` leads to a non unique branch name for this deposit we add a `/n`
        suffix to the branch name, where `n` is a number.

        Example:
            loader.generate_branch_name("ABC")
            # returns "deposit/abc"
            loader.generate_branch_name("abc")
            # returns "deposit/abc/1"
            loader.generate_branch_name("a$b$c")
            # returns "deposit/abc/2"
            loader.generate_branch_name("def")
            # returns "deposit/def"

        Args:
            version: a version number

        Returns:
            A unique branch name
        """
        initial_branch_name = unique_branch_name = build_branch_name(version)
        counter = 0
        while unique_branch_name in self._branches_names.values():
            counter += 1
            unique_branch_name = f"{initial_branch_name}/{counter}"
        self._branches_names[version] = unique_branch_name
        return unique_branch_name

    def get_default_branch_name(self) -> str:
        """The branch name of the default version.

        Returns:
            A branch name
        """
        return self._branches_names[self.get_default_version()]

    def get_metadata_authority(self) -> MetadataAuthority:
        provider = self.client.metadata_get(self.deposit_id)["provider"]
        assert provider["provider_type"] == MetadataAuthorityType.DEPOSIT_CLIENT.value
        return MetadataAuthority(
            type=MetadataAuthorityType.DEPOSIT_CLIENT,
            url=provider["provider_url"],
            metadata={
                "name": provider["provider_name"],
                **(provider["metadata"] or {}),
            },
        )

    def get_metadata_fetcher(self) -> MetadataFetcher:
        tool = self.client.metadata_get(self.deposit_id)["tool"]
        return MetadataFetcher(
            name=tool["name"],
            version=tool["version"],
            metadata=tool["configuration"],
        )

    def get_package_info(
        self, version: str
    ) -> Iterator[Tuple[str, DepositPackageInfo]]:
        """Get package info

        First we look for the version matching the branch name, then we fetch metadata
        from the deposit server and build DepositPackageInfo with it.

        Args:
            version: a branch name.

        Yields:
            Package infos.
        """

        deposit = next(
            d
            for d in self.client.releases_get(self.deposit_id)
            if d["software_version"] == version
        )

        p_info = DepositPackageInfo.from_metadata(
            self.client.metadata_get(deposit["id"]),
            url=deposit["origin_url"],
            filename=self.default_filename,
            version=deposit["software_version"],
        )

        yield self.generate_branch_name(version), p_info

    def download_package(
        self, p_info: DepositPackageInfo, tmpdir: str
    ) -> List[Tuple[str, Mapping]]:
        """Override to allow use of the dedicated deposit client"""
        return [self.client.archive_get(p_info.id, tmpdir, p_info.filename)]

    def build_release(
        self,
        p_info: DepositPackageInfo,
        uncompressed_path: str,
        directory: Sha1Git,
    ) -> Optional[Release]:
        message = (
            f"{p_info.client}: Deposit {p_info.id} in collection {p_info.collection}"
        )

        if p_info.release_notes:
            message += "\n\n" + p_info.release_notes

        if not message.endswith("\n"):
            message += "\n"

        return Release(
            name=p_info.version.encode(),
            message=message.encode(),
            author=p_info.author,
            date=TimestampWithTimezone.from_dict(p_info.author_date),
            target=directory,
            target_type=ObjectType.DIRECTORY,
            synthetic=True,
        )

    def get_extrinsic_origin_metadata(self) -> List[RawExtrinsicMetadataCore]:
        metadata = self.client.metadata_get(self.deposit_id)
        raw_metadata: str = metadata["raw_metadata"]
        origin_metadata = json.dumps(
            {
                "metadata": [raw_metadata],
                "provider": metadata["provider"],
                "tool": metadata["tool"],
            }
        ).encode()
        return [
            RawExtrinsicMetadataCore(
                discovery_date=now(),
                metadata=raw_metadata.encode(),
                format="sword-v2-atom-codemeta-v2",
            ),
            RawExtrinsicMetadataCore(
                discovery_date=now(),
                metadata=origin_metadata,
                format="original-artifacts-json",
            ),
        ]

    def load(self) -> Dict:
        # First making sure the deposit is known on the deposit's RPC server
        # prior to trigger a loading
        try:
            self.client.metadata_get(self.deposit_id)
        except ValueError:
            logger.exception(f"Unknown deposit {self.deposit_id}")
            sentry_sdk.capture_exception()
            return {"status": "failed"}

        # Then usual loading
        return super().load()

    def finalize_visit(
        self,
        status_visit: str,
        snapshot: Optional[Snapshot],
        errors: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        r = super().finalize_visit(
            status_visit=status_visit, snapshot=snapshot, **kwargs
        )
        success = status_visit == "full"

        # Update deposit status
        try:
            if not success:
                self.client.status_update(
                    self.deposit_id,
                    status="failed",
                    errors=errors,
                )
                return r

            if not snapshot:
                logger.error(
                    "No snapshot provided while finalizing deposit %d",
                    self.deposit_id,
                )
                return r

            branches = snapshot.branches
            logger.debug("branches: %s", branches)
            if not branches:
                return r

            default_branch_name = self.get_default_branch_name()
            branch_by_name = branches[default_branch_name.encode()]
            if not branch_by_name or not branch_by_name.target:
                logger.error(
                    "Unable to get branch %s for deposit %d",
                    default_branch_name,
                    self.deposit_id,
                )
                return r
            rel_id = branch_by_name.target
            release = self.storage.release_get([rel_id])[0]

            if not release:
                return r

            # update the deposit's status to success with its
            # release-id and directory-id
            self.client.status_update(
                self.deposit_id,
                status="done",
                release_id=hash_to_hex(rel_id),
                directory_id=hash_to_hex(release.target),
                snapshot_id=r["snapshot_id"],
                origin_url=self.origin.url,
            )
        except Exception:
            logger.exception("Problem when trying to update the deposit's status")
            sentry_sdk.capture_exception()
            return {"status": "failed"}
        return r


def parse_author(author) -> Person:
    """See prior fixme"""
    return Person(
        fullname=author["fullname"].encode("utf-8"),
        name=author["name"].encode("utf-8"),
        email=author["email"].encode("utf-8"),
    )


class ApiClient:
    """Private Deposit Api client"""

    def __init__(self, url, auth: Optional[Mapping[str, str]]):
        self.base_url = url.rstrip("/")
        self.auth = None if not auth else (auth["username"], auth["password"])

    def do(self, method: str, url: str, *args, **kwargs):
        """Internal method to deal with requests, possibly with basic http
           authentication.

        Args:
            method (str): supported http methods as in get/post/put

        Returns:
            The request's execution output

        """
        method_fn = getattr(requests, method)
        if self.auth:
            kwargs["auth"] = self.auth
        return method_fn(url, *args, **kwargs)

    def archive_get(
        self, deposit_id: DepositId, tmpdir: str, filename: str
    ) -> Tuple[str, Dict]:
        """Retrieve deposit's archive artifact locally"""
        url = f"{self.base_url}/{deposit_id}/raw/"
        return download(url, dest=tmpdir, filename=filename, auth=self.auth)

    @lru_cache
    def metadata_get(self, deposit_id: DepositId) -> Dict[str, Any]:
        """Retrieve deposit's metadata artifact as json

        The result of this API call is cached.

        Args:
            deposit_id: a deposit id

        Returns:
            A dict of metadata

        Raises:
            ValueError: something when wrong with the metadata API.
        """
        response = self.do("get", f"{self.base_url}/{deposit_id}/meta/")
        if not response.ok:
            raise ValueError(
                f"Problem when retrieving deposit metadata at {response.url}"
            )
        return response.json()

    @lru_cache
    def releases_get(self, deposit_id: DepositId) -> List[Dict[str, Any]]:
        """Retrieve the list of releases related to this deposit.

        The result of this API call is cached.

        Args:
            deposit_id: a deposit id

        Returns:
            A list of deposits

        Raises:
            ValueError: something when wrong with the releases API.
        """
        response = self.do("get", f"{self.base_url}/{deposit_id}/releases/")
        if not response.ok:
            raise ValueError(
                f"Problem when retrieving deposit releases at {response.url}"
            )
        return response.json()

    def status_update(
        self,
        deposit_id: DepositId,
        status: str,
        errors: Optional[List[str]] = None,
        release_id: Optional[str] = None,
        directory_id: Optional[str] = None,
        snapshot_id: Optional[str] = None,
        origin_url: Optional[str] = None,
    ):
        """Update deposit's information including status, and persistent
        identifiers result of the loading.

        """
        url = f"{self.base_url}/{deposit_id}/update/"
        payload: Dict[str, Any] = {"status": status}
        if release_id:
            payload["release_id"] = release_id
        if directory_id:
            payload["directory_id"] = directory_id
        if snapshot_id:
            payload["snapshot_id"] = snapshot_id
        if origin_url:
            payload["origin_url"] = origin_url
        if errors:
            payload["status_detail"] = {"loading": errors}

        self.do("put", url, json=payload)
