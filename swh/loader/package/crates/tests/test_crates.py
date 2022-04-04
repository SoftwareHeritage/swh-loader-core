# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information
from swh.loader.package.crates.loader import CratesLoader
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

CRATES_EXTRA = [
    {
        "name": "hg-core",
        "version": "0.0.1",
        "url": "https://static.crates.io/crates/hg-core/hg-core-0.0.1.crate",
        "checksum": "7fe168efadebadb9da6a329fdc027036e233b662285730cad27220e11e53c384",
    },
    {
        "name": "micro-timer",
        "version": "0.4.0",
        "url": "https://static.crates.io/crates/micro-timer/micro-timer-0.4.0.crate",
        "checksum": "5de32cb59a062672560d6f0842c4aa7714727457b9fe2daf8987d995a176a405",
    },
]


def test_get_versions(requests_mock_datadir, swh_storage):
    loader = CratesLoader(
        swh_storage,
        url=CRATES_EXTRA[1]["url"],
        package_name=CRATES_EXTRA[1]["name"],
        version=CRATES_EXTRA[1]["version"],
    )
    assert loader.get_versions() == [
        "0.1.0",
        "0.1.1",
        "0.1.2",
        "0.2.0",
        "0.2.1",
        "0.3.0",
        "0.3.1",
        "0.4.0",
    ]


def test_get_default_version(requests_mock_datadir, swh_storage):
    loader = CratesLoader(
        swh_storage,
        url=CRATES_EXTRA[1]["url"],
        package_name=CRATES_EXTRA[1]["name"],
        version=CRATES_EXTRA[1]["version"],
    )
    assert loader.get_default_version() == "0.4.0"


def test_crate_origin_not_found(swh_storage, requests_mock_datadir):
    url = "https://nowhere-to-run/nowhere-to-hide-0.0.1.crate"
    loader = CratesLoader(
        swh_storage,
        url,
        package_name="nowhere-to-hide",
        version="0.0.1",
    )

    assert loader.load() == {"status": "failed"}

    assert_last_visit_matches(
        swh_storage, url, status="not_found", type="crates", snapshot=None
    )


def test_crates_loader_load_one_version(datadir, requests_mock_datadir, swh_storage):
    loader = CratesLoader(
        swh_storage,
        url=CRATES_EXTRA[0]["url"],
        package_name=CRATES_EXTRA[0]["name"],
        version=CRATES_EXTRA[0]["version"],
    )
    actual_load_status = loader.load()
    assert actual_load_status["status"] == "eventful"
    assert actual_load_status["snapshot_id"] is not None

    expected_snapshot_id = "353cd6858c88ee8210432ea1098993c2e9966561"
    expected_release_id = "d578833534017430f1b93eb741620899620c2505"

    assert expected_snapshot_id == actual_load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(actual_load_status["snapshot_id"]),
        branches={
            b"releases/0.0.1/hg-core-0.0.1.crate": SnapshotBranch(
                target=hash_to_bytes(expected_release_id),
                target_type=TargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/0.0.1/hg-core-0.0.1.crate",
                target_type=TargetType.ALIAS,
            ),
        },
    )
    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 1,
        "directory": 2,
        "origin": 1,
        "origin_visit": 1,
        "release": 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    assert swh_storage.release_get([hash_to_bytes(expected_release_id)])[0] == Release(
        name=b"0.0.1",
        message=b"Synthetic release for Crate source package hg-core version "
        b"0.0.1\nMercurial pure Rust core library, with no assumption "
        b"on Python bindings (FFI)\n",
        target=hash_to_bytes("674c3b0b54628d55b93a79dc7adf304efc01b371"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
        author=Person.from_fullname(b"Georges Racinet <georges.racinet@octobus.net>"),
        date=TimestampWithTimezone.from_iso8601("2019-04-16T18:48:11.404457+00:00"),
        id=hash_to_bytes(expected_release_id),
    )


def test_crates_loader_load_n_versions(datadir, requests_mock_datadir, swh_storage):
    url = CRATES_EXTRA[1]["url"]
    loader = CratesLoader(
        swh_storage,
        url=url,
        package_name=CRATES_EXTRA[1]["name"],
        version=CRATES_EXTRA[1]["version"],
        checksum=CRATES_EXTRA[1]["checksum"],
    )
    actual_load_status = loader.load()
    assert actual_load_status["status"] == "eventful"
    assert actual_load_status["snapshot_id"] is not None

    expected_snapshot_id = "016cbbe3bb78424c35b898015a2d80d79359e2ad"
    assert expected_snapshot_id == actual_load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(expected_snapshot_id),
        branches={
            b"releases/0.4.0/micro-timer-0.4.0.crate": SnapshotBranch(
                target=hash_to_bytes("3237c1174c4ccfa8e934d1bfd8d80b3a89760e39"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.3.1/micro-timer-0.3.1.crate": SnapshotBranch(
                target=hash_to_bytes("8b727a280051cdb90468ede2746e176e6fdf355f"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.3.0/micro-timer-0.3.0.crate": SnapshotBranch(
                target=hash_to_bytes("f45ec236ae50fb37e924a3d2cc093e72b6cbf1cd"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.2.1/micro-timer-0.2.1.crate": SnapshotBranch(
                target=hash_to_bytes("50a60a2c3696df7cd1b623bd7dbea2c89b994e42"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.2.0/micro-timer-0.2.0.crate": SnapshotBranch(
                target=hash_to_bytes("f0592dc0ae05399d872017d0260c45b875cb590e"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.1.2/micro-timer-0.1.2.crate": SnapshotBranch(
                target=hash_to_bytes("9220d7823fc40ab44e3ae3227522e7de672fad3e"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.1.1/micro-timer-0.1.1.crate": SnapshotBranch(
                target=hash_to_bytes("38529b7e355f79fdce31a3ba891e146174e10237"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.1.0/micro-timer-0.1.0.crate": SnapshotBranch(
                target=hash_to_bytes("5e5e6120af55b65c577e09331df54e70fad5e8b0"),
                target_type=TargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/0.4.0/micro-timer-0.4.0.crate",
                target_type=TargetType.ALIAS,
            ),
        },
    )

    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 8,
        "directory": 16,
        "origin": 1,
        "origin_visit": 1,
        "release": 8,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    assert_last_visit_matches(
        swh_storage,
        url,
        status="full",
        type="crates",
        snapshot=expected_snapshot.id,
    )
