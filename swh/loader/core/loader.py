# Copyright (C) 2015-2024 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from abc import ABC, abstractmethod
import datetime
import hashlib
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import (
    Any,
    Callable,
    ContextManager,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    Union,
)
from urllib.parse import urlparse

from requests.exceptions import HTTPError
import sentry_sdk
from tenacity.stop import stop_after_attempt

from swh.core.config import load_from_envvar
from swh.core.statsd import Statsd
from swh.core.tarball import uncompress
from swh.loader.core.metadata_fetchers import CredentialsType, get_fetchers_for_lister
from swh.loader.core.nar import Nar
from swh.loader.core.utils import download as download_orig
from swh.loader.exception import NotFound, UnsupportedChecksumLayout
from swh.model import from_disk, model
from swh.model.hashutil import hash_to_bytes
from swh.model.model import (
    Content,
    Directory,
    ExtID,
    Origin,
    OriginVisit,
    OriginVisitStatus,
    RawExtrinsicMetadata,
    Sha1Git,
    Snapshot,
    SnapshotBranch,
    SnapshotTargetType,
)
from swh.storage import get_storage
from swh.storage.algos.snapshot import snapshot_get_latest
from swh.storage.interface import StorageInterface
from swh.storage.utils import now

logger = logging.getLogger()


DEFAULT_CONFIG: Dict[str, Any] = {
    "max_content_size": 100 * 1024 * 1024,
}

SENTRY_ORIGIN_URL_TAG_NAME = "swh.loader.origin_url"
SENTRY_VISIT_TYPE_TAG_NAME = "swh.loader.visit_type"


def _download(*args, **kwargs):
    # reduce number of request retries to avoid waiting too much time
    return download_orig.retry_with(stop=stop_after_attempt(3))(*args, **kwargs)


class BaseLoader:
    """Base class for (D)VCS loaders (e.g Svn, Git, Mercurial, ...) or PackageLoader (e.g
    PyPI, Npm, CRAN, ...)

    A loader retrieves origin information (git/mercurial/svn repositories, pypi/npm/...
    package artifacts), ingests the contents/directories/revisions/releases/snapshot
    read from those artifacts and send them to the archive through the storage backend.

    The main entry point for the loader is the :func:`load` function.

    2 static methods (:func:`from_config`, :func:`from_configfile`) centralizes and
    eases the loader instantiation from either configuration dict or configuration file.

    Some class examples:

    - :class:`SvnLoader`
    - :class:`GitLoader`
    - :class:`PyPILoader`
    - :class:`NpmLoader`

    Args:
      lister_name: Name of the lister which triggered this load.
        If provided, the loader will try to use the forge's API to retrieve extrinsic
        metadata
      lister_instance_name: Name of the lister instance which triggered this load.
        Must be None iff lister_name is, but it may be the empty string for listers
        with a single instance.

    """

    visit_type: str
    origin: Origin
    loaded_snapshot_id: Optional[Sha1Git]

    parent_origins: Optional[List[Origin]]
    """If the given origin is a "forge fork" (ie. created with the "Fork" button
    of GitHub-like forges), :meth:`build_extrinsic_origin_metadata` sets this to
    a list of origins it was forked from; closest parent first."""

    def __init__(
        self,
        storage: StorageInterface,
        origin_url: str,
        logging_class: Optional[str] = None,
        save_data_path: Optional[str] = None,
        max_content_size: Optional[int] = None,
        lister_name: Optional[str] = None,
        lister_instance_name: Optional[str] = None,
        metadata_fetcher_credentials: CredentialsType = None,
        create_partial_snapshot: bool = False,
    ):
        if lister_name == "":
            raise ValueError("lister_name must not be the empty string")
        if lister_name is None and lister_instance_name is not None:
            raise ValueError(
                f"lister_name is None but lister_instance_name is {lister_instance_name!r}"
            )
        if lister_name is not None and lister_instance_name is None:
            raise ValueError(
                f"lister_instance_name is None but lister_name is {lister_name!r}"
            )

        self.storage = storage
        self.origin = Origin(url=origin_url)
        self.max_content_size = int(max_content_size) if max_content_size else None
        self.lister_name = lister_name
        self.lister_instance_name = lister_instance_name
        self.metadata_fetcher_credentials = metadata_fetcher_credentials or {}
        self.create_partial_snapshot = create_partial_snapshot

        if logging_class is None:
            logging_class = "%s.%s" % (
                self.__class__.__module__,
                self.__class__.__name__,
            )
        self.log = logging.getLogger(logging_class)

        _log = logging.getLogger("requests.packages.urllib3.connectionpool")
        _log.setLevel(logging.WARN)

        sentry_sdk.set_tag(SENTRY_ORIGIN_URL_TAG_NAME, self.origin.url)
        sentry_sdk.set_tag(SENTRY_VISIT_TYPE_TAG_NAME, self.visit_type)

        # possibly overridden in self.prepare method
        self.visit_date = datetime.datetime.now(tz=datetime.timezone.utc)

        self.loaded_snapshot_id = None

        if save_data_path:
            path = save_data_path
            os.stat(path)
            if not os.access(path, os.R_OK | os.W_OK):
                raise PermissionError("Permission denied: %r" % path)

        self.save_data_path = save_data_path

        self.parent_origins = None

        self.statsd = Statsd(
            namespace="swh_loader", constant_tags={"visit_type": self.visit_type}
        )

    @classmethod
    def from_config(
        cls,
        storage: Dict[str, Any],
        overrides: Optional[Dict[str, Any]] = None,
        **extra_kwargs: Any,
    ):
        """Instantiate a loader from a configuration dict.

        This is basically a backwards-compatibility shim for the CLI.

        Args:
          storage: instantiation config for the storage
          overrides: A dict of extra configuration for loaders. Maps fully qualified
            class names (e.g. ``"swh.loader.git.loader.GitLoader"``) to a dict of extra
            keyword arguments to pass to this (and only this) loader.
          extra_kwargs: all extra keyword arguments are passed to all loaders

        Returns:
          the instantiated loader

        """
        # Drop the legacy config keys which aren't used for this generation of loader.
        # Should probably raise a deprecation warning?
        extra_kwargs.pop("celery", None)

        qualified_classname = f"{cls.__module__}.{cls.__name__}"
        my_overrides = (overrides or {}).get(qualified_classname, {})
        kwargs = {**extra_kwargs, **my_overrides}

        # Instantiate the storage
        storage_instance = get_storage(**storage)
        return cls(storage=storage_instance, **kwargs)

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
        return cls.from_config(**config)

    def save_data(self) -> None:
        """Save the data associated to the current load"""
        raise NotImplementedError

    def get_save_data_path(self) -> str:
        """The path to which we archive the loader's raw data"""
        if not hasattr(self, "__save_data_path"):
            year = str(self.visit_date.year)

            assert self.origin
            url = self.origin.url.encode("utf-8")
            origin_url_hash = hashlib.sha1(url).hexdigest()

            path = "%s/sha1:%s/%s/%s" % (
                self.save_data_path,
                origin_url_hash[0:2],
                origin_url_hash,
                year,
            )

            os.makedirs(path, exist_ok=True)
            self.__save_data_path = path

        return self.__save_data_path

    def flush(self) -> Dict[str, int]:
        """Flush any potential buffered data not sent to swh-storage.
        Returns the same value as :meth:`swh.storage.interface.StorageInterface.flush`.
        """
        return self.storage.flush()

    def cleanup(self) -> None:
        """Last step executed by the loader."""
        raise NotImplementedError

    def _store_origin_visit(self) -> None:
        """Store origin and visit references. Sets the self.visit references."""
        assert self.origin
        self.storage.origin_add([self.origin])

        assert isinstance(self.visit_type, str)
        self.visit = list(
            self.storage.origin_visit_add(
                [
                    OriginVisit(
                        origin=self.origin.url,
                        date=self.visit_date,
                        type=self.visit_type,
                    )
                ]
            )
        )[0]

    def prepare(self) -> None:
        """Second step executed by the loader to prepare some state needed by
           the loader.

        Raises
           NotFound exception if the origin to ingest is not found.

        """
        raise NotImplementedError

    def get_origin(self) -> Origin:
        """Get the origin that is currently being loaded.
        self.origin should be set in :func:`prepare_origin`

        Returns:
          dict: an origin ready to be sent to storage by
          :func:`origin_add`.
        """
        assert self.origin
        return self.origin

    def fetch_data(self) -> bool:
        """Fetch the data from the source the loader is currently loading
           (ex: git/hg/svn/... repository).

        Returns:
            a value that is interpreted as a boolean. If True, fetch_data needs
            to be called again to complete loading.

        """
        raise NotImplementedError

    def process_data(self) -> bool:
        """Run any additional processing between fetching and storing the data

        Returns:
            a value that is interpreted as a boolean. If True, :meth:`fetch_data` needs
            to be called again to complete loading. Ignored if :meth:`fetch_data`
            already returned :const:`False`.
        """
        return True

    def store_data(self) -> None:
        """Store fetched and processed data in the storage.

        This should call the `storage.<object>_add` methods, which handle the objects to
        store in the storage.

        """
        raise NotImplementedError

    def load_status(self) -> Dict[str, str]:
        """Detailed loading status.

        Defaults to logging an eventful load.

        Returns: a dictionary that is eventually passed back as the task's
          result to the scheduler, allowing tuning of the task recurrence
          mechanism.
        """
        return {
            "status": "eventful",
        }

    def post_load(self, success: bool = True) -> None:
        """Permit the loader to do some additional actions according to status
        after the loading is done. The flag success indicates the
        loading's status.

        Defaults to doing nothing.

        This is up to the implementer of this method to make sure this
        does not break.

        Args:
            success (bool): the success status of the loading

        """
        pass

    def visit_status(self) -> str:
        """Detailed visit status.

        Defaults to logging a full visit.
        """
        return "full"

    def pre_cleanup(self) -> None:
        """As a first step, will try and check for dangling data to cleanup.
        This should do its best to avoid raising issues.

        """
        pass

    def build_partial_snapshot(self) -> Optional[Snapshot]:
        """When the loader is configured to serialize partial snapshot, this allows the
        loader to give an implementation that builds a partial snapshot. This is used
        when the ingestion is taking multiple calls to :meth:`fetch_data` and
        :meth:`store_data`. Ignored when the loader is not configured to serialize
        partial snapshot.

        """
        return None

    def load(self) -> Dict[str, str]:
        r"""Loading logic for the loader to follow:

        - Store the actual ``origin_visit`` to storage
        - Call :meth:`prepare` to prepare any eventual state
        - Call :meth:`get_origin` to get the origin we work with and store

        - while True:

          - Call :meth:`fetch_data` to fetch the data to store
          - Call :meth:`process_data` to optionally run processing between
            :meth:`fetch_data` and :meth:`store_data`
          - Call :meth:`store_data` to store the data

        - Call :meth:`cleanup` to clean up any eventual state put in place
             in :meth:`prepare` method.

        """
        try:
            with self.statsd_timed("pre_cleanup"):
                self.pre_cleanup()
        except Exception:
            msg = "Cleaning up dangling data failed! Continue loading."
            self.log.warning(msg)
            sentry_sdk.capture_exception()

        self._store_origin_visit()

        assert (
            self.visit.visit
        ), "The method `_store_origin_visit` should set the visit (OriginVisit)"
        self.log.info(
            "Load origin '%s' with type '%s'", self.origin.url, self.visit.type
        )

        try:
            with self.statsd_timed("build_extrinsic_origin_metadata"):
                metadata = self.build_extrinsic_origin_metadata()
            self.load_metadata_objects(metadata)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            # Do not fail the whole task if this is the only failure
            self.log.exception(
                "Failure while loading extrinsic origin metadata.",
                extra={
                    "swh_task_args": [],
                    "swh_task_kwargs": {
                        "origin": self.origin.url,
                        "lister_name": self.lister_name,
                        "lister_instance_name": self.lister_instance_name,
                    },
                },
            )

        total_time_fetch_data = 0.0
        total_time_process_data = 0.0
        total_time_store_data = 0.0

        # Initially not a success, will be True when actually one
        status = "failed"
        success = False

        try:
            with self.statsd_timed("prepare"):
                self.prepare()

            while True:
                t1 = time.monotonic()
                more_data_to_fetch = self.fetch_data()
                t2 = time.monotonic()
                total_time_fetch_data += t2 - t1

                more_data_to_fetch = self.process_data() and more_data_to_fetch
                t3 = time.monotonic()
                total_time_process_data += t3 - t2

                self.store_data()
                t4 = time.monotonic()
                total_time_store_data += t4 - t3

                # At the end of each ingestion loop, if the loader is configured for
                # partial snapshot (see self.create_partial_snapshot) and there are more
                # data to fetch, allows the loader to record an intermediary snapshot of
                # the ingestion. This could help when failing to load large repositories
                # for technical reasons (running out of disk, memory, etc...).
                if more_data_to_fetch and self.create_partial_snapshot:
                    partial_snapshot = self.build_partial_snapshot()
                    if partial_snapshot is not None:
                        self.storage.snapshot_add([partial_snapshot])
                        visit_status = OriginVisitStatus(
                            origin=self.origin.url,
                            visit=self.visit.visit,
                            type=self.visit_type,
                            date=now(),
                            status="partial",
                            snapshot=partial_snapshot.id,
                        )
                        self.storage.origin_visit_status_add([visit_status])

                if not more_data_to_fetch:
                    break

            self.statsd_timing("fetch_data", total_time_fetch_data * 1000.0)
            self.statsd_timing("process_data", total_time_process_data * 1000.0)
            self.statsd_timing("store_data", total_time_store_data * 1000.0)

            status = self.visit_status()
            visit_status = OriginVisitStatus(
                origin=self.origin.url,
                visit=self.visit.visit,
                type=self.visit_type,
                date=now(),
                status=status,
                snapshot=self.loaded_snapshot_id,
            )
            self.storage.origin_visit_status_add([visit_status])
            success = True
            with self.statsd_timed(
                "post_load", tags={"success": success, "status": status}
            ):
                self.post_load()
        except BaseException as e:
            success = False
            if isinstance(e, NotFound):
                status = "not_found"
                task_status = "uneventful"
            else:
                status = "partial" if self.loaded_snapshot_id else "failed"
                task_status = "failed"

            self.log.exception(
                "Loading failure, updating to `%s` status",
                status,
                extra={
                    "swh_task_args": [],
                    "swh_task_kwargs": {
                        "origin": self.origin.url,
                        "lister_name": self.lister_name,
                        "lister_instance_name": self.lister_instance_name,
                    },
                },
            )
            if not isinstance(e, (SystemExit, KeyboardInterrupt, NotFound)):
                sentry_sdk.capture_exception()
            visit_status = OriginVisitStatus(
                origin=self.origin.url,
                visit=self.visit.visit,
                type=self.visit_type,
                date=now(),
                status=status,
                snapshot=self.loaded_snapshot_id,
            )
            self.storage.origin_visit_status_add([visit_status])
            with self.statsd_timed(
                "post_load", tags={"success": success, "status": status}
            ):
                self.post_load(success=success)
            if not isinstance(e, Exception):
                # e derives from BaseException but not Exception; this is most likely
                # SystemExit or KeyboardInterrupt, so we should re-raise it.
                raise
            return {"status": task_status}
        finally:
            with self.statsd_timed(
                "flush", tags={"success": success, "status": status}
            ):
                self.flush()
            with self.statsd_timed(
                "cleanup", tags={"success": success, "status": status}
            ):
                self.cleanup()

        return self.load_status()

    def load_metadata_objects(
        self, metadata_objects: List[RawExtrinsicMetadata]
    ) -> None:
        if not metadata_objects:
            return

        authorities = {mo.authority for mo in metadata_objects}
        self.storage.metadata_authority_add(list(authorities))

        fetchers = {mo.fetcher for mo in metadata_objects}
        self.storage.metadata_fetcher_add(list(fetchers))

        self.storage.raw_extrinsic_metadata_add(metadata_objects)

    def build_extrinsic_origin_metadata(self) -> List[RawExtrinsicMetadata]:
        """Builds a list of full RawExtrinsicMetadata objects, using
        a metadata fetcher returned by :func:`get_fetcher_classes`."""
        if self.lister_name is None:
            self.log.debug("lister_not provided, skipping extrinsic origin metadata")
            return []

        assert (
            self.lister_instance_name is not None
        ), "lister_instance_name is None, but lister_name is not"

        metadata = []

        fetcher_classes = get_fetchers_for_lister(self.lister_name)

        self.statsd_average("metadata_fetchers", len(fetcher_classes))

        for cls in fetcher_classes:
            metadata_fetcher = cls(
                origin=self.origin,
                lister_name=self.lister_name,
                lister_instance_name=self.lister_instance_name,
                credentials=self.metadata_fetcher_credentials,
            )
            with self.statsd_timed(
                "fetch_one_metadata", tags={"fetcher": cls.FETCHER_NAME}
            ):
                metadata.extend(metadata_fetcher.get_origin_metadata())
            if self.parent_origins is None:
                self.parent_origins = metadata_fetcher.get_parent_origins()
                self.statsd_average(
                    "metadata_parent_origins",
                    len(self.parent_origins),
                    tags={"fetcher": cls.FETCHER_NAME},
                )
        self.statsd_average("metadata_objects", len(metadata))

        return metadata

    def statsd_timed(self, name: str, tags: Dict[str, Any] = {}) -> ContextManager:
        """
        Wrapper for :meth:`swh.core.statsd.Statsd.timed`, which uses the standard
        metric name and tags for loaders.
        """
        return self.statsd.timed(
            "operation_duration_seconds", tags={"operation": name, **tags}
        )

    def statsd_timing(self, name: str, value: float, tags: Dict[str, Any] = {}) -> None:
        """
        Wrapper for :meth:`swh.core.statsd.Statsd.timing`, which uses the standard
        metric name and tags for loaders.
        """
        self.statsd.timing(
            "operation_duration_seconds", value, tags={"operation": name, **tags}
        )

    def statsd_average(
        self, name: str, value: Union[int, float], tags: Dict[str, Any] = {}
    ) -> None:
        """Increments both ``{name}_sum`` (by the ``value``) and ``{name}_count``
        (by ``1``), allowing to prometheus to compute the average ``value`` over
        time."""
        self.statsd.increment(f"{name}_sum", value, tags=tags)
        self.statsd.increment(f"{name}_count", tags=tags)


class NodeLoader(BaseLoader, ABC):
    """Common abstract class for :class:`ContentLoader` and :class:`Directoryloader`.

    The "checksums" field is a dictionary of hex hashes on the object retrieved (content
    or directory). When "checksum_layout" is "standard", the checksums are computed on
    the content of the remote file to retrieve itself (as unix cli allows, "sha1sum",
    "sha256sum", ...). When "checksum_layout" is "nar", the checks is delegated to Nar
    class (which does an equivalent hash computation as the `nix store --dump` cli).
    It's actually checksums on the content of the remote artifact retrieved (be it a
    file or an archive). Other "checksum_layout" will raise UnsupportedChecksumLayout.

    The multiple "fallback" urls received are mirror urls only used to fetch the object
    if the main origin is no longer available. Those are not stored.

    Ingestion is considered eventful on the first ingestion. Subsequent load of the same
    object should end up being an uneventful visit (matching snapshot).

    """

    # Bump version when incompatible changes occur:
    # - 20240215: Tarball directory from a leaf class changed the tarball ingestion
    extid_version = 1

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        checksums: Dict[str, str],
        checksums_computation: Optional[str] = None,
        checksum_layout: Optional[str] = None,
        fallback_urls: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(storage, url, **kwargs)
        # We need to use qualified imports here otherwise
        # Sphinx gets lost when handling subclasses. See:
        # https://github.com/sphinx-doc/sphinx/issues/10124
        self.snapshot: Optional[model.Snapshot] = None
        self.checksums = checksums
        # The path to an artifact retrieved locally (e.g. file or directory)
        self.artifact_path: Optional[Path] = None

        # Keep compatibility with the previous name 'checksums_computations'
        if checksum_layout is not None:
            checksum_layout = checksum_layout
        elif checksum_layout is None and checksums_computation is not None:
            # checksum_layout param has priority over the checksums_computation
            # parameter if both are provided
            checksum_layout = checksums_computation
        else:
            # finally, fall back to the previous behavior, defaulting to standard if
            # nothing is provided
            checksum_layout = "standard"

        if checksum_layout not in ("nar", "standard"):
            raise UnsupportedChecksumLayout(
                "Unsupported checksums layout: %s",
                checksum_layout,
            )

        self.checksum_layout = checksum_layout
        fallback_urls_ = fallback_urls or []
        self.mirror_urls: List[str] = [self.origin.url, *fallback_urls_]
        # Ensure content received matched the "standard" checksums received, this
        # contains the checksums when checksum_computations is "standard", it's empty
        # otherwise
        self.standard_hashes = (
            self.checksums if self.checksum_layout == "standard" else {}
        )
        self.log.debug("Loader checksums computation: %s", self.checksum_layout)

    def prepare(self) -> None:
        self.last_snapshot = snapshot_get_latest(
            self.storage,
            self.origin.url,
            visit_type=self.visit_type,
        )

    def load_status(self) -> Dict[str, Any]:
        return {
            "status": (
                "uneventful" if self.last_snapshot == self.snapshot else "eventful"
            )
        }

    def cleanup(self) -> None:
        self.log.debug("cleanup")

    def _load_extids(self, extids: Set[ExtID]) -> None:
        """Load a set of ExtIDs if any."""
        if not extids:
            return
        try:
            self.storage.extid_add(list(extids))
        except Exception as e:
            logger.exception("Failed to load new ExtIDs for %s", self.origin.url)
            sentry_sdk.capture_exception(e)
            # No big deal, it just means the next visit will load the same versions
            # again.

    def _extids(self, node: Union[Content, Directory]) -> Set[ExtID]:
        """Compute the set of ExtIDs for the :term:`node` (e.g. Content of Directory).

        This creates as much ExtID types as there are keys in :data:`self.checksums`
        dict.
        """
        extids: Set[ExtID] = set()
        extid_type: Optional[str] = None
        if self.checksum_layout == "nar":
            extid_type = "nar-%s"
        elif self.checksum_layout == "standard":
            extid_type = "checksum-%s"

        if extid_type:
            checksums = {
                hash_algo: hash_to_bytes(hsh)
                for hash_algo, hsh in self.checksums.items()
            }
            extids = {
                ExtID(
                    extid_type=extid_type % hash_algo,
                    extid=extid,
                    target=node.swhid(),
                    extid_version=self.extid_version,
                )
                for hash_algo, extid in checksums.items()
            }

        return extids

    @abstractmethod
    def fetch_artifact(self) -> Iterator[Path]:
        """This fetches an artifact representation and yields its associated local
        representation (as Path). Depending on the implementation, this may yield
        contents coming from a remote location, or directories coming from tarball, svn
        tree, git tree, hg tree, ...

        Raises
            NotFound if nothing is found;
            ValueError in case of mismatched checksums

        """
        pass

    @abstractmethod
    def process_artifact(self, artifact_path: Path) -> None:
        """Build the DAG objects out of the locally retrieved artifact."""
        pass

    def fetch_data(self) -> bool:
        """Fetch artifact (e.g. content, directory), checks and ingests the DAG objects
        coming from the artifact.

        This iterates over the generator :meth:`fetch_artifact` to retrieve artifact. As
        soon as one is retrieved and pass the checks (e.g. nar checks if the
        "checksum_layout" is "nar"), the method proceeds with the DAG ingestion as
        usual. If the artifact does not pass the check, this tries to retrieve the next
        mirrored artifact. If no artifacts is retrievable, this raises.

        Raises
            NotFound if no artifact is found;
            ValueError in case of mismatched checksums

        """
        errors = []
        for artifact_path in self.fetch_artifact():
            if self.checksum_layout == "nar":
                # hashes are not "standard", so we need an extra check to happen on the
                # artifact retrieved. We also want to exclude any vcs (.git, .svn, ...)
                # metadata which would impact hash computation if present.

                visit_type_split = set(self.visit_type.split("-"))
                vcs_types = {"bzr", "git", "hg", "svn"}
                vcs_type = next(iter(visit_type_split & vcs_types), None)

                nar = Nar(
                    list(self.checksums.keys()), exclude_vcs=True, vcs_type=vcs_type
                )
                self.log.debug(
                    "Artifact <%s> with path %s", self.visit_type, artifact_path
                )

                self.log.debug(
                    "Artifact <%s> to check nar hashes: %s",
                    self.visit_type,
                    artifact_path,
                )
                nar.serialize(artifact_path)
                actual_checksums = nar.hexdigest()

                if actual_checksums != self.checksums:
                    errors.append(
                        ValueError(
                            f"Checksum mismatched on <{self.origin.url}>: "
                            f"{actual_checksums} != {self.checksums}"
                        )
                    )
                    self.log.debug(
                        "Mismatched checksums <%s>: continue on next mirror url if any",
                        self.origin.url,
                    )
                    continue

            if artifact_path is not None:
                self.process_artifact(artifact_path)
                return False  # no more data to fetch

        if errors:
            raise errors[0]

        # if we reach here, we did not find any proper tarball, so consider the origin
        # not found
        raise NotFound(f"Unknown origin {self.origin.url}.")

    def store_extids(self, node: Union[Content, Directory]) -> None:
        """Store the checksums provided as extids for :data:`node`.

        This stores as much ExtID types as there are keys in the provided
        :data:`self.checksums` dict.

        """
        if node is not None:
            extids = self._extids(node)
            self._load_extids(extids)


class ContentLoader(NodeLoader):
    """Basic loader for edge case ingestion of url resolving to bare 'content' file.

    A visit ends up in full visit with a snapshot when the artifact is retrieved with
    success, match the checksums provided and is ingested with success in the archive.

    An extid mapping entry is recorded in the extid table. The extid_type depends on the
    checksums' type provided (see :class:`NodeLoader` docstring).

    .. code:

           ExtID(extid_type='[nar|checksums]-sha256',
             extid_version=self.extid_version,
             target='swh:1:cnt:<content-id>',
             target_type='content')

    The output snapshot has the following structure:

    .. code::

       id: <bytes>
       branches:
         HEAD:
           target_type: content
           target: <content-id>

    """

    visit_type = "content"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content: Optional[Content] = None

    def fetch_artifact(self) -> Iterator[Path]:
        """Iterates over the mirror urls to find a content.

        Raises
            NotFound if nothing is found;
            ValueError in case of any error when fetching/computing (length, checksums
            mismatched...)

        """
        errors = []
        found_file_path = False
        for url in self.mirror_urls:
            url_ = urlparse(url)
            self.log.debug(
                "prepare; origin_url=%s fallback=%s scheme=%s path=%s",
                self.origin.url,
                url,
                url_.scheme,
                url_.path,
            )
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    file_path, _ = _download(
                        url, dest=tmpdir, hashes=self.standard_hashes
                    )
                    found_file_path = True
                    yield Path(file_path)
            except ValueError as e:
                errors.append(e)
                self.log.debug(
                    "Mismatched checksums <%s>: continue on next mirror url if any",
                    url,
                )
                continue
            except HTTPError as http_error:
                if http_error.response.status_code == 404:
                    self.log.debug(
                        "Not found '%s', continue on next mirror url if any", url
                    )
                continue

        # To catch 'standard' hash mismatch issues raise by the 'download' method.
        if not found_file_path and errors:
            raise errors[0]

    def process_artifact(self, artifact_path: Path):
        """Build the Content out of the remote artifact retrieved.

        This needs to happen in this method because it's within a context manager block.

        """
        with open(artifact_path, "rb") as content_file:
            self.content = Content.from_data(content_file.read())

    def process_data(self) -> bool:
        """Build Snapshot out of the artifact retrieved."""
        assert self.content is not None
        self.snapshot = Snapshot(
            branches={
                b"HEAD": SnapshotBranch(
                    target=self.content.sha1_git,
                    target_type=SnapshotTargetType.CONTENT,
                ),
            }
        )

        return False  # no more data to process

    def store_data(self) -> None:
        """Store newly retrieved Content and Snapshot."""
        assert self.content is not None
        self.storage.content_add([self.content])
        self.store_extids(self.content)

        assert self.snapshot is not None
        self.storage.snapshot_add([self.snapshot])
        self.loaded_snapshot_id = self.snapshot.id

    def visit_status(self) -> str:
        return "full" if self.content and self.snapshot is not None else "partial"


class BaseDirectoryLoader(NodeLoader):
    """Abstract base Directory Loader for 'tree' ingestion (through any media).

    Implementations should inherit from this class and provide the:

    - required :meth:`fetch_artifact` method to retrieve the Directory (from the proper
      media protocol, e.g. git, svn, hg, ...)

    - optional :meth:`build_snapshot` method to build the Snapshot with the proper
      structure if the default is not enough.

    """

    visit_type = "directory"

    def __init__(
        self,
        *args,
        path_filter: Callable[
            [bytes, bytes, Optional[Iterable[bytes]]], bool
        ] = from_disk.accept_all_paths,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.directory: Optional[from_disk.Directory] = None
        # We need to use qualified imports here otherwise
        # Sphinx gets lost when handling subclasses. See:
        # https://github.com/sphinx-doc/sphinx/issues/10124
        self.cnts: Optional[List[model.Content]] = None
        self.skipped_cnts: Optional[List[model.SkippedContent]] = None
        self.dirs: Optional[List[model.Directory]] = None
        self._path_filter = path_filter

    def path_filter(
        self, path: bytes, name: bytes, entries: Optional[Iterable[bytes]]
    ) -> bool:
        return self._path_filter(path, name, entries)

    def process_artifact(self, artifact_path: Path) -> None:
        """Build the Directory and other DAG objects out of the remote artifact
        retrieved (self.artifact_path).

        This needs to happen in this method because it's within a context manager block.

        """
        self.directory = from_disk.Directory.from_disk(
            path=bytes(artifact_path),
            max_content_length=self.max_content_size,
            path_filter=self.path_filter,
        )
        # Compute the merkle dag from the top-level directory
        self.cnts, self.skipped_cnts, self.dirs = from_disk.iter_directory(
            self.directory
        )

    def build_snapshot(self) -> Snapshot:
        """Build and return the snapshot to store in the archive.

        By default, this builds the snapshot with the structure:

        .. code::

           id: <bytes>
           branches:
             HEAD:
               target_type: directory
               target: <directory-id>

        Other directory loader implementations could override this method to build a
        more specific snapshot.

        """
        assert self.directory is not None
        return Snapshot(
            branches={
                b"HEAD": SnapshotBranch(
                    target=self.directory.hash,
                    target_type=SnapshotTargetType.DIRECTORY,
                ),
            }
        )

    def store_data(self) -> None:
        """Store newly retrieved Content and Snapshot."""
        assert self.skipped_cnts is not None
        self.log.debug("Number of skipped contents: %s", len(self.skipped_cnts))
        self.storage.skipped_content_add(self.skipped_cnts)
        assert self.cnts is not None
        self.log.debug("Number of contents: %s", len(self.cnts))
        self.storage.content_add(self.cnts)
        assert self.dirs is not None
        self.log.debug("Number of directories: %s", len(self.dirs))
        self.storage.directory_add(self.dirs)
        assert self.directory is not None
        self.store_extids(self.directory.to_model())
        self.snapshot = self.build_snapshot()
        self.storage.snapshot_add([self.snapshot])
        self.loaded_snapshot_id = self.snapshot.id

    def visit_status(self):
        return "full" if self.directory and self.snapshot is not None else "partial"


class TarballDirectoryLoader(BaseDirectoryLoader):
    """TarballDirectoryLoader for ingestion of url resolving to a tarball. The tarball
    is uncompressed and checked against its provided checksums (either standard
    checksums or :class:`Nar` checksums).

    A visit ends up in full visit with a snapshot when the artifact is retrieved with
    success, match the checksums provided and is ingested with success in the archive.

    An extid mapping entry is recorded in the extid table. The extid_type depends on the
    checksums' type provided (see :class:`NodeLoader` docstring).

    .. code:

       ExtID(extid_type='[nar|checksums]-sha256',
             extid_version=self.extid_version,
             target='swh:1:dir:<directory-id>',
             target_type='directory')

    The output snapshot has the following structure:

    .. code::

       id: <bytes>
       branches:
         HEAD:
           target_type: directory
           target: <directory-id>

    """

    visit_type = "tarball-directory"

    def fetch_artifact(self) -> Iterator[Path]:
        """Iterates over the mirror urls to find a directory packaged in a tarball.

        Raises
            NotFound if nothing is found;
            ValueError in case of any error when fetching/computing (length, checksums
            mismatched...)

        """
        errors = []
        found_directory_path = False
        for url in self.mirror_urls:
            url_ = urlparse(url)
            self.log.debug(
                "prepare; origin_url=%s fallback=%s scheme=%s path=%s",
                self.origin.url,
                url,
                url_.scheme,
                url_.path,
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    tarball_path, _ = _download(
                        url,
                        tmpdir,
                        hashes=self.standard_hashes,
                        extra_request_headers={"Accept-Encoding": "identity"},
                    )
                except ValueError as e:
                    errors.append(e)
                    self.log.debug(
                        "Mismatched checksums <%s>: continue on next mirror url if any",
                        url,
                    )
                    continue
                except HTTPError as http_error:
                    if http_error.response.status_code == 404:
                        self.log.debug(
                            "Not found <%s>: continue on next mirror url if any", url
                        )
                    continue

                assert tarball_path is not None
                directory_path = Path(tmpdir) / "src"
                directory_path.mkdir(parents=True, exist_ok=True)
                uncompress(tarball_path, dest=str(directory_path))
                self.log.debug("uncompressed path to directory: %s", directory_path)

                if directory_path:
                    found_directory_path = True
                    # Yield the top-level directory as-is
                    yield directory_path
                    # If there is a mismatch between the computed NAR hash and the one
                    # we should obtain, retry its computation by not including single
                    # top level directory if there is such a layout (as nix does).
                    # Check whether a top-level directory exists
                    listing = list(directory_path.iterdir())
                    if len(listing) == 1:
                        # Top-level directory exists, we provide it, nix depends on it
                        yield listing[0]

        # To catch 'standard' hash mismatch issues raise by the 'download' method.
        if not found_directory_path and errors:
            raise errors[0]
