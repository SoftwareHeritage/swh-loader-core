# Copyright (C) 2022-2025  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import gzip
import hashlib
import os
from pathlib import Path

import pytest

from swh.core.tarball import uncompress
from swh.loader.core import __version__
from swh.loader.package.rubygems.loader import RubyGemsLoader
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model import from_disk
from swh.model.hashutil import hash_to_hex
from swh.model.model import (
    MetadataFetcher,
    Person,
    RawExtrinsicMetadata,
    Release,
    ReleaseTargetType,
    Snapshot,
    SnapshotBranch,
    SnapshotTargetType,
    TimestampWithTimezone,
)
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
            "version": "0.0.2",
            "extrinsic_metadata_url": "https://rubygems.org/api/v2/rubygems/haar_joke/versions/0.0.2.json",  # noqa: B950
        },
        {
            "date": "2016-07-23T00:00:00+00:00",
            "version": "0.0.1",
            "extrinsic_metadata_url": "https://rubygems.org/api/v2/rubygems/haar_joke/versions/0.0.1.json",  # noqa: B950
        },
    ],
}


def test_get_sorted_versions(requests_mock_datadir, swh_storage):
    loader = RubyGemsLoader(
        swh_storage,
        url=ORIGIN["url"],
        artifacts=ORIGIN["artifacts"],
        rubygem_metadata=ORIGIN["rubygem_metadata"],
    )
    assert loader.get_sorted_versions() == ["0.0.1", "0.0.2"]


def test_get_default_version(requests_mock_datadir, swh_storage):
    loader = RubyGemsLoader(
        swh_storage,
        url=ORIGIN["url"],
        artifacts=ORIGIN["artifacts"],
        rubygem_metadata=ORIGIN["rubygem_metadata"],
    )
    assert loader.get_default_version() == "0.0.2"


def uncompress_gem_package(datadir, tmp_path, package_filename):
    tarball_path = os.path.join(datadir, "https_rubygems.org", package_filename)
    uncompress_path = os.path.join(
        tmp_path, hashlib.sha1(package_filename.encode()).hexdigest()
    )
    uncompress(tarball_path, uncompress_path)
    contents_uncompressed_path = os.path.join(uncompress_path, "data")
    contents_tarball_path = os.path.join(uncompress_path, "data.tar.gz")
    metadata_path = os.path.join(uncompress_path, "metadata.gz")
    with gzip.open(metadata_path) as metadata_stream:
        metadata_bytes = metadata_stream.read()
    uncompress(contents_tarball_path, contents_uncompressed_path)
    return (
        from_disk.Directory.from_disk(
            path=contents_uncompressed_path.encode("utf-8"), max_content_length=None
        ),
        metadata_bytes,
    )


@pytest.fixture
def release_0_0_1_dir(datadir, tmp_path):
    return uncompress_gem_package(datadir, tmp_path, "downloads_haar_joke-0.0.1.gem")[0]


@pytest.fixture
def release_0_0_2_dir(datadir, tmp_path):
    return uncompress_gem_package(datadir, tmp_path, "downloads_haar_joke-0.0.2.gem")[0]


@pytest.fixture
def release_0_0_1(release_0_0_1_dir):
    return Release(
        name=b"0.0.1",
        message=b"Synthetic release for RubyGems source package haar_joke version 0.0.1\n",
        target=release_0_0_1_dir.hash,
        target_type=ReleaseTargetType.DIRECTORY,
        synthetic=True,
        author=Person(
            fullname=b"Gemma Gotch <pveggie@hotmail.com>",
            name=b"Gemma Gotch",
            email=b"pveggie@hotmail.com",
        ),
        date=TimestampWithTimezone.from_iso8601("2016-07-23T00:00:00+00:00"),
    )


@pytest.fixture
def release_0_0_2(release_0_0_2_dir):
    return Release(
        name=b"0.0.2",
        message=b"Synthetic release for RubyGems source package haar_joke version 0.0.2\n",
        target=release_0_0_2_dir.hash,
        target_type=ReleaseTargetType.DIRECTORY,
        synthetic=True,
        author=Person(
            fullname=b"Gemma Gotch <pveggie@hotmail.com>",
            name=b"Gemma Gotch",
            email=b"pveggie@hotmail.com",
        ),
        date=TimestampWithTimezone.from_iso8601("2016-11-05T00:00:00+00:00"),
    )


@pytest.fixture
def head_release_extrinsic_metadata_json(datadir):
    return Path(
        datadir,
        "https_rubygems.org",
        "api_v2_rubygems_haar_joke_versions_0.0.2.json",
    ).read_bytes()


@pytest.fixture
def head_release_extrinsic_metadata_yaml(datadir, tmp_path):
    return uncompress_gem_package(datadir, tmp_path, "downloads_haar_joke-0.0.2.gem")[1]


@pytest.fixture
def expected_stats(release_0_0_1_dir, release_0_0_2_dir) -> dict:
    release_0_0_1_cnts, _, release_0_0_1_dirs = from_disk.iter_directory(
        release_0_0_1_dir
    )
    release_0_0_2_cnts, _, release_0_0_2_dirs = from_disk.iter_directory(
        release_0_0_2_dir
    )
    return {
        "content": len(set(release_0_0_1_cnts) | set(release_0_0_2_cnts)),
        "directory": len(set(release_0_0_1_dirs) | set(release_0_0_2_dirs)),
        "origin": 1,
        "origin_visit": 1,
        "release": 2,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    }


def test_rubygems_loader(
    swh_storage,
    requests_mock_datadir,
    head_release_extrinsic_metadata_json,
    head_release_extrinsic_metadata_yaml,
    release_0_0_1,
    release_0_0_2,
    expected_stats,
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

    expected_snapshot = Snapshot(
        branches={
            b"releases/0.0.1": SnapshotBranch(
                target=release_0_0_1.id,
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"releases/0.0.2": SnapshotBranch(
                target=release_0_0_2.id,
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/0.0.2",
                target_type=SnapshotTargetType.ALIAS,
            ),
        },
    )

    assert hash_to_hex(expected_snapshot.id) == load_status["snapshot_id"]

    check_snapshot(expected_snapshot, loader.storage)

    stats = get_stats(swh_storage)
    assert expected_stats == stats

    assert_last_visit_matches(
        loader.storage,
        url=ORIGIN["url"],
        status="full",
        type="rubygems",
        snapshot=expected_snapshot.id,
    )

    release_swhid = CoreSWHID(
        object_type=ObjectType.RELEASE, object_id=release_0_0_2.id
    )
    directory_swhid = ExtendedSWHID(
        object_type=ExtendedObjectType.DIRECTORY, object_id=release_0_0_2.target
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
            metadata=head_release_extrinsic_metadata_json,
            origin=ORIGIN["url"],
            release=release_swhid,
        ),
        RawExtrinsicMetadata(
            target=directory_swhid,
            authority=loader.get_metadata_authority(),
            fetcher=MetadataFetcher(
                name="swh.loader.package.rubygems.loader.RubyGemsLoader",
                version=__version__,
            ),
            discovery_date=loader.visit_date,
            format="rubygem-release-yaml",
            metadata=head_release_extrinsic_metadata_yaml,
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


def test_rubygems_loader_authors_extraction_from_metadata(
    swh_storage,
    requests_mock_datadir,
):
    loader = RubyGemsLoader(
        swh_storage,
        url="https://rubygems.org/gems/flurin-ticgit",
        artifacts=[
            {
                "url": "https://rubygems.org/downloads/flurin-ticgit-0.3.7.gem",
                "length": 14336,
                "version": "0.3.7",
                "filename": "flurin-ticgit-0.3.7.gem",
                "checksums": {
                    "sha256": "031ee86f4954e4d421bd3334dfdd128a377ea41d042c24f5f9226d57c006032b"
                },
            }
        ],
        rubygem_metadata=[
            {
                "date": "2016-07-23T00:00:00+00:00",
                "version": "0.3.7",
                "extrinsic_metadata_url": "https://rubygems.org/api/v2/rubygems/flurin-ticgit/versions/0.3.7.json",  # noqa: B950
            }
        ],
    )
    load_status = loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    snapshot = loader.last_snapshot()
    release_id = snapshot.branches[b"releases/0.3.7"].target
    release = swh_storage.release_get([release_id])[0]
    assert release.author == Person(
        fullname=b"Scott Chacon <schacon@gmail.com>",
        name=b"Scott Chacon",
        email=b"schacon@gmail.com",
    )

    assert (
        release.message
        == (
            "Synthetic release for RubyGems source package flurin-ticgit version 0.3.7\n\n"
            "Co-authored-by: Mislav Marohnić\n"
            "Co-authored-by: Flurin Egger\n"
        ).encode()
    )
