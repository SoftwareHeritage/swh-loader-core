# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

# flake8: noqa: B950

import pytest

from swh.loader.package import __version__
from swh.loader.package.cpan.loader import CpanLoader
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.hashutil import hash_to_bytes
from swh.model.model import (
    Person,
    Release,
    Snapshot,
    SnapshotBranch,
    TargetType,
    TimestampWithTimezone,
)
from swh.model.model import ObjectType as ModelObjectType

ORIGIN_URL = "https://metacpan.org/dist/Internals-CountObjects"

API_BASE_URL = "https://fastapi.metacpan.org/v1"

ORIGIN_ARTIFACTS = [
    {
        "url": "https://cpan.metacpan.org/authors/id/J/JJ/JJORE/Internals-CountObjects-0.05.tar.gz",
        "filename": "CountObjects-0.05.tar.gz",
        "version": "0.05",
        "length": 632,
        "checksums": {
            "sha256": "e0ecf6ab4873fa55ff74da22a3c4ae0ab6a1409635c9cd2d6059abbb32be3a6a"
        },
    },
    {
        "url": "https://cpan.metacpan.org/authors/id/J/JJ/JJORE/Internals-CountObjects-0.01.tar.gz",
        "filename": "CountObjects-0.01.tar.gz",
        "version": "0.01",
        "length": 453,
        "checksums": {
            "sha256": "a368004ab98c5860a8fd87e0a4c44e4ee2d1b95d9b13597519a0e644c167468a"
        },
    },
]

ORIGIN_MODULE_METADATA = [
    {
        "name": "Internals-CountObjects",
        "version": "0.05",
        "author": "Josh Jore <jjore@cpan.org>",
        "cpan_author": "JJORE",
        "date": "2011-06-11T05:23:31",
        "release_name": "Internals-CountObjects-0.05",
    },
    {
        "name": "Internals-CountObjects",
        "version": "0.01",
        "author": "Josh Jore <jjore@cpan.org>",
        "cpan_author": "JJORE",
        "date": "2011-06-05T18:44:02",
        "release_name": "Internals-CountObjects-0.01",
    },
]


@pytest.fixture
def cpan_loader(requests_mock_datadir, swh_storage):
    return CpanLoader(
        swh_storage,
        url=ORIGIN_URL,
        api_base_url=API_BASE_URL,
        artifacts=ORIGIN_ARTIFACTS,
        module_metadata=ORIGIN_MODULE_METADATA,
    )


def test_get_versions(cpan_loader):
    assert cpan_loader.get_versions() == ["0.01", "0.05"]


def test_get_default_version(cpan_loader):
    assert cpan_loader.get_default_version() == "0.05"


def test_cpan_loader_load_multiple_version(cpan_loader):

    load_status = cpan_loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    expected_snapshot_id = "848ee8d69d33481c88ab81f6794f6504190f011f"
    expected_head_release = "07382fd255ec0fc293b92aeb7e68b3fe31c174f9"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/0.01": SnapshotBranch(
                target=hash_to_bytes("e73aced4cc3d56b32a328d3248b25b052f029df4"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.05": SnapshotBranch(
                target=hash_to_bytes(expected_head_release),
                target_type=TargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/0.05",
                target_type=TargetType.ALIAS,
            ),
        },
    )

    storage = cpan_loader.storage

    check_snapshot(expected_snapshot, storage)

    stats = get_stats(storage)
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

    head_release = storage.release_get([hash_to_bytes(expected_head_release)])[0]

    assert head_release == Release(
        name=b"0.05",
        message=b"Synthetic release for Perl source package Internals-CountObjects version 0.05\n",
        target=hash_to_bytes("af3f6a43eaf4b26dbcadb1101e8d81db6d6151e0"),
        target_type=ModelObjectType.DIRECTORY,
        synthetic=True,
        author=Person(
            fullname=b"Josh Jore <jjore@cpan.org>",
            name=b"Josh Jore",
            email=b"jjore@cpan.org",
        ),
        date=TimestampWithTimezone.from_iso8601("2011-06-11T05:23:31+00:00"),
        id=hash_to_bytes(expected_head_release),
    )

    assert_last_visit_matches(
        storage,
        url=ORIGIN_URL,
        status="full",
        type="cpan",
        snapshot=expected_snapshot.id,
    )
