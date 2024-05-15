# Copyright (C) 2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information
import pytest

from swh.loader.package.bioconductor.loader import BioconductorLoader
from swh.loader.package.cran.loader import parse_date
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.hashutil import hash_to_bytes
from swh.model.model import (
    ObjectType,
    Person,
    Release,
    Snapshot,
    SnapshotBranch,
    SnapshotTargetType,
)
from swh.storage.interface import StorageInterface

ORIGIN = "https://www.bioconductor.org/packages/a4"

BIOC_TAR_URL = "https://www.bioconductor.org/a4_1.46.0.tar.gz"
WORKFLOW_TAR_URL = "https://www.bioconductor.org/a4_1.48.0.tar.gz"

PACKAGES = {
    "3.16/bioc/1.46.0": {
        "package": "a4",
        "release": "3.16",
        "tar_url": BIOC_TAR_URL,
        "version": "1.46.0",
        "category": "bioc",
        "last_update_date": "2022-11-01",
        "checksums": {"md5": "4fe2823df78513c79777d009196856fd"},
    }
}

NEW_PACKAGES = {
    **PACKAGES,
    "3.17/bioc/1.48.0": {
        "package": "a4",
        "release": "3.17",
        "tar_url": WORKFLOW_TAR_URL,
        "version": "1.48.0",
        "category": "bioc",
        "last_update_date": "2023-04-25",
        "checksums": {"md5": "5d945210d12e19d845e8949ef53b9d43"},
    },
}


@pytest.fixture()
def expected_stats():
    return {
        "content": 10,
        "directory": 9,
        "origin": 1,
        "origin_visit": 1,
        "release": 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    }


release = Release(
    name=b"1.46.0",
    author=Person.from_fullname(b"Laure Cougnaud <laure.cougnaud@openanalytics.eu>"),
    date=parse_date("2022-11-01 20:49:16 UTC"),
    message=(b"Synthetic release for Bioconductor source package a4 version 1.46.0\n"),
    target=hash_to_bytes("731acdd86190ac2e783d353f6755b407bc9cd773"),
    target_type=ObjectType.DIRECTORY,
    synthetic=True,
)

new_release = Release(
    name=b"1.48.0",
    author=Person.from_fullname(b"Laure Cougnaud <laure.cougnaud@openanalytics.eu>"),
    date=parse_date("2023-04-25 20:10:33 UTC"),
    message=(b"Synthetic release for Bioconductor source package a4 version 1.48.0\n"),
    target=hash_to_bytes("c4e98ef0affe3309ced415d36e3eee4e67f570da"),
    target_type=ObjectType.DIRECTORY,
    synthetic=True,
)

snapshot = Snapshot(
    branches={
        b"releases/3.16/bioc/1.46.0": SnapshotBranch(
            target=release.id,
            target_type=SnapshotTargetType.RELEASE,
        ),
        b"HEAD": SnapshotBranch(
            target=b"releases/3.16/bioc/1.46.0",
            target_type=SnapshotTargetType.ALIAS,
        ),
    },
)


new_snapshot = Snapshot(
    branches={
        b"releases/3.16/bioc/1.46.0": SnapshotBranch(
            target=release.id,
            target_type=SnapshotTargetType.RELEASE,
        ),
        b"releases/3.17/bioc/1.48.0": SnapshotBranch(
            target=new_release.id,
            target_type=SnapshotTargetType.RELEASE,
        ),
        b"HEAD": SnapshotBranch(
            target=b"releases/3.17/bioc/1.48.0",
            target_type=SnapshotTargetType.ALIAS,
        ),
    },
)


def assert_stored(
    swh_storage: StorageInterface,
    origin: str,
    release: Release,
    snapshot: Snapshot,
    stats: dict,
):
    assert_last_visit_matches(
        swh_storage,
        origin,
        status="full",
        type="bioconductor",
        snapshot=hash_to_bytes(snapshot.id),
    )
    check_snapshot(snapshot, swh_storage)
    assert swh_storage.release_get([release.id])[0] == release
    assert get_stats(swh_storage) == stats


def test_bioconductor_first_visit(swh_storage, requests_mock_datadir, expected_stats):
    loader = BioconductorLoader(
        swh_storage,
        ORIGIN,
        packages=PACKAGES,
        lister_name="bioconductor",
        lister_instance_name="Bioconductor",
    )

    actual_load_status = loader.load()

    assert actual_load_status == {
        "status": "eventful",
        "snapshot_id": snapshot.id.hex(),
    }
    assert [m.url for m in requests_mock_datadir.request_history] == [BIOC_TAR_URL]
    assert_stored(swh_storage, ORIGIN, release, snapshot, expected_stats)


def test_bioconductor_multiple_visits(
    swh_storage, requests_mock_datadir, expected_stats
):
    loader = BioconductorLoader(
        swh_storage,
        ORIGIN,
        packages=PACKAGES,
        lister_name="bioconductor",
        lister_instance_name="Bioconductor",
    )

    # First run: Discovered exactly 1 package
    load_status = loader.load()
    assert load_status == {"status": "eventful", "snapshot_id": snapshot.id.hex()}

    # Second run: No updates
    load_status = loader.load()
    expected_stats["origin_visit"] += 1  # a new visit occurred but no new snapshot

    assert load_status == {"status": "uneventful", "snapshot_id": snapshot.id.hex()}
    assert [m.url for m in requests_mock_datadir.request_history] == [BIOC_TAR_URL]
    assert_stored(swh_storage, ORIGIN, release, snapshot, expected_stats)

    # Third run: New release (Updated snapshot)
    del loader._cached_get_versions
    loader.packages = NEW_PACKAGES

    load_status = loader.load()
    expected_stats["origin_visit"] += 1  # visited same package
    expected_stats["release"] += 1  # new release (1.48.0)
    expected_stats["snapshot"] += 1  # updated metadata (`packages` param)

    expected_stats["content"] += 3
    expected_stats["directory"] += 5

    assert load_status == {"status": "eventful", "snapshot_id": new_snapshot.id.hex()}
    assert [m.url for m in requests_mock_datadir.request_history] == [
        BIOC_TAR_URL,
        WORKFLOW_TAR_URL,
    ]
    assert_stored(swh_storage, ORIGIN, new_release, new_snapshot, expected_stats)


def test_old_releases(swh_storage, requests_mock_datadir):
    OLD_ORIGIN = "https://www.bioconductor.org/packages/ABarray"
    OLD_TAR_URL = "https://www.bioconductor.org/ABarray_1.8.0.tar.gz"
    OLD_PACKAGES = {
        "2.2/bioc/1.8.0": {
            "package": "ABarray",
            "release": "2.2",
            "version": "1.8.0",
            "category": "bioc",
            "tar_url": OLD_TAR_URL,
        }
    }

    old_release = Release(
        name=b"1.8.0",
        # author=EMPTY_AUTHOR,
        author=Person.from_fullname(
            b"Yongming Andrew Sun <sunya@appliedbiosystems.com>"
        ),
        date=parse_date("Wed Apr 30 02:30:04 2008"),
        message=(
            b"Synthetic release for Bioconductor source package ABarray version 1.8.0\n"
        ),
        target=hash_to_bytes("459838c5d069f61cb5874ce3216e751b0080bc59"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
    )

    old_snapshot = Snapshot(
        branches={
            b"releases/2.2/bioc/1.8.0": SnapshotBranch(
                target=old_release.id,
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/2.2/bioc/1.8.0",
                target_type=SnapshotTargetType.ALIAS,
            ),
        },
    )
    expected_stats = {
        "content": 67,
        "directory": 7,
        "origin": 1,
        "origin_visit": 1,
        "release": 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    }

    loader = BioconductorLoader(
        swh_storage,
        OLD_ORIGIN,
        packages=OLD_PACKAGES,
        lister_name="bioconductor",
        lister_instance_name="Bioconductor",
    )

    actual_load_status = loader.load()

    assert actual_load_status == {
        "status": "eventful",
        "snapshot_id": old_snapshot.id.hex(),
    }

    assert [m.url for m in requests_mock_datadir.request_history] == [OLD_TAR_URL]
    assert_stored(swh_storage, OLD_ORIGIN, old_release, old_snapshot, expected_stats)
