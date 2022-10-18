# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from swh.loader.package.puppet.loader import PuppetLoader
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

ORIGINS = {
    "url": "https://forge.puppet.com/modules/saz/memcached",
    "artifacts": {
        "1.0.0": {
            "url": "https://forgeapi.puppet.com/v3/files/saz-memcached-1.0.0.tar.gz",  # noqa: B950
            "version": "1.0.0",
            "filename": "saz-memcached-1.0.0.tar.gz",
            "last_update": "2011-11-20T13:40:30-08:00",
            "checksums": {
                "length": 763,
            },
        },
        "8.1.0": {
            "url": "https://forgeapi.puppet.com/v3/files/saz-memcached-8.1.0.tar.gz",  # noqa: B950
            "version": "8.1.0",
            "filename": "saz-memcached-8.1.0.tar.gz",
            "last_update": "2022-07-11T03:34:55-07:00",
            "checksums": {
                "md5": "5313e8fff0af08d63681daf955e7a604",
                "sha256": "0dbb1470c64435700767e9887d0cf70203b1ae59445c401d5d200f2dabb3226e",  # noqa: B950
            },
        },
    },
}


def test_get_versions(requests_mock_datadir, swh_storage):
    loader = PuppetLoader(
        swh_storage, url=ORIGINS["url"], artifacts=ORIGINS["artifacts"]
    )
    assert loader.get_versions() == ["1.0.0", "8.1.0"]


def test_get_default_version(requests_mock_datadir, swh_storage):
    loader = PuppetLoader(
        swh_storage, url=ORIGINS["url"], artifacts=ORIGINS["artifacts"]
    )
    assert loader.get_default_version() == "8.1.0"


def test_puppet_loader_load_multiple_version(
    datadir, requests_mock_datadir, swh_storage
):
    loader = PuppetLoader(
        swh_storage, url=ORIGINS["url"], artifacts=ORIGINS["artifacts"]
    )
    load_status = loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    expected_snapshot_id = "9a8e76a8a6eae5285059d9f6d5083a99317727cf"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"HEAD": SnapshotBranch(
                target=b"releases/8.1.0",
                target_type=TargetType.ALIAS,
            ),
            b"releases/1.0.0": SnapshotBranch(
                target=hash_to_bytes("50eb560bb5322cd149359b9cc8debc78834bcfad"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/8.1.0": SnapshotBranch(
                target=hash_to_bytes("2f5722136d775dd48fe85fabdd274f1e2d7fcf22"),
                target_type=TargetType.RELEASE,
            ),
        },
    )

    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 1 + 1,
        "directory": 2 + 2,
        "origin": 1,
        "origin_visit": 1,
        "release": 1 + 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    assert swh_storage.release_get(
        [hash_to_bytes("2f5722136d775dd48fe85fabdd274f1e2d7fcf22")]
    )[0] == Release(
        name=b"8.1.0",
        message=b"Synthetic release for Puppet source package saz-memcached version 8.1.0\n\n"
        b"Manage memcached via Puppet\n",
        target=hash_to_bytes("1b9a2dbc80f954e1ba4b2f1c6344d1ce4e84ab7c"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
        author=Person(fullname=b"saz", name=b"saz", email=None),
        date=TimestampWithTimezone.from_iso8601("2022-07-11T03:34:55-07:00"),
        id=hash_to_bytes("2f5722136d775dd48fe85fabdd274f1e2d7fcf22"),
    )

    assert_last_visit_matches(
        swh_storage,
        url=ORIGINS["url"],
        status="full",
        type="puppet",
        snapshot=expected_snapshot.id,
    )
