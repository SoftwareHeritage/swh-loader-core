# Copyright (C) 2022-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import os
import tempfile

import pytest

from swh.loader.core.utils import EMPTY_AUTHOR, download
from swh.loader.package.rpm.loader import RpmLoader, extract_rpm_package
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.hashutil import hash_to_bytes
from swh.model.model import (
    ObjectType,
    Release,
    Snapshot,
    SnapshotBranch,
    SnapshotTargetType,
    TimestampWithTimezone,
)

ORIGIN = "rpm://Fedora/packages/nginx"
RPM_URL = "https://archives.fedoraproject.org/nginx-1.18.0-5.fc34.src.rpm"


PACKAGES = {
    "34/Everything/1.18.0-5": {
        "name": "nginx",
        "version": "1.18.0-5",
        "release": 34,
        "edition": "Everything",
        "build_time": "2022-11-01T12:00:55+00:00",
        "url": RPM_URL,
        "checksums": {
            "sha256": "ac68fa26886c661b77bfb97bbe234a6c37d36a16c1eca126eabafbfc7fcbece4"
        },
    }
}

NEW_PACKAGES = {
    **PACKAGES,
    "35/Everything/1.20.0-5": {
        # using the same .rpm file but for a new branch
        "name": "nginx",
        "version": "1.20.0-5",
        "release": 35,
        "edition": "Everything",
        "build_time": "2022-11-01T12:00:55+00:00",
        "url": RPM_URL,
        "checksums": {
            "sha256": "ac68fa26886c661b77bfb97bbe234a6c37d36a16c1eca126eabafbfc7fcbece4"
        },
    },
}


@pytest.fixture()
def expected_stats():
    return {
        "content": 421,
        "directory": 40,
        "origin": 1,
        "origin_visit": 1,
        "release": 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    }


release = Release(
    name=b"1.18.0-5",
    author=EMPTY_AUTHOR,
    date=TimestampWithTimezone.from_iso8601("2022-11-01T12:00:55+00:00"),
    message=(b"Synthetic release for RPM source package nginx version 1.18.0-5\n"),
    target=hash_to_bytes("044965ae8affff6fd0bcb908bb345e626ca99ef6"),
    target_type=ObjectType.DIRECTORY,
    synthetic=True,
)

new_release = Release(
    name=b"1.20.0-5",
    author=EMPTY_AUTHOR,
    date=TimestampWithTimezone.from_iso8601("2022-11-01T12:00:55+00:00"),
    message=(b"Synthetic release for RPM source package nginx version 1.20.0-5\n"),
    target=hash_to_bytes("044965ae8affff6fd0bcb908bb345e626ca99ef6"),
    target_type=ObjectType.DIRECTORY,
    synthetic=True,
)

snapshot = Snapshot(
    branches={
        b"releases/34/Everything/1.18.0-5": SnapshotBranch(
            target=release.id,
            target_type=SnapshotTargetType.RELEASE,
        ),
        b"HEAD": SnapshotBranch(
            target=b"releases/34/Everything/1.18.0-5",
            target_type=SnapshotTargetType.ALIAS,
        ),
        b"nginx-1.18.0.tar.gz": SnapshotBranch(
            target=hash_to_bytes("b0d583b0c289290294657b4c975b2094b9b6803b"),
            target_type=SnapshotTargetType.DIRECTORY,
        ),
    },
)


new_snapshot = Snapshot(
    branches={
        b"releases/34/Everything/1.18.0-5": SnapshotBranch(
            target=release.id,
            target_type=SnapshotTargetType.RELEASE,
        ),
        b"releases/35/Everything/1.20.0-5": SnapshotBranch(
            target=new_release.id,
            target_type=SnapshotTargetType.RELEASE,
        ),
        b"HEAD": SnapshotBranch(
            target=b"releases/35/Everything/1.20.0-5",
            target_type=SnapshotTargetType.ALIAS,
        ),
        b"nginx-1.18.0.tar.gz": SnapshotBranch(
            target=hash_to_bytes("b0d583b0c289290294657b4c975b2094b9b6803b"),
            target_type=SnapshotTargetType.DIRECTORY,
        ),
    },
)


def test_download_and_extract_rpm_package(requests_mock_datadir):
    rpm_url = RPM_URL

    with tempfile.TemporaryDirectory() as tmpdir:
        rpm_path, _ = download(rpm_url, tmpdir)
        extract_rpm_package(rpm_path, tmpdir)

        # .spec and .tar.gz should be extracted from .rpm
        assert os.path.exists(f"{tmpdir}/extracted/nginx.spec")
        assert os.path.exists(f"{tmpdir}/extracted/nginx-1.18.0.tar.gz")

        with open(f"{tmpdir}/extract.log", "r") as f:
            logs = f.read()
            assert logs.startswith("404.html")


def test_extract_non_rpm_package(requests_mock_datadir):
    rpm_url = RPM_URL

    with tempfile.TemporaryDirectory() as tmpdir:
        rpm_path, _ = download(rpm_url, tmpdir)
        extract_rpm_package(rpm_path, tmpdir)

        with pytest.raises(ValueError):
            extract_rpm_package(f"{tmpdir}/extracted/nginx.spec", tmpdir)


def test_extract_non_existent_rpm_package():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(FileNotFoundError) as e:
            extract_rpm_package(f"{tmpdir}/non-existent.src.rpm", tmpdir)
        assert f"RPM package {tmpdir}/non-existent.src.rpm not found" in str(e)


def assert_stored(swh_storage, release: Release, snapshot: Snapshot, stats: dict):
    assert_last_visit_matches(
        swh_storage,
        ORIGIN,
        status="full",
        type="rpm",
        snapshot=hash_to_bytes(snapshot.id),
    )
    check_snapshot(snapshot, swh_storage)
    assert swh_storage.release_get([release.id])[0] == release
    assert get_stats(swh_storage) == stats


def test_rpm_first_visit(swh_storage, requests_mock_datadir, expected_stats):
    loader = RpmLoader(
        swh_storage,
        ORIGIN,
        packages=PACKAGES,
        lister_name="rpm",
        lister_instance_name="Fedora",
    )

    actual_load_status = loader.load()

    assert actual_load_status == {
        "status": "eventful",
        "snapshot_id": snapshot.id.hex(),
    }
    assert [m.url for m in requests_mock_datadir.request_history] == [RPM_URL]
    assert_stored(swh_storage, release, snapshot, expected_stats)


def test_rpm_multiple_visits(swh_storage, requests_mock_datadir, expected_stats):
    loader = RpmLoader(
        swh_storage,
        ORIGIN,
        packages=PACKAGES,
        lister_name="rpm",
        lister_instance_name="Fedora",
    )

    # First run: Discovered exactly 1 package
    load_status = loader.load()
    assert load_status == {"status": "eventful", "snapshot_id": snapshot.id.hex()}

    # Second run: No updates
    load_status = loader.load()

    expected_stats["origin_visit"] += 1  # a new visit occurred but no new snapshot

    assert load_status == {"status": "uneventful", "snapshot_id": snapshot.id.hex()}
    assert [m.url for m in requests_mock_datadir.request_history] == [RPM_URL]
    assert_stored(swh_storage, release, snapshot, expected_stats)

    # Third run: New release (Updated snapshot)
    loader = RpmLoader(
        swh_storage,
        ORIGIN,
        packages=NEW_PACKAGES,
        lister_name="rpm",
        lister_instance_name="Fedora",
    )

    load_status = loader.load()
    expected_stats["origin_visit"] += 1  # same rpm:// origin
    expected_stats["release"] += 1  # new release (1.20.0-5)
    expected_stats["snapshot"] += 1  # updated metadata (`packages` param)

    assert load_status == {"status": "eventful", "snapshot_id": new_snapshot.id.hex()}
    assert [m.url for m in requests_mock_datadir.request_history] == [RPM_URL, RPM_URL]
    assert_stored(swh_storage, new_release, new_snapshot, expected_stats)


def test_rpm_package_versions_sort(swh_storage):
    packages = {
        "7/Fedora/0.6.1-5": {
            "version": "0.6.1-5",
            "build_time": "2007-09-24T16:49:52+00:00",
        },
        "7/Server/0.6.1-5": {
            "version": "0.6.1-5",
            "build_time": "2007-09-24T16:49:52+00:00",
        },
        "7/Modular/0.6.1-5": {
            "version": "0.6.1-5",
            "build_time": "2007-09-24T16:49:52+00:00",
        },
        "7/Everything/0.6.1-5": {
            "version": "0.6.1-5",
            "build_time": "2007-09-24T16:49:52+00:00",
        },
        "8/Everything/0.6.1-6": {
            "version": "0.6.1-6",
            "build_time": "2007-10-17T06:20:56+00:00",
        },
        "9/Everything/0.6.1-9": {
            "version": "0.6.1-9",
            "build_time": "2008-04-06T08:18:00+00:00",
        },
        "10/Everything/0.6.1-9": {
            "version": "0.6.1-9",
            "build_time": "2008-04-06T08:18:00+00:00",
        },
        "7/Workstation/0.6.1-5": {
            "version": "0.6.1-5",
            "build_time": "2007-09-24T16:49:52+00:00",
        },
        "11/Everything/0.6.1-10": {
            "version": "0.6.1-10",
            "build_time": "2009-02-25T18:00:39+00:00",
        },
        "12/Everything/0.6.1-11": {
            "version": "0.6.1-11",
            "build_time": "2009-07-28T11:00:32+00:00",
        },
        "13/Everything/0.6.1-11": {
            "version": "0.6.1-11",
            "build_time": "2009-07-28T11:00:32+00:00",
        },
        "14/Everything/0.6.1-11": {
            "version": "0.6.1-11",
            "build_time": "2009-07-28T11:00:32+00:00",
        },
    }

    loader = RpmLoader(
        swh_storage,
        "rpm://example/package",
        packages=packages,
        lister_name="rpm",
        lister_instance_name="Fedora",
    )

    expected_versions_sort = [
        "7/Fedora/0.6.1-5",
        "7/Server/0.6.1-5",
        "7/Modular/0.6.1-5",
        "7/Everything/0.6.1-5",
        "7/Workstation/0.6.1-5",
        "8/Everything/0.6.1-6",
        "9/Everything/0.6.1-9",
        "10/Everything/0.6.1-9",
        "11/Everything/0.6.1-10",
        "12/Everything/0.6.1-11",
        "13/Everything/0.6.1-11",
        "14/Everything/0.6.1-11",
    ]

    # sorting by branch name or package version does not result
    # in expected ordering
    assert list(sorted(packages)) != expected_versions_sort
    assert (
        list(sorted(packages, key=lambda p: packages[p]["version"]))
        != expected_versions_sort
    )

    # sorting by build time does
    assert loader.get_versions() == expected_versions_sort
