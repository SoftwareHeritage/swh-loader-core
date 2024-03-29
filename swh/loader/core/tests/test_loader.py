# Copyright (C) 2018-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import datetime
from functools import partial
import hashlib
import logging
import time
from unittest.mock import MagicMock, call

import pytest

from swh.loader.core.loader import (
    SENTRY_ORIGIN_URL_TAG_NAME,
    SENTRY_VISIT_TYPE_TAG_NAME,
    BaseLoader,
    ContentLoader,
    DirectoryLoader,
)
from swh.loader.core.metadata_fetchers import MetadataFetcherProtocol
from swh.loader.exception import NotFound, UnsupportedChecksumComputation
from swh.loader.tests import assert_last_visit_matches
from swh.model.model import (
    MetadataAuthority,
    MetadataAuthorityType,
    MetadataFetcher,
    Origin,
    RawExtrinsicMetadata,
)
import swh.storage.exc

from .conftest import compute_hashes, compute_nar_hashes, nix_store_missing

ORIGIN = Origin(url="some-url")
PARENT_ORIGIN = Origin(url="base-origin-url")

METADATA_AUTHORITY = MetadataAuthority(
    type=MetadataAuthorityType.FORGE, url="http://example.org/"
)
REMD = RawExtrinsicMetadata(
    target=ORIGIN.swhid(),
    discovery_date=datetime.datetime.now(tz=datetime.timezone.utc),
    authority=METADATA_AUTHORITY,
    fetcher=MetadataFetcher(
        name="test fetcher",
        version="0.0.1",
    ),
    format="test-format",
    metadata=b'{"foo": "bar"}',
)


class DummyLoader:
    """Base Loader to overload and simplify the base class (technical: to avoid repetition
    in other *Loader classes)"""

    visit_type = "git"

    def __init__(self, storage, *args, **kwargs):
        super().__init__(storage, ORIGIN.url, *args, **kwargs)

    def cleanup(self):
        pass

    def prepare(self, *args, **kwargs):
        pass

    def fetch_data(self):
        pass

    def get_snapshot_id(self):
        return None


class DummyBaseLoader(DummyLoader, BaseLoader):
    """Buffered loader will send new data when threshold is reached"""

    def store_data(self):
        pass


class DummyMetadataFetcher:
    SUPPORTED_LISTERS = {"fake-forge"}
    FETCHER_NAME = "fake-forge"

    def __init__(self, origin, credentials, lister_name, lister_instance_name):
        pass

    def get_origin_metadata(self):
        return [REMD]

    def get_parent_origins(self):
        return []


class DummyMetadataFetcherWithFork:
    SUPPORTED_LISTERS = {"fake-forge"}
    FETCHER_NAME = "fake-forge"

    def __init__(self, origin, credentials, lister_name, lister_instance_name):
        pass

    def get_origin_metadata(self):
        return [REMD]

    def get_parent_origins(self):
        return [PARENT_ORIGIN]


def test_types():
    assert isinstance(
        DummyMetadataFetcher(None, None, None, None), MetadataFetcherProtocol
    )
    assert isinstance(
        DummyMetadataFetcherWithFork(None, None, None, None), MetadataFetcherProtocol
    )


def test_base_loader(swh_storage):
    loader = DummyBaseLoader(swh_storage)
    result = loader.load()
    assert result == {"status": "eventful"}


def test_base_loader_with_config(swh_storage):
    loader = DummyBaseLoader(swh_storage, "logger-name")
    result = loader.load()
    assert result == {"status": "eventful"}


def test_base_loader_with_known_lister_name(swh_storage, mocker):
    fetcher_cls = MagicMock(wraps=DummyMetadataFetcher)
    fetcher_cls.SUPPORTED_LISTERS = DummyMetadataFetcher.SUPPORTED_LISTERS
    fetcher_cls.FETCHER_NAME = "fake-forge"
    mocker.patch(
        "swh.loader.core.metadata_fetchers._fetchers", return_value=[fetcher_cls]
    )

    loader = DummyBaseLoader(
        swh_storage, lister_name="fake-forge", lister_instance_name=""
    )
    statsd_report = mocker.patch.object(loader.statsd, "_report")
    result = loader.load()
    assert result == {"status": "eventful"}

    fetcher_cls.assert_called_once()
    fetcher_cls.assert_called_once_with(
        origin=ORIGIN,
        credentials={},
        lister_name="fake-forge",
        lister_instance_name="",
    )
    assert swh_storage.raw_extrinsic_metadata_get(
        ORIGIN.swhid(), METADATA_AUTHORITY
    ).results == [REMD]
    assert loader.parent_origins == []

    assert [
        call("metadata_fetchers_sum", "c", 1, {}, 1),
        call("metadata_fetchers_count", "c", 1, {}, 1),
        call("metadata_parent_origins_sum", "c", 0, {"fetcher": "fake-forge"}, 1),
        call("metadata_parent_origins_count", "c", 1, {"fetcher": "fake-forge"}, 1),
        call("metadata_objects_sum", "c", 1, {}, 1),
        call("metadata_objects_count", "c", 1, {}, 1),
    ] == [c for c in statsd_report.mock_calls if "metadata_" in c[1][0]]
    assert loader.statsd.namespace == "swh_loader"
    assert loader.statsd.constant_tags == {"visit_type": "git"}


def test_base_loader_with_unknown_lister_name(swh_storage, mocker):
    fetcher_cls = MagicMock(wraps=DummyMetadataFetcher)
    fetcher_cls.SUPPORTED_LISTERS = DummyMetadataFetcher.SUPPORTED_LISTERS
    mocker.patch(
        "swh.loader.core.metadata_fetchers._fetchers", return_value=[fetcher_cls]
    )

    loader = DummyBaseLoader(
        swh_storage, lister_name="other-lister", lister_instance_name=""
    )
    result = loader.load()
    assert result == {"status": "eventful"}

    fetcher_cls.assert_not_called()
    with pytest.raises(swh.storage.exc.StorageArgumentException):
        swh_storage.raw_extrinsic_metadata_get(ORIGIN.swhid(), METADATA_AUTHORITY)


def test_base_loader_forked_origin(swh_storage, mocker):
    fetcher_cls = MagicMock(wraps=DummyMetadataFetcherWithFork)
    fetcher_cls.SUPPORTED_LISTERS = DummyMetadataFetcherWithFork.SUPPORTED_LISTERS
    fetcher_cls.FETCHER_NAME = "fake-forge"
    mocker.patch(
        "swh.loader.core.metadata_fetchers._fetchers", return_value=[fetcher_cls]
    )

    loader = DummyBaseLoader(
        swh_storage, lister_name="fake-forge", lister_instance_name=""
    )
    statsd_report = mocker.patch.object(loader.statsd, "_report")
    result = loader.load()
    assert result == {"status": "eventful"}

    fetcher_cls.assert_called_once()
    fetcher_cls.assert_called_once_with(
        origin=ORIGIN,
        credentials={},
        lister_name="fake-forge",
        lister_instance_name="",
    )
    assert swh_storage.raw_extrinsic_metadata_get(
        ORIGIN.swhid(), METADATA_AUTHORITY
    ).results == [REMD]
    assert loader.parent_origins == [PARENT_ORIGIN]

    assert [
        call("metadata_fetchers_sum", "c", 1, {}, 1),
        call("metadata_fetchers_count", "c", 1, {}, 1),
        call("metadata_parent_origins_sum", "c", 1, {"fetcher": "fake-forge"}, 1),
        call("metadata_parent_origins_count", "c", 1, {"fetcher": "fake-forge"}, 1),
        call("metadata_objects_sum", "c", 1, {}, 1),
        call("metadata_objects_count", "c", 1, {}, 1),
    ] == [c for c in statsd_report.mock_calls if "metadata_" in c[1][0]]
    assert loader.statsd.namespace == "swh_loader"
    assert loader.statsd.constant_tags == {"visit_type": "git"}


def test_base_loader_post_load_raise(swh_storage, mocker):
    loader = DummyBaseLoader(swh_storage)
    post_load = mocker.patch.object(loader, "post_load")

    # raise exception in post_load when success is True
    def post_load_method(*args, success=True):
        if success:
            raise Exception("Error in post_load")

    post_load.side_effect = post_load_method

    result = loader.load()
    assert result == {"status": "failed"}

    # ensure post_load has been called twice, once with success to True and
    # once with success to False as the first post_load call raised exception
    assert post_load.call_args_list == [mocker.call(), mocker.call(success=False)]


def test_loader_logger_default_name(swh_storage):
    loader = DummyBaseLoader(swh_storage)
    assert isinstance(loader.log, logging.Logger)
    assert loader.log.name == "swh.loader.core.tests.test_loader.DummyBaseLoader"


def test_loader_logger_with_name(swh_storage):
    loader = DummyBaseLoader(swh_storage, "some.logger.name")
    assert isinstance(loader.log, logging.Logger)
    assert loader.log.name == "some.logger.name"


def test_loader_save_data_path(swh_storage, tmp_path):
    loader = DummyBaseLoader(swh_storage, "some.logger.name.1", save_data_path=tmp_path)
    url = "http://bitbucket.org/something"
    loader.origin = Origin(url=url)
    loader.visit_date = datetime.datetime(year=2019, month=10, day=1)

    hash_url = hashlib.sha1(url.encode("utf-8")).hexdigest()
    expected_save_path = "%s/sha1:%s/%s/2019" % (str(tmp_path), hash_url[0:2], hash_url)

    save_path = loader.get_save_data_path()
    assert save_path == expected_save_path


def _check_load_failure(
    caplog, loader, exc_class, exc_text, status="partial", origin=ORIGIN
):
    """Check whether a failed load properly logged its exception, and that the
    snapshot didn't get referenced in storage"""
    assert isinstance(loader, (ContentLoader, DirectoryLoader))
    for record in caplog.records:
        if record.levelname != "ERROR":
            continue
        assert "Loading failure" in record.message
        assert record.exc_info
        exc = record.exc_info[1]
        assert isinstance(exc, exc_class)
        assert exc_text in exc.args[0]

    # And confirm that the visit doesn't reference a snapshot
    visit = assert_last_visit_matches(loader.storage, origin.url, status)
    if status != "partial":
        assert visit.snapshot is None
        # But that the snapshot didn't get loaded
        assert loader.loaded_snapshot_id is None


@pytest.mark.parametrize("success", [True, False])
def test_loader_timings(swh_storage, mocker, success):
    current_time = time.time()
    mocker.patch("time.monotonic", side_effect=lambda: current_time)
    mocker.patch("swh.core.statsd.monotonic", side_effect=lambda: current_time)

    runtimes = {
        "pre_cleanup": 2.0,
        "build_extrinsic_origin_metadata": 3.0,
        "prepare": 5.0,
        "fetch_data": 7.0,
        "process_data": 11.0,
        "store_data": 13.0,
        "post_load": 17.0,
        "flush": 23.0,
        "cleanup": 27.0,
    }

    class TimedLoader(BaseLoader):
        visit_type = "my-visit-type"

        def __getattribute__(self, method_name):
            if method_name == "visit_status" and not success:

                def crashy():
                    raise Exception("oh no")

                return crashy

            if method_name not in runtimes:
                return super().__getattribute__(method_name)

            def meth(*args, **kwargs):
                nonlocal current_time
                current_time += runtimes[method_name]

            return meth

    loader = TimedLoader(swh_storage, origin_url="http://example.org/hello.git")
    statsd_report = mocker.patch.object(loader.statsd, "_report")
    loader.load()

    if success:
        expected_tags = {
            "post_load": {"success": True, "status": "full"},
            "flush": {"success": True, "status": "full"},
            "cleanup": {"success": True, "status": "full"},
        }
    else:
        expected_tags = {
            "post_load": {"success": False, "status": "failed"},
            "flush": {"success": False, "status": "failed"},
            "cleanup": {"success": False, "status": "failed"},
        }

    # note that this is a list equality, so order of entries in 'runtimes' matters.
    # This is not perfect, but call() objects are not hashable so it's simpler this way,
    # even if not perfect.
    assert statsd_report.mock_calls == [
        call(
            "operation_duration_seconds",
            "ms",
            value * 1000,
            {"operation": key, **expected_tags.get(key, {})},
            1,
        )
        for (key, value) in runtimes.items()
    ]
    assert loader.statsd.namespace == "swh_loader"
    assert loader.statsd.constant_tags == {"visit_type": "my-visit-type"}


class DummyLoaderWithError(DummyBaseLoader):
    def prepare(self, *args, **kwargs):
        raise Exception("error")


def test_loader_sentry_tags_on_error(swh_storage, sentry_events):
    loader = DummyLoaderWithError(swh_storage)
    loader.load()
    sentry_tags = sentry_events[0]["tags"]
    assert sentry_tags.get(SENTRY_ORIGIN_URL_TAG_NAME) == ORIGIN.url
    assert sentry_tags.get(SENTRY_VISIT_TYPE_TAG_NAME) == DummyLoader.visit_type


CONTENT_MIRROR = "https://common-lisp.net"
CONTENT_URL = f"{CONTENT_MIRROR}/project/asdf/archives/asdf-3.3.5.lisp"


def test_content_loader_missing_field(swh_storage):
    """It should raise if the ContentLoader is missing checksums field"""
    origin = Origin(CONTENT_URL)
    with pytest.raises(TypeError, match="missing"):
        ContentLoader(swh_storage, origin.url)


@pytest.mark.parametrize("loader_class", [ContentLoader, DirectoryLoader])
def test_node_loader_missing_field(swh_storage, loader_class):
    """It should raise if the ContentLoader is missing checksums field"""
    with pytest.raises(UnsupportedChecksumComputation):
        loader_class(
            swh_storage,
            CONTENT_URL,
            checksums={"sha256": "irrelevant-for-that-test"},
            checksums_computation="unsupported",
        )


def test_content_loader_404(caplog, swh_storage, requests_mock_datadir, content_path):
    """It should not ingest origin when there is no file to be found (no mirror url)"""
    unknown_origin = Origin(f"{CONTENT_MIRROR}/project/asdf/archives/unknown.lisp")
    loader = ContentLoader(
        swh_storage,
        unknown_origin.url,
        checksums=compute_hashes(content_path),
    )
    result = loader.load()

    assert result == {"status": "uneventful"}

    _check_load_failure(
        caplog,
        loader,
        NotFound,
        "Unknown origin",
        status="not_found",
        origin=unknown_origin,
    )


def test_content_loader_404_with_fallback(
    caplog, swh_storage, requests_mock_datadir, content_path
):
    """It should not ingest origin when there is no file to be found"""
    unknown_origin = Origin(f"{CONTENT_MIRROR}/project/asdf/archives/unknown.lisp")
    fallback_url_ko = f"{CONTENT_MIRROR}/project/asdf/archives/unknown2.lisp"
    loader = ContentLoader(
        swh_storage,
        unknown_origin.url,
        fallback_urls=[fallback_url_ko],
        checksums=compute_hashes(content_path),
    )
    result = loader.load()

    assert result == {"status": "uneventful"}

    _check_load_failure(
        caplog,
        loader,
        NotFound,
        "Unknown origin",
        status="not_found",
        origin=unknown_origin,
    )


@pytest.mark.parametrize("checksum_algo", ["sha1", "sha256", "sha512"])
def test_content_loader_ok_with_fallback(
    checksum_algo,
    caplog,
    swh_storage,
    requests_mock_datadir,
    content_path,
):
    """It should be an eventful visit even when ingesting through mirror url"""
    dead_origin = Origin(f"{CONTENT_MIRROR}/dead-origin-url")
    fallback_url_ok = CONTENT_URL
    fallback_url_ko = f"{CONTENT_MIRROR}/project/asdf/archives/unknown2.lisp"

    loader = ContentLoader(
        swh_storage,
        dead_origin.url,
        fallback_urls=[fallback_url_ok, fallback_url_ko],
        checksums=compute_hashes(content_path, [checksum_algo]),
    )
    result = loader.load()

    assert result == {"status": "eventful"}


compute_content_nar_hashes = partial(compute_nar_hashes, is_tarball=False)


@pytest.mark.skipif(
    nix_store_missing, reason="requires nix-store binary from nix binaries"
)
@pytest.mark.parametrize("checksums_computation", ["standard", "nar"])
def test_content_loader_ok_simple(
    swh_storage, requests_mock_datadir, content_path, checksums_computation
):
    """It should be an eventful visit on a new file, then uneventful"""
    compute_hashes_fn = (
        compute_content_nar_hashes if checksums_computation == "nar" else compute_hashes
    )

    origin = Origin(CONTENT_URL)
    loader = ContentLoader(
        swh_storage,
        origin.url,
        checksums=compute_hashes_fn(content_path, ["sha1", "sha256", "sha512"]),
        checksums_computation=checksums_computation,
    )
    result = loader.load()

    assert result == {"status": "eventful"}

    visit_status = assert_last_visit_matches(
        swh_storage, origin.url, status="full", type="content"
    )
    assert visit_status.snapshot is not None

    result2 = loader.load()

    assert result2 == {"status": "uneventful"}


@pytest.mark.skipif(
    nix_store_missing, reason="requires nix-store binary from nix binaries"
)
@pytest.mark.parametrize("checksums_computation", ["standard", "nar"])
def test_content_loader_hash_mismatch(
    swh_storage, requests_mock_datadir, content_path, checksums_computation
):
    """It should be an eventful visit on a new file, then uneventful"""
    compute_hashes_fn = (
        compute_content_nar_hashes if checksums_computation == "nar" else compute_hashes
    )
    checksums = compute_hashes_fn(content_path, ["sha1", "sha256", "sha512"])
    erratic_checksums = {
        algo: chksum.replace("a", "e")  # alter checksums to fail integrity check
        for algo, chksum in checksums.items()
    }
    origin = Origin(CONTENT_URL)
    loader = ContentLoader(
        swh_storage,
        origin.url,
        checksums=erratic_checksums,
        checksums_computation=checksums_computation,
    )
    result = loader.load()

    assert result == {"status": "failed"}

    assert_last_visit_matches(swh_storage, origin.url, status="failed", type="content")


DIRECTORY_MIRROR = "https://example.org"
DIRECTORY_URL = f"{DIRECTORY_MIRROR}/archives/dummy-hello.tar.gz"


def test_directory_loader_missing_field(swh_storage):
    """It should raise if the DirectoryLoader is missing checksums field"""
    origin = Origin(DIRECTORY_URL)
    with pytest.raises(TypeError, match="missing"):
        DirectoryLoader(swh_storage, origin.url)


def test_directory_loader_404(caplog, swh_storage, requests_mock_datadir, tarball_path):
    """It should not ingest origin when there is no tarball to be found (no mirrors)"""
    unknown_origin = Origin(f"{DIRECTORY_MIRROR}/archives/unknown.tar.gz")
    loader = DirectoryLoader(
        swh_storage,
        unknown_origin.url,
        checksums=compute_hashes(tarball_path),
    )
    result = loader.load()

    assert result == {"status": "uneventful"}

    _check_load_failure(
        caplog,
        loader,
        NotFound,
        "Unknown origin",
        status="not_found",
        origin=unknown_origin,
    )


def test_directory_loader_404_with_fallback(
    caplog, swh_storage, requests_mock_datadir, tarball_path
):
    """It should not ingest origin when there is no tarball to be found"""
    unknown_origin = Origin(f"{DIRECTORY_MIRROR}/archives/unknown.tbz2")
    fallback_url_ko = f"{DIRECTORY_MIRROR}/archives/elsewhere-unknown2.tbz2"
    loader = DirectoryLoader(
        swh_storage,
        unknown_origin.url,
        fallback_urls=[fallback_url_ko],
        checksums=compute_hashes(tarball_path),
    )
    result = loader.load()

    assert result == {"status": "uneventful"}

    _check_load_failure(
        caplog,
        loader,
        NotFound,
        "Unknown origin",
        status="not_found",
        origin=unknown_origin,
    )


@pytest.mark.skipif(
    nix_store_missing, reason="requires nix-store binary from nix binaries"
)
@pytest.mark.parametrize("checksums_computation", ["standard", "nar"])
def test_directory_loader_hash_mismatch(
    caplog, swh_storage, requests_mock_datadir, tarball_path, checksums_computation
):
    """It should not ingest tarball with mismatched checksum"""
    compute_hashes_fn = (
        compute_nar_hashes if checksums_computation == "nar" else compute_hashes
    )
    checksums = compute_hashes_fn(tarball_path, ["sha1", "sha256", "sha512"])

    origin = Origin(DIRECTORY_URL)
    erratic_checksums = {
        algo: chksum.replace("a", "e")  # alter checksums to fail integrity check
        for algo, chksum in checksums.items()
    }

    loader = DirectoryLoader(
        swh_storage,
        origin.url,
        checksums=erratic_checksums,  # making the integrity check fail
        checksums_computation=checksums_computation,
    )
    result = loader.load()

    assert result == {"status": "failed"}

    _check_load_failure(
        caplog,
        loader,
        ValueError,
        "mismatched",
        status="failed",
        origin=origin,
    )


@pytest.mark.parametrize("checksum_algo", ["sha1", "sha256", "sha512"])
def test_directory_loader_ok_with_fallback(
    caplog, swh_storage, requests_mock_datadir, tarball_with_std_hashes, checksum_algo
):
    """It should be an eventful visit even when ingesting through mirror url"""
    tarball_path, checksums = tarball_with_std_hashes

    dead_origin = Origin(f"{DIRECTORY_MIRROR}/dead-origin-url")
    fallback_url_ok = DIRECTORY_URL
    fallback_url_ko = f"{DIRECTORY_MIRROR}/archives/unknown2.tgz"

    loader = DirectoryLoader(
        swh_storage,
        dead_origin.url,
        fallback_urls=[fallback_url_ok, fallback_url_ko],
        checksums={checksum_algo: checksums[checksum_algo]},
    )
    result = loader.load()

    assert result == {"status": "eventful"}


@pytest.mark.skipif(
    nix_store_missing, reason="requires nix-store binary from nix binaries"
)
@pytest.mark.parametrize("checksums_computation", ["standard", "nar"])
def test_directory_loader_ok_simple(
    swh_storage, requests_mock_datadir, tarball_path, checksums_computation
):
    """It should be an eventful visit on a new tarball, then uneventful"""
    origin = Origin(DIRECTORY_URL)
    compute_hashes_fn = (
        compute_nar_hashes if checksums_computation == "nar" else compute_hashes
    )

    loader = DirectoryLoader(
        swh_storage,
        origin.url,
        checksums=compute_hashes_fn(tarball_path, ["sha1", "sha256", "sha512"]),
        checksums_computation=checksums_computation,
    )
    result = loader.load()

    assert result == {"status": "eventful"}

    visit_status = assert_last_visit_matches(
        swh_storage, origin.url, status="full", type="directory"
    )
    assert visit_status.snapshot is not None

    result2 = loader.load()

    assert result2 == {"status": "uneventful"}
