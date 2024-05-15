# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from swh.loader.package.conda.loader import CondaLoader
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.hashutil import hash_to_bytes, hash_to_hex
from swh.model.model import (
    ObjectType,
    Person,
    Release,
    Snapshot,
    SnapshotBranch,
    SnapshotTargetType,
    TimestampWithTimezone,
)

ORIGINS = [
    {
        "url": "https://anaconda.org/conda-forge/lifetimes",
        "artifacts": [
            {
                "url": "https://conda.anaconda.org/conda-forge/linux-64/lifetimes-0.11.1-py36h9f0ad1d_1.tar.bz2",  # noqa: B950
                "date": "2020-07-06T12:19:36.425000+00:00",
                "version": "linux-64/0.11.1-py36h9f0ad1d_1",
                "filename": "lifetimes-0.11.1-py36h9f0ad1d_1.tar.bz2",
                "checksums": {
                    "md5": "5cbc765bd910a62315f340988f329768",
                    "sha256": "44f91fa4fd77aea15dcba382b3f20e13a6ae1d48eedb9ae6b3c3a0709bbdb76e",  # noqa: B950
                },
            },
            {
                "url": "https://conda.anaconda.org/conda-forge/linux-64/lifetimes-0.11.1-py36hc560c46_1.tar.bz2",  # noqa: B950
                "date": "",  # Empty date
                "version": "linux-64/0.11.1-py36hc560c46_1",
                "filename": "lifetimes-0.11.1-py36hc560c46_1.tar.bz2",
                "checksums": {
                    "md5": "14d2908d3b625ffd3f8d1fc0f20eaa07",
                    "sha256": "46f5c5ab12338ec7b546d930a75c39633762fb2dac5f486fefebabbc4705c6c1",  # noqa: B950
                },
            },
        ],
    },
]


def test_get_versions(requests_mock_datadir, swh_storage):
    loader = CondaLoader(
        swh_storage, url=ORIGINS[0]["url"], artifacts=ORIGINS[0]["artifacts"]
    )
    assert loader.get_versions() == [
        "linux-64/0.11.1-py36h9f0ad1d_1",
        "linux-64/0.11.1-py36hc560c46_1",
    ]


def test_get_default_version(requests_mock_datadir, swh_storage):
    loader = CondaLoader(
        swh_storage, url=ORIGINS[0]["url"], artifacts=ORIGINS[0]["artifacts"]
    )
    assert loader.get_default_version() == "linux-64/0.11.1-py36hc560c46_1"


def test_conda_loader_load_multiple_version(
    datadir, requests_mock_datadir, swh_storage
):
    loader = CondaLoader(
        swh_storage, url=ORIGINS[0]["url"], artifacts=ORIGINS[0]["artifacts"]
    )
    load_status = loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    first_release = Release(
        name=b"0.11.1-py36h9f0ad1d_1-linux-64",
        message=b"Synthetic release for Conda source package lifetimes version"
        b" linux-64/0.11.1-py36h9f0ad1d_1\n",
        target=hash_to_bytes("0c63e5f909e481d8e5832bac8abbd089bca42993"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
        author=Person(
            fullname=b"CamDavidsonPilon", name=b"CamDavidsonPilon", email=None
        ),
        date=TimestampWithTimezone.from_iso8601("2020-07-06T12:19:36.425000+00:00"),
    )

    # This one have empty author and date
    second_release = Release(
        name=b"0.11.1-py36hc560c46_1-linux-64",
        message=b"Synthetic release for Conda source package lifetimes version"
        b" linux-64/0.11.1-py36hc560c46_1\n",
        target=hash_to_bytes("45ca406aeb31f51836a8593b619ab216403ce489"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
        author=Person(fullname=b"", name=None, email=None),
        date=None,
    )

    expected_snapshot = Snapshot(
        branches={
            b"releases/linux-64/0.11.1-py36h9f0ad1d_1": SnapshotBranch(
                target=first_release.id,
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"releases/linux-64/0.11.1-py36hc560c46_1": SnapshotBranch(
                target=second_release.id,
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/linux-64/0.11.1-py36hc560c46_1",
                target_type=SnapshotTargetType.ALIAS,
            ),
        },
    )

    assert hash_to_hex(expected_snapshot.id) == load_status["snapshot_id"]

    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 1 + 1,
        "directory": 2 + 3,
        "origin": 1,
        "origin_visit": 1,
        "release": 1 + 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    assert_last_visit_matches(
        swh_storage,
        url=ORIGINS[0]["url"],
        status="full",
        type="conda",
        snapshot=hash_to_bytes(load_status["snapshot_id"]),
    )
