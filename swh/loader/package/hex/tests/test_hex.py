import hashlib
import os
from pathlib import Path
from typing import List

import pytest

from swh.core.tarball import uncompress
from swh.loader.core import __version__
from swh.loader.package.hex.loader import HexLoader
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model import from_disk
from swh.model.hashutil import hash_to_bytes, hash_to_hex
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

ORIGIN = "https://hex.pm/packages/gpio"

RELEASES = {
    "0.6.0": {
        "name": "gpio",
        "release_url": "https://hex.pm/api/packages/gpio/releases/0.6.0",
        "tarball_url": "https://repo.hex.pm/tarballs/gpio-0.6.0.tar",
        "inserted_at": "2023-02-05T09:55:17.707695Z",
    },
    "0.6.1": {
        "name": "gpio",
        "release_url": "https://hex.pm/api/packages/gpio/releases/0.6.1",
        "tarball_url": "https://repo.hex.pm/tarballs/gpio-0.6.1.tar",
        "inserted_at": "2023-01-13T09:39:48.267532Z",
    },
}


def uncompress_hex_package(datadir, tmp_path, package_filename):
    tarball_path = os.path.join(datadir, "https_repo.hex.pm", package_filename)
    uncompress_path = os.path.join(
        tmp_path, hashlib.sha1(package_filename.encode()).hexdigest()
    )
    uncompress(tarball_path, uncompress_path)
    contents_uncompressed_path = os.path.join(uncompress_path, "contents")
    contents_tarball_path = os.path.join(uncompress_path, "contents.tar.gz")
    uncompress(contents_tarball_path, contents_uncompressed_path)
    return from_disk.Directory.from_disk(
        path=contents_uncompressed_path.encode("utf-8")
    )


@pytest.fixture
def release_6_0_dir(datadir, tmp_path):
    return uncompress_hex_package(datadir, tmp_path, "tarballs_gpio-0.6.0.tar")


@pytest.fixture
def release_6_0(release_6_0_dir):
    return Release(
        name=b"0.6.0",
        author=Person.from_fullname(b"asabil <ali.sabil@gmail.com>"),
        date=TimestampWithTimezone.from_iso8601("2023-01-12T10:39:50.179787Z"),
        message=(b"Synthetic release for Hex source package gpio version 0.6.0\n"),
        target=release_6_0_dir.hash,
        target_type=ReleaseTargetType.DIRECTORY,
        synthetic=True,
    )


@pytest.fixture
def release_6_1_dir(datadir, tmp_path):
    return uncompress_hex_package(datadir, tmp_path, "tarballs_gpio-0.6.1.tar")


@pytest.fixture
def release_6_1(release_6_1_dir):
    return Release(
        name=b"0.6.1",
        author=Person.from_fullname(b"asabil <ali.sabil@gmail.com>"),
        date=TimestampWithTimezone.from_iso8601("2023-01-13T09:39:49.280041Z"),
        message=(b"Synthetic release for Hex source package gpio version 0.6.1\n"),
        target=release_6_1_dir.hash,
        target_type=ReleaseTargetType.DIRECTORY,
        synthetic=True,
    )


@pytest.fixture
def release_6_2_dir(datadir, tmp_path):
    return uncompress_hex_package(datadir, tmp_path, "tarballs_gpio-0.6.2.tar")


@pytest.fixture
def release_6_2(release_6_2_dir):
    cnts, skipped_cnts, dirs = from_disk.iter_directory(release_6_2_dir)
    return Release(
        name=b"0.6.2",
        author=Person.from_fullname(b"asabil <ali.sabil@gmail.com>"),
        date=TimestampWithTimezone.from_iso8601("2023-02-05T09:55:20.253248Z"),
        message=(b"Synthetic release for Hex source package gpio version 0.6.2\n"),
        target=release_6_2_dir.hash,
        target_type=ReleaseTargetType.DIRECTORY,
        synthetic=True,
    )


@pytest.fixture
def first_visit_snapshot(release_6_0, release_6_1):
    return Snapshot(
        branches={
            b"HEAD": SnapshotBranch(
                target=b"releases/0.6.1",
                target_type=SnapshotTargetType.ALIAS,
            ),
            b"releases/0.6.0": SnapshotBranch(
                target=release_6_0.id,
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"releases/0.6.1": SnapshotBranch(
                target=release_6_1.id,
                target_type=SnapshotTargetType.RELEASE,
            ),
        },
    )


@pytest.fixture()
def expected_stats_first_visit(release_6_0_dir, release_6_1_dir) -> dict:
    release_6_0_cnts, _, release_6_0_dirs = from_disk.iter_directory(release_6_0_dir)
    release_6_1_cnts, _, release_6_1_dirs = from_disk.iter_directory(release_6_1_dir)
    return {
        "content": len(set(release_6_0_cnts) | set(release_6_1_cnts)),
        "directory": len(set(release_6_0_dirs) | set(release_6_1_dirs)),
        "origin": 1,
        "origin_visit": 1,
        "release": 2,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    }


@pytest.fixture()
def expected_stats_second_visit(
    release_6_0_dir, release_6_1_dir, release_6_2_dir
) -> dict:
    release_6_0_cnts, _, release_6_0_dirs = from_disk.iter_directory(release_6_0_dir)
    release_6_1_cnts, _, release_6_1_dirs = from_disk.iter_directory(release_6_1_dir)
    release_6_2_cnts, _, release_6_2_dirs = from_disk.iter_directory(release_6_2_dir)
    return {
        "content": len(
            set(release_6_0_cnts) | set(release_6_1_cnts) | set(release_6_2_cnts)
        ),
        "directory": len(
            set(release_6_0_dirs) | set(release_6_1_dirs) | set(release_6_2_dirs)
        ),
        "origin": 1,
        "origin_visit": 3,
        "release": 3,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 2,
    }


@pytest.fixture()
def expected_request_history() -> List[str]:
    return [
        "https://hex.pm/api/packages/gpio/releases/0.6.0",
        "https://hex.pm/api/packages/gpio/releases/0.6.1",
        "https://repo.hex.pm/tarballs/gpio-0.6.0.tar",
        "https://repo.hex.pm/tarballs/gpio-0.6.1.tar",
    ]


def assert_stored(swh_storage, release: List[Release], snapshot: Snapshot, stats: dict):
    assert_last_visit_matches(
        swh_storage,
        ORIGIN,
        status="full",
        type="hex",
        snapshot=hash_to_bytes(snapshot.id),
    )
    check_snapshot(snapshot, swh_storage)
    for r in release:
        assert swh_storage.release_get([r.id])[0] == r

    assert get_stats(swh_storage) == stats


def assert_metadata_stored(loader, release: Release, metadata: bytes):
    assert release.target is not None

    release_swhid = CoreSWHID(object_type=ObjectType.RELEASE, object_id=release.id)
    directory_swhid = ExtendedSWHID(
        object_type=ExtendedObjectType.DIRECTORY, object_id=release.target
    )
    expected_metadata = RawExtrinsicMetadata(
        target=directory_swhid,
        authority=loader.get_metadata_authority(),
        fetcher=MetadataFetcher(
            name="swh.loader.package.hex.loader.HexLoader",
            version=__version__,
        ),
        discovery_date=loader.visit_date,
        format="hexpm-release-json",
        metadata=metadata,
        origin=ORIGIN,
        release=release_swhid,
    )

    assert loader.storage.raw_extrinsic_metadata_get(
        directory_swhid, loader.get_metadata_authority()
    ).results == [expected_metadata]


def test_hex_first_visit(
    swh_storage,
    datadir,
    requests_mock_datadir,
    expected_stats_first_visit: dict,
    expected_request_history: List[str],
    first_visit_snapshot,
    release_6_0,
    release_6_1,
):
    loader = HexLoader(swh_storage, ORIGIN, releases=RELEASES)

    status = loader.load()

    assert status == {
        "status": "eventful",
        "snapshot_id": hash_to_hex(first_visit_snapshot.id),
    }
    assert [
        m.url for m in requests_mock_datadir.request_history
    ] == expected_request_history

    # Check extrinsic metadata
    metadata_6_0 = Path(
        datadir, "https_hex.pm", "api_packages_gpio_releases_0.6.0"
    ).read_bytes()
    metadata_6_1 = Path(
        datadir, "https_hex.pm", "api_packages_gpio_releases_0.6.1"
    ).read_bytes()

    assert_stored(
        swh_storage,
        [release_6_0, release_6_1],
        first_visit_snapshot,
        expected_stats_first_visit,
    )

    assert_metadata_stored(loader, release_6_0, metadata_6_0)
    assert_metadata_stored(loader, release_6_1, metadata_6_1)


def test_rpm_multiple_visits(
    swh_storage,
    datadir,
    requests_mock_datadir,
    expected_stats_first_visit: dict,
    expected_stats_second_visit: dict,
    expected_request_history: List[str],
    first_visit_snapshot,
    release_6_0,
    release_6_1,
    release_6_2,
):
    loader = HexLoader(swh_storage, ORIGIN, releases=RELEASES)

    # First run: Discovered exactly 2 releases
    status = loader.load()
    assert status == {
        "status": "eventful",
        "snapshot_id": hash_to_hex(first_visit_snapshot.id),
    }

    # Second run: No updates
    status = loader.load()
    expected_request_history.extend(
        [
            "https://hex.pm/api/packages/gpio/releases/0.6.0",
            "https://hex.pm/api/packages/gpio/releases/0.6.1",
        ]
    )
    # a new visit occurs but no new releases/snapshots are created
    expected_stats_first_visit["origin_visit"] += 1

    assert status == {
        "status": "uneventful",
        "snapshot_id": hash_to_hex(first_visit_snapshot.id),
    }
    assert [
        m.url for m in requests_mock_datadir.request_history
    ] == expected_request_history
    assert_stored(
        swh_storage,
        [release_6_0, release_6_1],
        first_visit_snapshot,
        expected_stats_first_visit,
    )

    # Third run: New release
    # Updated snapshot but tar file is the same as 0.6.1 so no new content/directory
    new_releases = {
        **RELEASES,
        "0.6.2": {
            "name": "gpio",
            "release_url": "https://hex.pm/api/packages/gpio/releases/0.6.2",
            "tarball_url": "https://repo.hex.pm/tarballs/gpio-0.6.2.tar",
            "inserted_at": "2023-02-05T09:55:17.707695Z",
        },
    }
    loader = HexLoader(swh_storage, ORIGIN, releases=new_releases)

    status = loader.load()

    expected_request_history.extend(
        [
            "https://hex.pm/api/packages/gpio/releases/0.6.0",
            "https://hex.pm/api/packages/gpio/releases/0.6.1",
            "https://hex.pm/api/packages/gpio/releases/0.6.2",
            "https://repo.hex.pm/tarballs/gpio-0.6.2.tar",
        ]
    )

    new_snapshot = Snapshot(
        branches={
            **first_visit_snapshot.branches,
            b"HEAD": SnapshotBranch(
                target=b"releases/0.6.2",
                target_type=SnapshotTargetType.ALIAS,
            ),
            b"releases/0.6.2": SnapshotBranch(
                target=release_6_2.id,
                target_type=SnapshotTargetType.RELEASE,
            ),
        },
    )

    assert status == {"status": "eventful", "snapshot_id": hash_to_hex(new_snapshot.id)}
    assert [
        m.url for m in requests_mock_datadir.request_history
    ] == expected_request_history
    assert_stored(
        swh_storage,
        [release_6_0, release_6_1, release_6_2],
        new_snapshot,
        expected_stats_second_visit,
    )

    # Check extrinsic metadata
    metadata_6_2 = Path(
        datadir, "https_hex.pm", "api_packages_gpio_releases_0.6.2"
    ).read_bytes()
    assert_metadata_stored(loader, release_6_2, metadata_6_2)
