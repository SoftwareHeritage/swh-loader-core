# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import pytest

from swh.loader.package.pubdev.loader import PubDevLoader
from swh.loader.package.utils import EMPTY_AUTHOR
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

    expected_snapshot_id = "245092931ba809e6c54ebda8f865fb5a969a4134"
    expected_release_id = "919f267ea050539606344d49d14bf594c4386e5a"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/0.1.1": SnapshotBranch(
                target=hash_to_bytes(expected_release_id),
                target_type=TargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/0.1.1",
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
        name=b"0.1.1",
        message=b"Synthetic release for pub.dev source package Autolinker version"
        b" 0.1.1\n\nPort of Autolinker.js to dart\n",
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

    expected_snapshot_id = "43d5b68a9fa973aa95e56916aaef70841ccbc2a0"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/1.0.0": SnapshotBranch(
                target=hash_to_bytes("fbf8e40af675096681954553d737861e10b57216"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/3.8.2": SnapshotBranch(
                target=hash_to_bytes("627a5d586e3fb4e7319b17f1aee268fe2fb8e01c"),
                target_type=TargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/3.8.2",
                target_type=TargetType.ALIAS,
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

    expected_snapshot_id = "4fa9f19d1d6ccc70921c8c50b278f510db63aa36"
    expected_release_id = "538c98fd69a42d8d0561a7ca95b354de2143a3ab"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/1.1.5": SnapshotBranch(
                target=hash_to_bytes(expected_release_id),
                target_type=TargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/1.1.5",
                target_type=TargetType.ALIAS,
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

    expected_snapshot_id = "0c7fa6b9fced23c648d2093ad5597622683f8aed"
    expected_release_id = "7d8c05181069aa1049a3f0bc1d13bedc34625d47"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/0.0.1": SnapshotBranch(
                target=hash_to_bytes(expected_release_id),
                target_type=TargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/0.0.1",
                target_type=TargetType.ALIAS,
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
