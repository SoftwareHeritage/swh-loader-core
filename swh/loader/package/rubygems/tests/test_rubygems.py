# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from pathlib import Path

import pytest

from swh.loader.package import __version__
from swh.loader.package.rubygems.loader import RubyGemsLoader
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.hashutil import hash_to_bytes
from swh.model.model import (
    Person,
    RawExtrinsicMetadata,
    Release,
    Snapshot,
    SnapshotBranch,
    TargetType,
    TimestampWithTimezone,
)
from swh.model.model import MetadataFetcher
from swh.model.model import ObjectType as ModelObjectType
from swh.model.swhids import CoreSWHID, ExtendedObjectType, ExtendedSWHID, ObjectType

ORIGIN = {
    "url": "https://rubygems.org/gems/haar_joke",
    "artifacts": [
        {
            "url": "https://rubygems.org/downloads/haar_joke-0.0.2.gem",
            "length": 8704,
            "version": "0.0.2",
            "filename": "haar_joke-0.0.2.gem",
            "checksums": {
                "sha256": "85a8cf5f41890e9605265eeebfe9e99aa0350a01a3c799f9f55a0615a31a2f5f"
            },
        },
        {
            "url": "https://rubygems.org/downloads/haar_joke-0.0.1.gem",
            "length": 8704,
            "version": "0.0.1",
            "filename": "haar_joke-0.0.1.gem",
            "checksums": {
                "sha256": "a2ee7052fb8ffcfc4ec0fdb77fae9a36e473f859af196a36870a0f386b5ab55e"
            },
        },
    ],
    "rubygem_metadata": [
        {
            "date": "2016-11-05T00:00:00+00:00",
            "authors": "Gemma Gotch",
            "version": "0.0.2",
            "extrinsic_metadata_url": "https://rubygems.org/api/v2/rubygems/haar_joke/versions/0.0.2.json",  # noqa: B950
        },
        {
            "date": "2016-07-23T00:00:00+00:00",
            "authors": "Gemma Gotch",
            "version": "0.0.1",
            "extrinsic_metadata_url": "https://rubygems.org/api/v2/rubygems/haar_joke/versions/0.0.1.json",  # noqa: B950
        },
    ],
}


@pytest.fixture
def head_release_extrinsic_metadata(datadir):
    return Path(
        datadir,
        "https_rubygems.org",
        "api_v2_rubygems_haar_joke_versions_0.0.2.json",
    ).read_bytes()


def test_get_versions(requests_mock_datadir, swh_storage):
    loader = RubyGemsLoader(
        swh_storage,
        url=ORIGIN["url"],
        artifacts=ORIGIN["artifacts"],
        rubygem_metadata=ORIGIN["rubygem_metadata"],
    )
    assert loader.get_versions() == ["0.0.1", "0.0.2"]


def test_get_default_version(requests_mock_datadir, swh_storage):
    loader = RubyGemsLoader(
        swh_storage,
        url=ORIGIN["url"],
        artifacts=ORIGIN["artifacts"],
        rubygem_metadata=ORIGIN["rubygem_metadata"],
    )
    assert loader.get_default_version() == "0.0.2"


def test_rubygems_loader(
    swh_storage, requests_mock_datadir, head_release_extrinsic_metadata
):
    loader = RubyGemsLoader(
        swh_storage,
        url=ORIGIN["url"],
        artifacts=ORIGIN["artifacts"],
        rubygem_metadata=ORIGIN["rubygem_metadata"],
    )
    load_status = loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    expected_snapshot_id = "7a646532d6fdd7df84e35d64bf1f3da9ddbd0971"
    expected_head_release = "afd15d9042873b8082218433f5dd4db1024defc1"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/0.0.1": SnapshotBranch(
                target=hash_to_bytes("604dbd4f9768e952ae63249edc4084bf0fe85a8c"),
                target_type=TargetType.RELEASE,
            ),
            b"releases/0.0.2": SnapshotBranch(
                target=hash_to_bytes(expected_head_release),
                target_type=TargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/0.0.2",
                target_type=TargetType.ALIAS,
            ),
        },
    )

    check_snapshot(expected_snapshot, loader.storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 23,
        "directory": 7,
        "origin": 1,
        "origin_visit": 1,
        "release": 1 + 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    head_release = loader.storage.release_get([hash_to_bytes(expected_head_release)])[0]

    assert head_release == Release(
        name=b"0.0.2",
        message=b"Synthetic release for RubyGems source package haar_joke version 0.0.2\n",
        target=hash_to_bytes("8af199118ef7f6b6c312bcf09c77552442b87a45"),
        target_type=ModelObjectType.DIRECTORY,
        synthetic=True,
        author=Person(
            fullname=b"Gemma Gotch",
            name=b"",
            email=None,
        ),
        date=TimestampWithTimezone.from_iso8601("2016-11-05T00:00:00+00:00"),
        id=hash_to_bytes(expected_head_release),
    )

    assert_last_visit_matches(
        loader.storage,
        url=ORIGIN["url"],
        status="full",
        type="rubygems",
        snapshot=expected_snapshot.id,
    )

    release_swhid = CoreSWHID(object_type=ObjectType.RELEASE, object_id=head_release.id)
    directory_swhid = ExtendedSWHID(
        object_type=ExtendedObjectType.DIRECTORY, object_id=head_release.target
    )
    expected_metadata = [
        RawExtrinsicMetadata(
            target=directory_swhid,
            authority=loader.get_metadata_authority(),
            fetcher=MetadataFetcher(
                name="swh.loader.package.rubygems.loader.RubyGemsLoader",
                version=__version__,
            ),
            discovery_date=loader.visit_date,
            format="rubygem-release-json",
            metadata=head_release_extrinsic_metadata,
            origin=ORIGIN["url"],
            release=release_swhid,
        ),
    ]

    assert (
        loader.storage.raw_extrinsic_metadata_get(
            directory_swhid,
            loader.get_metadata_authority(),
        ).results
        == expected_metadata
    )
