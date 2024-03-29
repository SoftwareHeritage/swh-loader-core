# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import os
import tempfile

import pytest

from swh.loader.package.rpm.loader import RpmLoader, extract_rpm_package
from swh.loader.package.utils import EMPTY_AUTHOR, download
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.hashutil import hash_to_bytes
from swh.model.model import (
    ObjectType,
    Release,
    Snapshot,
    SnapshotBranch,
    TargetType,
    TimestampWithTimezone,
)

ORIGIN = "rpm://Fedora/packages/nginx"
RPM_URL = "https://archives.fedoraproject.org/nginx-1.18.0-5.fc34.src.rpm"


PACKAGES = {
    "fedora34/everything/1.18.0-5": {
        "name": "nginx",
        "version": "1.18.0-5",
        "release": 34,
        "edition": "Everything",
        "buildTime": "2022-11-01T12:00:55+00:00",
        "url": RPM_URL,
        "checksums": {
            "sha256": "ac68fa26886c661b77bfb97bbe234a6c37d36a16c1eca126eabafbfc7fcbece4"
        },
    }
}

NEW_PACKAGES = {
    **PACKAGES,
    "fedora35/everything/1.20.0-5": {
        # using the same .rpm file but for a new branch
        "name": "nginx",
        "version": "1.20.0-5",
        "release": 35,
        "edition": "Everything",
        "buildTime": "2022-11-01T12:00:55+00:00",
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


snapshot_id = "e3b199390a96f70afe73137f5082e34f0deb4872"
release_id = hash_to_bytes("5aafaa6f753002fc1b87e603c5e42f582f777f6d")

snapshot = Snapshot(
    id=hash_to_bytes(snapshot_id),
    branches={
        b"releases/fedora34/everything/1.18.0-5": SnapshotBranch(
            target=release_id,
            target_type=TargetType.RELEASE,
        ),
        b"HEAD": SnapshotBranch(
            target=hash_to_bytes(
                "72656c65617365732f6665646f726133342f65766572797468696e672f312e31382e302d35"
            ),
            target_type=TargetType.ALIAS,
        ),
        b"nginx-1.18.0.tar.gz": SnapshotBranch(
            target=hash_to_bytes("b0d583b0c289290294657b4c975b2094b9b6803b"),
            target_type=TargetType.DIRECTORY,
        ),
    },
)
release = Release(
    id=release_id,
    name=b"1.18.0-5",
    author=EMPTY_AUTHOR,
    date=TimestampWithTimezone.from_iso8601("2022-11-01T12:00:55+00:00"),
    message=(
        b"Synthetic release for Rpm source package "
        b"nginx version fedora34/everything/1.18.0-5\n"
    ),
    target=hash_to_bytes("044965ae8affff6fd0bcb908bb345e626ca99ef6"),
    target_type=ObjectType.DIRECTORY,
    synthetic=True,
)

new_snapshot_id = "ec0c636be12a8dd26e9697ea79b30e7ef43f5ca7"
new_release_id = hash_to_bytes("4a554d436472947f0e325f0b24140c9616645a25")

new_snapshot = Snapshot(
    id=hash_to_bytes(new_snapshot_id),
    branches={
        b"releases/fedora34/everything/1.18.0-5": SnapshotBranch(
            target=release_id,
            target_type=TargetType.RELEASE,
        ),
        b"releases/fedora35/everything/1.20.0-5": SnapshotBranch(
            target=new_release_id,
            target_type=TargetType.RELEASE,
        ),
        b"HEAD": SnapshotBranch(
            target=hash_to_bytes(
                "72656c65617365732f6665646f726133352f65766572797468696e672f312e32302e302d35"
            ),
            target_type=TargetType.ALIAS,
        ),
        b"nginx-1.18.0.tar.gz": SnapshotBranch(
            target=hash_to_bytes("b0d583b0c289290294657b4c975b2094b9b6803b"),
            target_type=TargetType.DIRECTORY,
        ),
    },
)
new_release = Release(
    id=new_release_id,
    name=b"1.20.0-5",
    author=EMPTY_AUTHOR,
    date=TimestampWithTimezone.from_iso8601("2022-11-01T12:00:55+00:00"),
    message=(
        b"Synthetic release for Rpm source package "
        b"nginx version fedora35/everything/1.20.0-5\n"
    ),
    target=hash_to_bytes("044965ae8affff6fd0bcb908bb345e626ca99ef6"),
    target_type=ObjectType.DIRECTORY,
    synthetic=True,
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
    loader = RpmLoader(swh_storage, ORIGIN, packages=PACKAGES)

    actual_load_status = loader.load()

    assert actual_load_status == {"status": "eventful", "snapshot_id": snapshot_id}
    assert [m.url for m in requests_mock_datadir.request_history] == [RPM_URL]
    assert_stored(swh_storage, release, snapshot, expected_stats)


def test_rpm_multiple_visits(swh_storage, requests_mock_datadir, expected_stats):
    loader = RpmLoader(swh_storage, ORIGIN, packages=PACKAGES)

    # First run: Discovered exactly 1 package
    load_status = loader.load()
    assert load_status == {"status": "eventful", "snapshot_id": snapshot_id}

    # Second run: No updates
    load_status = loader.load()
    expected_stats["origin_visit"] += 1  # a new visit occurred but no new snapshot

    assert load_status == {"status": "uneventful", "snapshot_id": snapshot_id}
    assert [m.url for m in requests_mock_datadir.request_history] == [RPM_URL]
    assert_stored(swh_storage, release, snapshot, expected_stats)

    # Third run: New release (Updated snapshot)
    loader.packages = NEW_PACKAGES

    load_status = loader.load()
    expected_stats["origin_visit"] += 1  # same rpm:// origin
    expected_stats["release"] += 1  # new release (1.20.0-5)
    expected_stats["snapshot"] += 1  # updated metadata (`packages` param)

    assert load_status == {"status": "eventful", "snapshot_id": new_snapshot_id}
    assert [m.url for m in requests_mock_datadir.request_history] == [RPM_URL, RPM_URL]
    assert_stored(swh_storage, new_release, new_snapshot, expected_stats)
