# Copyright (C) 2022-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import pytest

from swh.loader.core.utils import EMPTY_AUTHOR
from swh.loader.package.pubdev.loader import PubDevLoader
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.hashutil import hash_to_bytes
from swh.model.model import (
    ObjectType,
    Person,
    Release,
    Snapshot,
    SnapshotBranch,
    SnapshotTargetType,
    TimestampWithTimezone,
)

EXPECTED_PACKAGES = [
    {
        "url": "https://pub.dev/packages/Autolinker",  # one version
    },
    {
        "url": "https://pub.dev/packages/pdf",  # multiple versions
    },
    {
        "url": "https://pub.dev/packages/bezier",  # multiple authors
    },
    {
        "url": "https://pub.dev/packages/authentication",  # empty author
    },
    {
        "url": "https://pub.dev/packages/abstract_io",  # loose versions names
    },
    {
        "url": "https://pub.dev/packages/audio_manager",  # loose ++ versions names
    },
    {
        "url": "https://pub.dev/packages/yust",  # package with dash in version number
    },
]


def test_get_versions(requests_mock_datadir, swh_storage):
    loader = PubDevLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[1]["url"],
    )
    assert loader.get_versions() == [
        "1.0.0",
        "3.8.2",
    ]


def test_sort_loose_versions(requests_mock_datadir, swh_storage):
    """Sometimes version name does not follow semver"""
    loader = PubDevLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[4]["url"],
    )
    assert loader.get_versions() == ["0.1.2+4", "0.1.2+5", "0.1.2+6"]


def test_sort_loose_versions_1(requests_mock_datadir, swh_storage):
    """Sometimes version name does not follow semver and mix patterns"""
    loader = PubDevLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[5]["url"],
    )
    assert loader.get_versions() == [
        "0.0.1",
        "0.0.2",
        "0.1.1",
        "0.1.2",
        "0.1.3",
        "0.1.4",
        "0.1.5",
        "0.2.1",
        "0.2.1+hotfix.1",
        "0.2.1+hotfix.2",
        "0.2.1+3",
        "0.3.1",
        "0.3.1+1",
        "0.5.1",
        "0.5.1+1",
        "0.5.1+2",
        "0.5.1+3",
        "0.5.1+4",
        "0.5.1+5",
        "0.5.2",
        "0.5.2+1",
        "0.5.3",
        "0.5.3+1",
        "0.5.3+2",
        "0.5.3+3",
        "0.5.4",
        "0.5.4+1",
        "0.5.5",
        "0.5.5+1",
        "0.5.5+2",
        "0.5.5+3",
        "0.5.6",
        "0.5.7",
        "0.5.7+1",
        "0.6.1",
        "0.6.2",
        "0.7.1",
        "0.7.2",
        "0.7.3",
        "0.8.1",
        "0.8.2",
    ]


def test_get_default_version(requests_mock_datadir, swh_storage):
    loader = PubDevLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[1]["url"],
    )
    assert loader.get_default_version() == "3.8.2"


def test_pubdev_loader_load_one_version(datadir, requests_mock_datadir, swh_storage):
    loader = PubDevLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[0]["url"],
    )
    load_status = loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    expected_snapshot_id = "dffca49aec93fcf1fa63fa25bf9a04c833a30d73"
    expected_release_id = "1e2e7226ac9136f2eb7ce28f32ca08fff28590b1"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/0.1.1": SnapshotBranch(
                target=hash_to_bytes(expected_release_id),
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/0.1.1",
                target_type=SnapshotTargetType.ALIAS,
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
        name=b"0.1.1",
        message=b"Synthetic release for pub.dev source package Autolinker version 0.1.1\n",
        target=hash_to_bytes("3fb6d4f2c0334d1604357ae92b2dd38a55a78194"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
        author=Person(
            fullname=b"hackcave <hackers@hackcave.org>",
            name=b"hackcave",
            email=b"hackers@hackcave.org",
        ),
        date=TimestampWithTimezone.from_iso8601("2014-12-24T22:34:02.534090+00:00"),
        id=hash_to_bytes(expected_release_id),
    )

    assert_last_visit_matches(
        swh_storage,
        url=EXPECTED_PACKAGES[0]["url"],
        status="full",
        type="pubdev",
        snapshot=expected_snapshot.id,
    )


def test_pubdev_loader_load_multiple_versions(
    datadir, requests_mock_datadir, swh_storage
):
    loader = PubDevLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[1]["url"],
    )
    load_status = loader.load()

    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    expected_snapshot_id = "b03a4ef56b1a3bd4812f8e37f439c261cf4fd2c7"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/1.0.0": SnapshotBranch(
                target=hash_to_bytes("6f6eecd1ced321778d6a4bc60af4fb0e93178307"),
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"releases/3.8.2": SnapshotBranch(
                target=hash_to_bytes("012bac381e2b9cda7de2da0391bc2969bf80ff97"),
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/3.8.2",
                target_type=SnapshotTargetType.ALIAS,
            ),
        },
    )

    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 1 + 1,
        "directory": 1 + 1,
        "origin": 1,
        "origin_visit": 1,
        "release": 1 + 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    assert_last_visit_matches(
        swh_storage,
        url=EXPECTED_PACKAGES[1]["url"],
        status="full",
        type="pubdev",
        snapshot=expected_snapshot.id,
    )


def test_pubdev_loader_multiple_authors(datadir, requests_mock_datadir, swh_storage):
    loader = PubDevLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[2]["url"],
    )
    load_status = loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    expected_snapshot_id = "2af571a302514bf17807dc114fff15501f8c1387"
    expected_release_id = "87331a7804673cb00a339b504d2345769b7ae34a"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/1.1.5": SnapshotBranch(
                target=hash_to_bytes(expected_release_id),
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/1.1.5",
                target_type=SnapshotTargetType.ALIAS,
            ),
        },
    )

    check_snapshot(expected_snapshot, swh_storage)

    release = swh_storage.release_get([hash_to_bytes(expected_release_id)])[0]
    assert release.author == Person(
        fullname=b"Aaron Barrett <aaron@aaronbarrett.com>",
        name=b"Aaron Barrett",
        email=b"aaron@aaronbarrett.com",
    )


def test_pubdev_loader_empty_author(datadir, requests_mock_datadir, swh_storage):
    loader = PubDevLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[3]["url"],
    )

    load_status = loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    expected_snapshot_id = "8b86c9fb49bbf3e2b4513dc35a2838c67e8895bc"
    expected_release_id = "d6ba845e28fba2a51e2ed358664cad645a2591ca"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/0.0.1": SnapshotBranch(
                target=hash_to_bytes(expected_release_id),
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/0.0.1",
                target_type=SnapshotTargetType.ALIAS,
            ),
        },
    )

    check_snapshot(expected_snapshot, swh_storage)

    release = swh_storage.release_get([hash_to_bytes(expected_release_id)])[0]
    assert release.author == EMPTY_AUTHOR


def test_pubdev_invalid_origin(swh_storage):
    with pytest.raises(AssertionError):
        PubDevLoader(
            swh_storage,
            "http://nowhere/api/packages/42",
        )


def test_pubdev_loader_dash_in_package_version(requests_mock_datadir, swh_storage):
    loader = PubDevLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[6]["url"],
    )

    load_status = loader.load()
    assert load_status["status"] == "eventful"

    expected_snapshot_id = "feb1fa3f17fc011fc0f86b596a91da6dcad23d0f"

    expected_snapshot = Snapshot(
        branches={
            b"HEAD": SnapshotBranch(
                target=hash_to_bytes("72656c65617365732f332e362e31"),
                target_type=SnapshotTargetType.ALIAS,
            ),
            b"releases/2.0.0-nullsafety.1": SnapshotBranch(
                target=hash_to_bytes("12156dabe4eb0aaf95810b2e779a61b42c057119"),
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"releases/3.6.1": SnapshotBranch(
                target=hash_to_bytes("3af5c2b85f0d3ab16577ec2f0886367b12d41aab"),
                target_type=SnapshotTargetType.RELEASE,
            ),
        },
        id=hash_to_bytes(expected_snapshot_id),
    )

    check_snapshot(expected_snapshot, swh_storage)
