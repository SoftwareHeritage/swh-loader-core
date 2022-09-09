# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information
import pytest

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
        "url": "https://crates.io/api/v1/crates/hg-core",
        "artifacts": [
            {
                "checksums": {
                    "sha256": "48a45b46c2a8c38348adb1205b13c3c5eb0174e0c0fec52cc88e9fb1de14c54d",  # noqa: B950
                },
                "filename": "hg-core-0.0.1.crate",
                "url": "https://static.crates.io/crates/hg-core/hg-core-0.0.1.crate",
                "version": "0.0.1",
            },
        ],
    },
    {
        "url": "https://crates.io/api/v1/crates/micro-timer",
        "artifacts": [
            {
                "checksums": {
                    "sha256": "69ad8fd116f8af0298ae4e83e587b1600af12709022471e25581c3aeb1da77ce",  # noqa: B950
                },
                "filename": "micro-timer-0.1.0.crate",
                "url": "https://static.crates.io/crates/micro-timer/micro-timer-0.1.0.crate",
                "version": "0.1.0",
            },
            {
                "checksums": {
                    "sha256": "7b3f65fe0e109daad8d47e1938c9b5f9353efacd86bbe7ff013f84ae7ca758bf",  # noqa: B950
                },
                "filename": "micro-timer-0.1.1.crate",
                "url": "https://static.crates.io/crates/micro-timer/micro-timer-0.1.1.crate",
                "version": "0.1.1",
            },
            {
                "checksums": {
                    "sha256": "16439fea388f712c1df7737ceb8f784d407844624b4796faf1e1bf8bbaa97445",  # noqa: B950
                },
                "filename": "micro-timer-0.1.2.crate",
                "url": "https://static.crates.io/crates/micro-timer/micro-timer-0.1.2.crate",
                "version": "0.1.2",
            },
            {
                "checksums": {
                    "sha256": "336b4c0f071d16674747faa4643d742cc096fec2bf8cf01bb1a98d984bedcaf1",  # noqa: B950
                },
                "filename": "micro-timer-0.2.0.crate",
                "url": "https://static.crates.io/crates/micro-timer/micro-timer-0.2.0.crate",
                "version": "0.2.0",
            },
            {
                "checksums": {
                    "sha256": "987429cd6162a80ed5ff44fc790f5090b1c6d617ac73a2e272965ed91201d79b",  # noqa: B950
                },
                "filename": "micro-timer-0.2.1.crate",
                "url": "https://static.crates.io/crates/micro-timer/micro-timer-0.2.1.crate",
                "version": "0.2.1",
            },
            {
                "checksums": {
                    "sha256": "25b31d6cb9112984323d05d7a353f272ae5d7a307074f9ab9b25c00121b8c947",  # noqa: B950
                },
                "filename": "micro-timer-0.3.0.crate",
                "url": "https://static.crates.io/crates/micro-timer/micro-timer-0.3.0.crate",
                "version": "0.3.0",
            },
            {
                "checksums": {
                    "sha256": "2620153e1d903d26b72b89f0e9c48d8c4756cba941c185461dddc234980c298c",  # noqa: B950
                },
                "filename": "micro-timer-0.3.1.crate",
                "url": "https://static.crates.io/crates/micro-timer/micro-timer-0.3.1.crate",
                "version": "0.3.1",
            },
            {
                "checksums": {
                    "sha256": "5de32cb59a062672560d6f0842c4aa7714727457b9fe2daf8987d995a176a405",  # noqa: B950
                },
                "filename": "micro-timer-0.4.0.crate",
                "url": "https://static.crates.io/crates/micro-timer/micro-timer-0.4.0.crate",
                "version": "0.4.0",
            },
        ],
    },
]


def test_get_versions(requests_mock_datadir, swh_storage):
    loader = CratesLoader(
        swh_storage,
        url=CRATES_EXTRA[1]["url"],
        artifacts=CRATES_EXTRA[1]["artifacts"],
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
        artifacts=CRATES_EXTRA[1]["artifacts"],
    )
    assert loader.get_default_version() == "0.4.0"


def test_crate_invalid_origin_archive_not_found(swh_storage, requests_mock_datadir):
    url = "https://nowhere-to-run/nowhere-to-hide"
    loader = CratesLoader(
        swh_storage,
        url,
        artifacts=[
            {
                "filename": "nowhere-to-hide-0.0.1.crate",
                "url": "https://nowhere-to-run/nowhere-to-hide-0.0.1.crate",
                "version": "0.0.1",
            },
        ],
    )

    with pytest.raises(Exception):
        assert loader.load() == {"status": "failed"}
        assert_last_visit_matches(
            swh_storage, url, status="not_found", type="crates", snapshot=None
        )


def test_crates_loader_load_one_version(datadir, requests_mock_datadir, swh_storage):
    loader = CratesLoader(
        swh_storage,
        url=CRATES_EXTRA[0]["url"],
        artifacts=CRATES_EXTRA[0]["artifacts"],
    )
    actual_load_status = loader.load()
    assert actual_load_status["status"] == "eventful"
    assert actual_load_status["snapshot_id"] is not None

    expected_snapshot_id = "b3affb4949eb89b244f0e1d1fe235fc1d26bde76"
    expected_release_id = "237c4cdd44a90e620795e5a07ebcc72bc82487f7"

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
        message=b"Synthetic release for Crate source package hg-core version 0.0.1\n\n"
        b"Mercurial pure Rust core library, with no assumption "
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
        url=CRATES_EXTRA[1]["url"],
        artifacts=CRATES_EXTRA[1]["artifacts"],
    )

    actual_load_status = loader.load()
    assert actual_load_status["status"] == "eventful"
    assert actual_load_status["snapshot_id"] is not None

    expected_snapshot_id = "3f8ca5908a570fa32270b07a0946bcffa88babd5"
    assert expected_snapshot_id == actual_load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(expected_snapshot_id),
        branches={
            b"releases/0.4.0/micro-timer-0.4.0.crate": SnapshotBranch(
                target=hash_to_bytes("b038a927244c852fb3794aecbebdc70f68ddf067"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.3.1/micro-timer-0.3.1.crate": SnapshotBranch(
                target=hash_to_bytes("ea331a2ce755e6f0cd9d05c9be52accde68536c4"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.3.0/micro-timer-0.3.0.crate": SnapshotBranch(
                target=hash_to_bytes("7ea45f915ace083ed361bb12593625bf4cf1f5f2"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.2.1/micro-timer-0.2.1.crate": SnapshotBranch(
                target=hash_to_bytes("074f27605be8b759e5d7c638f026aac3709f58e5"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.2.0/micro-timer-0.2.0.crate": SnapshotBranch(
                target=hash_to_bytes("a1d642aaa54c5361f67e57adbd86e01f3a3276f8"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.1.2/micro-timer-0.1.2.crate": SnapshotBranch(
                target=hash_to_bytes("60f18ae067ce235bc60243bf5cdaaae474b11978"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.1.1/micro-timer-0.1.1.crate": SnapshotBranch(
                target=hash_to_bytes("fd6c55dfd016d58647a2d44b29a3fd4e3afa7671"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.1.0/micro-timer-0.1.0.crate": SnapshotBranch(
                target=hash_to_bytes("3e07559a4b366a397b1ca154e72753ce27223ca1"),
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
