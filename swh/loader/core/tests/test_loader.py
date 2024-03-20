# Copyright (C) 2018-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import datetime
from functools import partial
import hashlib
import logging
import time
from typing import Any, Dict
from unittest.mock import MagicMock, call

import pytest

from swh.core.api.classes import stream_results
from swh.core.tests.test_retry import assert_sleep_calls
from swh.loader.core.loader import (
    SENTRY_ORIGIN_URL_TAG_NAME,
    SENTRY_VISIT_TYPE_TAG_NAME,
    BaseLoader,
    ContentLoader,
    TarballDirectoryLoader,
    download_orig,
)
from swh.loader.core.metadata_fetchers import MetadataFetcherProtocol
from swh.loader.core.tests.dummy_loader import (
    METADATA_AUTHORITY,
    ORIGIN,
    PARENT_ORIGIN,
    REMD,
    BarLoader,
    DummyBaseLoader,
    DummyLoader,
    DummyMetadataFetcher,
    DummyMetadataFetcherWithFork,
    FooLoader,
)
from swh.loader.core.utils import compute_hashes, compute_nar_hashes
from swh.loader.exception import NotFound, UnsupportedChecksumLayout
from swh.loader.tests import (
    assert_last_visit_matches,
    fetch_extids_from_checksums,
    get_stats,
)
from swh.model.hashutil import hash_to_bytes
from swh.model.model import Origin, Snapshot, SnapshotBranch, SnapshotTargetType


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
    assert (
        list(
            stream_results(
                swh_storage.raw_extrinsic_metadata_get,
                ORIGIN.swhid(),
                METADATA_AUTHORITY,
            )
        )
        == []
    )


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
    assert loader.log.name == "swh.loader.core.tests.dummy_loader.DummyBaseLoader"


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
    assert isinstance(loader, (ContentLoader, TarballDirectoryLoader))
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


class DummyLoaderWithPartialSnapshot(DummyBaseLoader):
    call = 0

    def fetch_data(self):
        self.call += 1
        # Let's have one call to fetch data and then another to fetch further data
        return self.call == 1

    def store_data(self) -> None:
        # First call does nothing and the last one flushes the final snapshot
        if self.call != 1:
            self.storage.snapshot_add([Snapshot(branches={})])

    def build_partial_snapshot(self):
        """Build partial snapshot to serialize during loading."""
        return Snapshot(
            branches={
                b"alias": SnapshotBranch(
                    target=hash_to_bytes(b"0" * 20),
                    target_type=SnapshotTargetType.DIRECTORY,
                )
            }
        )


def test_loader_with_partial_snapshot(swh_storage, sentry_events):
    """Ensure loader can write partial snapshot when configured to."""
    loader = DummyLoaderWithPartialSnapshot(
        swh_storage, "dummy-url", create_partial_snapshot=True
    )
    status = loader.load()

    assert status == {"status": "eventful"}

    actual_stats = get_stats(swh_storage)

    expected_stats = {
        "origin": 1,  # only 1 origin
        "origin_visit": 1,  # with 1 visit
        "snapshot": 1 + 1,  # 1 partial snapshot and 1 final snapshot
    }
    for key in expected_stats.keys():
        assert actual_stats[key] == expected_stats[key]


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


@pytest.mark.parametrize("loader_class", [ContentLoader, TarballDirectoryLoader])
def test_loader_extid_version(swh_storage, loader_class, content_path):
    """Ensure the extid_version is the expected one"""
    unknown_origin = Origin(f"{CONTENT_MIRROR}/project/asdf/archives/unknown.lisp")
    loader = loader_class(
        swh_storage,
        unknown_origin.url,
        checksums=compute_hashes(content_path),
    )
    assert loader.extid_version == 1


@pytest.mark.parametrize("loader_class", [ContentLoader, TarballDirectoryLoader])
def test_node_loader_missing_field(swh_storage, loader_class):
    """It should raise if the ContentLoader is missing checksums field"""
    with pytest.raises(UnsupportedChecksumLayout):
        loader_class(
            swh_storage,
            CONTENT_URL,
            checksums={"sha256": "irrelevant-for-that-test"},
            checksum_layout="unsupported",
        )

    # compat' check
    with pytest.raises(UnsupportedChecksumLayout):
        loader_class(
            swh_storage,
            CONTENT_URL,
            checksums={"sha256": "irrelevant-for-that-test"},
            checksums_computation="unsupported",
        )


def test_content_loader_404(
    caplog, swh_storage, requests_mock_datadir, content_path, requests_mock
):
    """It should not ingest origin when there is no file to be found (no mirror url)"""
    unknown_origin = Origin(f"{CONTENT_MIRROR}/project/asdf/archives/unknown.lisp")
    requests_mock.get(unknown_origin.url, status_code=404)
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
    caplog, swh_storage, requests_mock_datadir, content_path, requests_mock
):
    """It should not ingest origin when there is no file to be found"""
    unknown_origin = Origin(f"{CONTENT_MIRROR}/project/asdf/archives/unknown.lisp")
    fallback_url_ko = f"{CONTENT_MIRROR}/project/asdf/archives/unknown2.lisp"
    requests_mock.get(unknown_origin.url, status_code=404)
    requests_mock.get(fallback_url_ko, status_code=404)
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
    requests_mock,
):
    """It should be an eventful visit even when ingesting through mirror url"""
    dead_origin = Origin(f"{CONTENT_MIRROR}/dead-origin-url")
    fallback_url_ok = CONTENT_URL
    fallback_url_ko = f"{CONTENT_MIRROR}/project/asdf/archives/unknown2.lisp"
    requests_mock.get(dead_origin.url, status_code=404)
    requests_mock.get(fallback_url_ko, status_code=404)

    loader = ContentLoader(
        swh_storage,
        dead_origin.url,
        fallback_urls=[fallback_url_ok, fallback_url_ko],
        checksums=compute_hashes(content_path, [checksum_algo]),
    )
    result = loader.load()

    assert result == {"status": "eventful"}


compute_content_nar_hashes = partial(compute_nar_hashes, is_tarball=False)


@pytest.mark.parametrize("checksum_layout", ["standard", "nar"])
def test_content_loader_ok_simple(
    swh_storage, requests_mock_datadir, content_path, checksum_layout
):
    """It should be an eventful visit on a new file, then uneventful"""
    compute_hashes_fn = (
        compute_content_nar_hashes if checksum_layout == "nar" else compute_hashes
    )

    checksums = compute_hashes_fn(content_path, ["sha1", "sha256", "sha512"])
    origin = Origin(CONTENT_URL)
    loader = ContentLoader(
        swh_storage,
        origin.url,
        checksums=checksums,
        checksum_layout=checksum_layout,
    )
    result = loader.load()

    assert result == {"status": "eventful"}

    extids = fetch_extids_from_checksums(
        loader.storage, checksum_layout, checksums, extid_version=loader.extid_version
    )
    assert len(extids) == len(checksums)

    visit_status = assert_last_visit_matches(
        swh_storage, origin.url, status="full", type="content"
    )
    assert visit_status.snapshot is not None

    result2 = loader.load()

    assert result2 == {"status": "uneventful"}


@pytest.mark.parametrize("checksum_layout", ["standard", "nar"])
def test_content_loader_hash_mismatch(
    swh_storage, requests_mock_datadir, content_path, checksum_layout
):
    """It should be an eventful visit on a new file, then uneventful"""
    compute_hashes_fn = (
        compute_content_nar_hashes if checksum_layout == "nar" else compute_hashes
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
        checksum_layout=checksum_layout,
    )
    result = loader.load()

    assert result == {"status": "failed"}

    assert_last_visit_matches(swh_storage, origin.url, status="failed", type="content")


DIRECTORY_MIRROR = "https://example.org"
DIRECTORY_URL = f"{DIRECTORY_MIRROR}/archives/dummy-hello.tar.gz"


def test_directory_loader_missing_field(swh_storage):
    """It should raise if the TarballDirectoryLoader is missing checksums field"""
    origin = Origin(DIRECTORY_URL)
    with pytest.raises(TypeError, match="missing"):
        TarballDirectoryLoader(swh_storage, origin.url)


def test_directory_loader_404(
    caplog, swh_storage, requests_mock_datadir, tarball_path, requests_mock
):
    """It should not ingest origin when there is no tarball to be found (no mirrors)"""
    unknown_origin = Origin(f"{DIRECTORY_MIRROR}/archives/unknown.tar.gz")
    requests_mock.get(unknown_origin.url, status_code=404)
    loader = TarballDirectoryLoader(
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
    caplog, swh_storage, requests_mock_datadir, tarball_path, requests_mock
):
    """It should not ingest origin when there is no tarball to be found"""
    unknown_origin = Origin(f"{DIRECTORY_MIRROR}/archives/unknown.tbz2")
    fallback_url_ko = f"{DIRECTORY_MIRROR}/archives/elsewhere-unknown2.tbz2"
    requests_mock.get(unknown_origin.url, status_code=404)
    requests_mock.get(fallback_url_ko, status_code=404)

    loader = TarballDirectoryLoader(
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


def test_directory_loader_500_with_fallback(
    caplog, swh_storage, requests_mock_datadir, tarball_path, requests_mock, mocker
):
    """It should not ingest origin when there is no tarball to be found"""
    unknown_origin = Origin(f"{DIRECTORY_MIRROR}/archives/unknown.tbz2")
    fallback_url_ko = f"{DIRECTORY_MIRROR}/archives/elsewhere-unknown2.tbz2"
    requests_mock.get(unknown_origin.url, status_code=500)
    requests_mock.get(fallback_url_ko, status_code=500)

    mock_sleep = mocker.patch.object(download_orig.retry, "sleep")

    loader = TarballDirectoryLoader(
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

    assert_sleep_calls(mocker, mock_sleep, [1, 10, 1, 10])


@pytest.mark.parametrize("checksum_layout", ["standard", "nar"])
def test_directory_loader_hash_mismatch(
    caplog, swh_storage, requests_mock_datadir, tarball_path, checksum_layout
):
    """It should not ingest tarball with mismatched checksum"""
    compute_hashes_fn = (
        compute_nar_hashes if checksum_layout == "nar" else compute_hashes
    )
    checksums = compute_hashes_fn(tarball_path, ["sha1", "sha256", "sha512"])

    origin = Origin(DIRECTORY_URL)
    erratic_checksums = {
        algo: chksum.replace("a", "e")  # alter checksums to fail integrity check
        for algo, chksum in checksums.items()
    }

    loader = TarballDirectoryLoader(
        swh_storage,
        origin.url,
        checksums=erratic_checksums,  # making the integrity check fail
        checksum_layout=checksum_layout,
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
    caplog,
    swh_storage,
    requests_mock_datadir,
    tarball_with_std_hashes,
    checksum_algo,
    requests_mock,
):
    """It should be an eventful visit even when ingesting through mirror url"""
    tarball_path, checksums = tarball_with_std_hashes

    dead_origin = Origin(f"{DIRECTORY_MIRROR}/dead-origin-url")
    fallback_url_ok = DIRECTORY_URL
    fallback_url_ko = f"{DIRECTORY_MIRROR}/archives/unknown2.tgz"
    requests_mock.get(dead_origin.url, status_code=404)
    requests_mock.get(fallback_url_ko, status_code=404)

    loader = TarballDirectoryLoader(
        swh_storage,
        dead_origin.url,
        fallback_urls=[fallback_url_ok, fallback_url_ko],
        checksums={checksum_algo: checksums[checksum_algo]},
    )
    result = loader.load()

    assert result == {"status": "eventful"}


@pytest.mark.parametrize("checksum_layout", ["nar", "standard"])
def test_directory_loader_ok_simple(
    swh_storage, requests_mock_datadir, tarball_path, checksum_layout
):
    """It should be an eventful visit on a new tarball, then uneventful"""
    origin = Origin(DIRECTORY_URL)
    compute_hashes_fn = (
        compute_nar_hashes if checksum_layout == "nar" else compute_hashes
    )

    checksums = compute_hashes_fn(tarball_path, ["sha1", "sha256", "sha512"])

    loader = TarballDirectoryLoader(
        swh_storage,
        origin.url,
        checksums=checksums,
        checksum_layout=checksum_layout,
    )
    result = loader.load()

    assert result == {"status": "eventful"}

    extids = fetch_extids_from_checksums(
        loader.storage, checksum_layout, checksums, extid_version=loader.extid_version
    )
    assert len(extids) == len(checksums)

    visit_status = assert_last_visit_matches(
        swh_storage, origin.url, status="full", type="tarball-directory"
    )
    assert visit_status.snapshot is not None

    result2 = loader.load()

    assert result2 == {"status": "uneventful"}


def test_directory_loader_nar_hash_without_top_level_dir(swh_storage, tarball_path):
    """It should be an eventful visit when the expected NAR hash omits tarball top level
    directory in its computation."""

    origin = Origin(f"file://{tarball_path}")

    expected_nar_checksums = {
        "sha256": "23fb1fe278aeb2de899f7d7f10cf892f63136cea2c07146da2200da4de54b7e4"
    }

    loader = TarballDirectoryLoader(
        swh_storage,
        origin.url,
        checksums=expected_nar_checksums,
        checksum_layout="nar",
    )
    result = loader.load()

    assert result == {"status": "eventful"}


@pytest.mark.parametrize("tarball_top_level_directory", [True, False])
def test_directory_loader_nar_hash_tarball_with_or_without_top_level(
    swh_storage, requests_mock_datadir, tarball_path, tarball_top_level_directory
):
    """It should be eventful to ingest tarball when the expected NAR hash omits tarball
    top level directory in its computation (as nixpkgs computes the nar on tarball) or
    when the top level directory is provided directly (as guix computes the nar on
    tarball)

    """
    origin = Origin(DIRECTORY_URL)
    # Compute nar hashes out of:
    # - the uncompressed directory top-level (top_level=True)
    # - the first directory (top_level=False) within the tarball
    # In any case, the ingestion should be ok
    checksums = compute_nar_hashes(
        tarball_path,
        ["sha1", "sha256", "sha512"],
        is_tarball=True,
        top_level=tarball_top_level_directory,
    )

    loader = TarballDirectoryLoader(
        swh_storage,
        origin.url,
        checksums=checksums,
        checksum_layout="nar",
    )
    result = loader.load()

    assert result == {"status": "eventful"}

    extids = fetch_extids_from_checksums(
        loader.storage, "nar", checksums, extid_version=loader.extid_version
    )
    assert len(extids) == len(checksums)

    visit_status = assert_last_visit_matches(
        swh_storage, origin.url, status="full", type="tarball-directory"
    )
    assert visit_status.snapshot is not None

    result2 = loader.load()

    assert result2 == {"status": "uneventful"}


@pytest.mark.parametrize("checksum_layout", ["nar", "standard"])
def test_directory_loader_ok_local_url(swh_storage, tarball_path, checksum_layout):
    """It should be an eventful visit on a new local tarball, then uneventful"""

    origin = Origin(f"file://{tarball_path}")
    compute_hashes_fn = (
        compute_nar_hashes if checksum_layout == "nar" else compute_hashes
    )

    checksums = compute_hashes_fn(tarball_path, ["sha1", "sha256", "sha512"])

    loader = TarballDirectoryLoader(
        swh_storage,
        origin.url,
        checksums=checksums,
        checksum_layout=checksum_layout,
    )
    result = loader.load()

    assert result == {"status": "eventful"}

    result2 = loader.load()

    assert result2 == {"status": "uneventful"}


@pytest.fixture
def swh_loader_config() -> Dict[str, Any]:
    return {
        "storage": {
            "cls": "memory",
        },
        "origin_url": "origin",
        "overrides": {"swh.loader.core.tests.dummy_loader.FooLoader": {"foo": "bar"}},
    }


def test_loader_from_config_with_override(swh_storage, swh_loader_config):
    """Instanting multiple loaders with centralized configuration is ok"""
    storage_config = swh_loader_config.pop("storage")

    foo_loader = FooLoader.from_config(storage_config, **swh_loader_config)
    # Instantiating the loader will pick up its specific configuration in the override
    assert foo_loader is not None
    # and use it
    assert foo_loader.foo == "bar"

    bar_loader = BarLoader.from_config(storage_config, **swh_loader_config)
    # Instantiating another loader with that same configuration is fine too
    # It just discards the unknown part of the configuration
    assert bar_loader is not None

    swh_loader_config.pop("overrides")
    foo_loader2 = FooLoader.from_config(storage_config, **swh_loader_config)
    # Instantiating the loader without the override works too as it's an optional
    # configuration
    assert foo_loader2 is not None
    assert foo_loader2.foo is None


def test_loader_from_config_with_override2(swh_storage, swh_loader_config):
    """Instanting multiple loaders with centralized configuration is ok"""
    storage_config = swh_loader_config.pop("storage")
    overrides = swh_loader_config.pop("overrides")

    foo_loader = FooLoader.from_config(storage_config, overrides, **swh_loader_config)
    # Instantiating the loader will pick up its specific configuration in the override
    assert foo_loader is not None
    # and use it
    assert foo_loader.foo == "bar"

    bar_loader = BarLoader.from_config(storage_config, overrides, **swh_loader_config)
    # Instantiating another loader with that same configuration is fine too
    # It just discards the unknown part of the configuration
    assert bar_loader is not None

    foo_loader2 = FooLoader.from_config(storage_config, **swh_loader_config)
    # Instantiating the loader without the override works too as it's an optional
    # configuration
    assert foo_loader2 is not None
    assert foo_loader2.foo is None


class SvnDirectoryLoader(TarballDirectoryLoader):
    visit_type = "svn-export"


def test_nar_vcs_type_for_svn_dir_loader(swh_storage, tarball_path, mocker):
    """It should detect vcs_type for nar hash from loader visit_type"""

    origin = Origin(f"file://{tarball_path}")

    checksums = compute_nar_hashes(tarball_path, ["sha1", "sha256", "sha512"])

    from swh.loader.core.nar import Nar

    nar_obj = mocker.spy(Nar, "__init__")

    loader = SvnDirectoryLoader(
        swh_storage,
        origin.url,
        checksums=checksums,
        checksum_layout="nar",
    )
    result = loader.load()
    assert result == {"status": "eventful"}

    _, kwargs = nar_obj.call_args
    assert kwargs == {"exclude_vcs": True, "vcs_type": "svn"}
