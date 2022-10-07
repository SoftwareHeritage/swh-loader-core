# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from swh.loader.package.cpan.loader import CpanLoader
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.hashutil import hash_to_bytes
from swh.model.model import (
    ObjectType,
    Person,
    Release,
    Snapshot,
    SnapshotBranch,
    TargetType,
    TimestampWithTimezone,
)

ORIGINS = [
    "https://metacpan.org/dist/Internals-CountObjects",
]


def test_get_versions(requests_mock_datadir, swh_storage):
    loader = CpanLoader(
        swh_storage,
        url=ORIGINS[0],
    )
    assert loader.get_versions() == ["0.01", "0.05"]


def test_get_default_version(requests_mock_datadir, swh_storage):
    loader = CpanLoader(
        swh_storage,
        url=ORIGINS[0],
    )
    assert loader.get_default_version() == "0.05"


def test_cpan_loader_load_multiple_version(datadir, requests_mock_datadir, swh_storage):
    loader = CpanLoader(
        swh_storage,
        url=ORIGINS[0],
    )
    load_status = loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    expected_snapshot_id = "848ee8d69d33481c88ab81f6794f6504190f011f"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/0.01": SnapshotBranch(
                target=hash_to_bytes("e73aced4cc3d56b32a328d3248b25b052f029df4"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.05": SnapshotBranch(
                target=hash_to_bytes("07382fd255ec0fc293b92aeb7e68b3fe31c174f9"),
                target_type=TargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/0.05",
                target_type=TargetType.ALIAS,
            ),
        },
    )

    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 2,
        "directory": 4,
        "origin": 1,
        "origin_visit": 1,
        "release": 2,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    assert swh_storage.release_get(
        [hash_to_bytes("07382fd255ec0fc293b92aeb7e68b3fe31c174f9")]
    )[0] == Release(
        name=b"0.05",
        message=b"Synthetic release for Perl source package Internals-CountObjects"
        b" version 0.05\n",
        target=hash_to_bytes("af3f6a43eaf4b26dbcadb1101e8d81db6d6151e0"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
        author=Person(
            fullname=b"Josh Jore <jjore@cpan.org>",
            name=b"Josh Jore",
            email=b"jjore@cpan.org",
        ),
        date=TimestampWithTimezone.from_iso8601("2011-06-11T05:23:31+00:00"),
        id=hash_to_bytes("07382fd255ec0fc293b92aeb7e68b3fe31c174f9"),
    )

    assert_last_visit_matches(
        swh_storage,
        url=ORIGINS[0],
        status="full",
        type="cpan",
        snapshot=expected_snapshot.id,
    )
