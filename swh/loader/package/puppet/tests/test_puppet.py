# Copyright (C) 2022-2025  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import copy
import json
import os

import iso8601
import pytest

from swh.loader.core import __version__
from swh.loader.core.utils import EMPTY_AUTHOR
from swh.loader.package.puppet.loader import PuppetLoader, PuppetPackageInfo
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.hashutil import hash_to_bytes
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
    "url": "https://forge.puppet.com/modules/saz/memcached",
    "artifacts": [
        {
            "url": "https://forgeapi.puppet.com/v3/files/saz-memcached-1.0.0.tar.gz",  # noqa: B950
            "version": "1.0.0",
            "filename": "saz-memcached-1.0.0.tar.gz",
            "last_update": "2011-11-20T13:40:30-08:00",
            "checksums": {
                "length": 763,
            },
        },
        {
            "url": "https://forgeapi.puppet.com/v3/files/saz-memcached-8.1.0.tar.gz",  # noqa: B950
            "version": "8.1.0",
            "filename": "saz-memcached-8.1.0.tar.gz",
            "last_update": "2022-07-11T03:34:55-07:00",
            "checksums": {
                "md5": "dc0d6b7336ddcd21987f74af83a64f43",
                "sha256": "094fd1bba5110a88875af0d3a687374baca6ac809607c9705a3bf50b76637832",  # noqa: B950
            },
        },
    ],
}


@pytest.fixture
def puppet_module_extrinsic_metadata(datadir):
    with open(
        os.path.join(
            datadir,
            "https_forgeapi.puppet.com",
            "v3_releases,module=saz-memcached",
        )
    ) as metadata:
        return json.load(metadata)["results"]


def test_get_sorted_versions(requests_mock_datadir, swh_storage):
    loader = PuppetLoader(swh_storage, url=ORIGIN["url"], artifacts=ORIGIN["artifacts"])
    assert loader.get_sorted_versions() == ["1.0.0", "8.1.0"]


def test_get_default_version(requests_mock_datadir, swh_storage):
    loader = PuppetLoader(swh_storage, url=ORIGIN["url"], artifacts=ORIGIN["artifacts"])
    assert loader.get_default_version() == "8.1.0"


def test_puppet_loader_load_multiple_version(
    datadir, requests_mock_datadir, swh_storage, puppet_module_extrinsic_metadata
):
    loader = PuppetLoader(swh_storage, url=ORIGIN["url"], artifacts=ORIGIN["artifacts"])
    load_status = loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    expected_snapshot_id = "bcfa7d70f0ceb83e45acaf20a57216b2df3ce311"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"HEAD": SnapshotBranch(
                target=b"releases/8.1.0",
                target_type=SnapshotTargetType.ALIAS,
            ),
            b"releases/1.0.0": SnapshotBranch(
                target=hash_to_bytes("83b3463dd35d44dbae4bfe917a9b127924a14bbd"),
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"releases/8.1.0": SnapshotBranch(
                target=hash_to_bytes("7a89a5b7060900ae8cdd340441cf0432f1b96d25"),
                target_type=SnapshotTargetType.RELEASE,
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

    expected_release = Release(
        name=b"8.1.0",
        message=b"Synthetic release for Puppet source package saz-memcached version 8.1.0\n",
        target=hash_to_bytes("ff46ca938c6d42eac34753393d4596ccebc637a1"),
        target_type=ReleaseTargetType.DIRECTORY,
        synthetic=True,
        author=Person(fullname=b"saz", name=b"saz", email=None),
        date=TimestampWithTimezone.from_iso8601("2022-07-11T03:34:55-07:00"),
    )

    assert swh_storage.release_get([expected_release.id])[0] == expected_release

    assert_last_visit_matches(
        swh_storage,
        url=ORIGIN["url"],
        status="full",
        type="puppet",
        snapshot=expected_snapshot.id,
    )

    directory_swhid = ExtendedSWHID(
        object_type=ExtendedObjectType.DIRECTORY,
        object_id=expected_release.target,
    )
    release_swhid = CoreSWHID(
        object_type=ObjectType.RELEASE, object_id=expected_release.id
    )

    expected_metadata = [
        RawExtrinsicMetadata(
            target=directory_swhid,
            authority=loader.get_metadata_authority(),
            fetcher=MetadataFetcher(
                name="swh.loader.package.puppet.loader.PuppetLoader",
                version=__version__,
            ),
            discovery_date=loader.visit_date,
            format="puppet-module-json",
            metadata=json.dumps(puppet_module_extrinsic_metadata[0]).encode(),
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

    package_extids = [
        package_info.extid()
        for version in loader.get_versions()
        for _, package_info in loader.get_package_info(version)
    ]

    extids = loader.storage.extid_get_from_extid(
        id_type=PuppetPackageInfo.EXTID_TYPE,
        ids=[extid for (_, _, extid) in package_extids],
        version=PuppetPackageInfo.EXTID_VERSION,
    )
    assert len(extids) == 2

    assert release_swhid in {extid.target for extid in extids}


def test_puppet_loader_load_missing_extrinsic_metadata(
    requests_mock_datadir,
    swh_storage,
    puppet_module_extrinsic_metadata,
    mocker,
):
    loader = PuppetLoader(swh_storage, url=ORIGIN["url"], artifacts=ORIGIN["artifacts"])
    # one release is missing extrinsic metadata
    mocker.patch.object(loader, "extrinsic_metadata").return_value = {
        "1.0.0": puppet_module_extrinsic_metadata[1]
    }
    loader.load()

    # both releases should have been loaded regardless if extrinsic metadata
    # are available or not
    assert get_stats(swh_storage)["release"] == len(ORIGIN["artifacts"])


@pytest.fixture
def puppet_module_intrinsic_metadata():
    return copy.copy(
        {
            "summary": "UNKNOWN",
            "author": "saz",
            "source": "UNKNOWN",
            "dependencies": [],
            "types": [],
            "license": "Apache License, Version 2.0",
            "project_page": "https://github.com/saz/puppet-memcached",
            "version": "1.0.0",
            "name": "saz-memcached",
            "description": "Manage memcached via Puppet",
        }
    )


@pytest.fixture
def puppet_package_info(puppet_module_extrinsic_metadata):
    return PuppetPackageInfo.from_metadata(
        url="https://forgeapi.puppet.com/v3/files/saz-memcached-1.0.0.tar.gz",
        module_name="saz-memcached",
        filename="saz-memcached-1.0.0.tar.gz",
        version="1.0.0",
        last_modified=iso8601.parse_date("2011-11-20T13:40:30-08:00"),
        extrinsic_metadata={"1.0.0": puppet_module_extrinsic_metadata[1]},
    )


def test_puppet_package_build_release_missing_author(
    swh_storage,
    puppet_package_info,
    puppet_module_intrinsic_metadata,
    mocker,
):
    puppet_module_intrinsic_metadata["author"] = None

    loader = PuppetLoader(swh_storage, url=ORIGIN["url"], artifacts=ORIGIN["artifacts"])

    mocker.patch(
        "swh.loader.package.puppet.loader.extract_intrinsic_metadata"
    ).return_value = puppet_module_intrinsic_metadata

    release = loader.build_release(
        puppet_package_info,
        uncompressed_path="",
        directory=hash_to_bytes("1b9a2dbc80f954e1ba4b2f1c6344d1ce4e84ab7c"),
    )

    assert release.author == EMPTY_AUTHOR


def test_puppet_package_build_release_multi_authors(
    swh_storage,
    puppet_package_info,
    puppet_module_intrinsic_metadata,
    mocker,
):
    puppet_module_intrinsic_metadata["author"] = [
        "John Doe <john.doe@example.org>",
        "Jane Doe <jane.doe@example.org>",
    ]

    loader = PuppetLoader(swh_storage, url=ORIGIN["url"], artifacts=ORIGIN["artifacts"])

    mocker.patch(
        "swh.loader.package.puppet.loader.extract_intrinsic_metadata"
    ).return_value = puppet_module_intrinsic_metadata

    release = loader.build_release(
        puppet_package_info,
        uncompressed_path="",
        directory=hash_to_bytes("1b9a2dbc80f954e1ba4b2f1c6344d1ce4e84ab7c"),
    )

    assert release.author == Person.from_fullname(b"John Doe <john.doe@example.org>")
    assert b"Co-authored-by: Jane Doe <jane.doe@example.org>\n" in release.message
