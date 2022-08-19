# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information
import pytest

from swh.loader.package.arch.loader import ArchLoader
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

EXPECTED_PACKAGES = [
    {
        "url": "https://archive.archlinux.org/packages/d/dialog/",
        "artifacts": [
            {
                "url": "https://archive.archlinux.org/packages/d/dialog/dialog-1:1.3_20190211-1-x86_64.pkg.tar.xz",  # noqa: B950
                "version": "1:1.3_20190211-1",
                "length": 180000,
                "filename": "dialog-1:1.3_20190211-1-x86_64.pkg.tar.xz",
            },
            {
                "url": "https://archive.archlinux.org/packages/d/dialog/dialog-1:1.3_20220414-1-x86_64.pkg.tar.zst",  # noqa: B950
                "version": "1:1.3_20220414-1",
                "length": 198000,
                "filename": "dialog-1:1.3_20220414-1-x86_64.pkg.tar.zst",
            },
        ],
        "arch_metadata": [
            {
                "arch": "x86_64",
                "repo": "core",
                "name": "dialog",
                "version": "1:1.3_20190211-1",
                "last_modified": "2019-02-13T08:36:00",
            },
            {
                "arch": "x86_64",
                "repo": "core",
                "name": "dialog",
                "version": "1:1.3_20220414-1",
                "last_modified": "2022-04-16T03:59:00",
            },
        ],
    },
    {
        "url": "https://archlinuxarm.org/packages/aarch64/gzip",
        "artifacts": [
            {
                "url": "https://uk.mirror.archlinuxarm.org/aarch64/core/gzip-1.12-1-aarch64.pkg.tar.xz",  # noqa: B950
                "length": 79640,
                "version": "1.12-1",
                "filename": "gzip-1.12-1-aarch64.pkg.tar.xz",
            }
        ],
        "arch_metadata": [
            {
                "arch": "aarch64",
                "name": "gzip",
                "repo": "core",
                "version": "1.12-1",
                "last_modified": "2022-04-07T21:08:14",
            }
        ],
    },
]


def test_get_versions(swh_storage):
    loader = ArchLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[0]["url"],
        artifacts=EXPECTED_PACKAGES[0]["artifacts"],
        arch_metadata=EXPECTED_PACKAGES[0]["arch_metadata"],
    )

    assert loader.get_versions() == [
        "1:1.3_20190211-1",
        "1:1.3_20220414-1",
    ]


def test_get_default_version(requests_mock_datadir, swh_storage):
    loader = ArchLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[0]["url"],
        artifacts=EXPECTED_PACKAGES[0]["artifacts"],
        arch_metadata=EXPECTED_PACKAGES[0]["arch_metadata"],
    )
    assert loader.get_default_version() == "1:1.3_20220414-1"


def test_arch_loader_load_one_version(datadir, requests_mock_datadir, swh_storage):
    loader = ArchLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[1]["url"],
        artifacts=EXPECTED_PACKAGES[1]["artifacts"],
        arch_metadata=EXPECTED_PACKAGES[1]["arch_metadata"],
    )
    actual_load_status = loader.load()
    assert actual_load_status["status"] == "eventful"
    assert actual_load_status["snapshot_id"] is not None

    expected_snapshot_id = "4020d0a278027550e336b5481a4159a913c91aa4"
    expected_release_id = "7681098c9e381f9cc8bd1724d57eeee2182982dc"

    assert expected_snapshot_id == actual_load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(actual_load_status["snapshot_id"]),
        branches={
            b"releases/1.12-1/gzip-1.12-1-aarch64.pkg.tar.xz": SnapshotBranch(
                target=hash_to_bytes(expected_release_id),
                target_type=TargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/1.12-1/gzip-1.12-1-aarch64.pkg.tar.xz",
                target_type=TargetType.ALIAS,
            ),
        },
    )
    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 1,
        "directory": 1,
        "origin": 1,
        "origin_visit": 1,
        "release": 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    assert swh_storage.release_get([hash_to_bytes(expected_release_id)])[0] == Release(
        name=b"1.12-1",
        message=b"Synthetic release for Arch Linux source package gzip version "
        b"1.12-1\n\nGNU compression utility\n",
        target=hash_to_bytes("bd742aaf422953a1f7a5e084ec4a7477491d63fb"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
        author=Person.from_fullname(
            b"Arch Linux ARM Build System <builder+seattle@archlinuxarm.org>"
        ),
        date=TimestampWithTimezone.from_iso8601("2022-04-07T21:08:14+00:00"),
        id=hash_to_bytes(expected_release_id),
    )

    assert_last_visit_matches(
        swh_storage,
        url=EXPECTED_PACKAGES[1]["url"],
        status="full",
        type="arch",
        snapshot=expected_snapshot.id,
    )


def test_arch_loader_load_n_versions(datadir, requests_mock_datadir, swh_storage):

    loader = ArchLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[0]["url"],
        artifacts=EXPECTED_PACKAGES[0]["artifacts"],
        arch_metadata=EXPECTED_PACKAGES[0]["arch_metadata"],
    )
    actual_load_status = loader.load()
    assert actual_load_status["status"] == "eventful"
    assert actual_load_status["snapshot_id"] is not None

    expected_snapshot_id = "832139d69a91edffcc3a96cca11deaf9255041c3"

    assert expected_snapshot_id == actual_load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(actual_load_status["snapshot_id"]),
        branches={
            b"releases/1:1.3_20190211-1/"
            b"dialog-1:1.3_20190211-1-x86_64.pkg.tar.xz": SnapshotBranch(
                target=hash_to_bytes("37efb727ff8bb8fbf92518aa8fe5fff2ad427d06"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/1:1.3_20220414-1/"
            b"dialog-1:1.3_20220414-1-x86_64.pkg.tar.zst": SnapshotBranch(
                target=hash_to_bytes("020d3f5627df7474f257fd04f1ede4415296e265"),
                target_type=TargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/1:1.3_20220414-1/dialog-1:1.3_20220414-1-x86_64.pkg.tar.zst",
                target_type=TargetType.ALIAS,
            ),
        },
    )

    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 2,
        "directory": 2,
        "origin": 1,
        "origin_visit": 1,
        "release": 2,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    assert_last_visit_matches(
        swh_storage,
        url=EXPECTED_PACKAGES[0]["url"],
        status="full",
        type="arch",
        snapshot=expected_snapshot.id,
    )


def test_arch_invalid_origin_archive_not_found(swh_storage, requests_mock_datadir):
    url = "https://nowhere/packages/42"
    loader = ArchLoader(
        swh_storage,
        url,
        artifacts=[
            {
                "filename": "42-0.0.1.pkg.xz",
                "url": "https://mirror2.nowhere/pkg/42-0.0.1.pkg.xz",
                "version": "0.0.1",
                "length": 42,
            },
        ],
        arch_metadata=[
            {
                "version": "0.0.1",
                "arch": "aarch64",
                "name": "42",
                "repo": "community",
                "last_modified": "2022-04-07T21:08:14",
            },
        ],
    )
    with pytest.raises(Exception):
        assert loader.load() == {"status": "failed"}
        assert_last_visit_matches(
            swh_storage, url, status="not_found", type="arch", snapshot=None
        )
