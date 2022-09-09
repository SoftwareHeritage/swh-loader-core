# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information
from swh.loader.package.aur.loader import AurLoader
from swh.loader.package.utils import EMPTY_AUTHOR
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.hashutil import hash_to_bytes
from swh.model.model import (
    ObjectType,
    Release,
    Snapshot,
    SnapshotBranch,
    TargetType,
    TimestampWithTimezone,
)

EXPECTED_PACKAGES = [
    {
        "url": "https://aur.archlinux.org/hg-evolve.git",
        "artifacts": [
            {
                "filename": "hg-evolve.tar.gz",
                "url": "https://aur.archlinux.org/cgit/aur.git/snapshot/hg-evolve.tar.gz",  # noqa: B950
                "version": "10.5.2-1",
            }
        ],
        "aur_metadata": [
            {
                "version": "10.5.2-1",
                "project_url": "https://www.mercurial-scm.org/doc/evolution/",
                "last_update": "2022-07-16T00:08:41+00:00",
                "pkgname": "hg-evolve",
            }
        ],
    },
    {
        "url": "https://aur.archlinux.org/ibus-git.git",
        "artifacts": [
            {
                "filename": "ibus-git.tar.gz",
                "url": "https://aur.archlinux.org/cgit/aur.git/snapshot/ibus-git.tar.gz",  # noqa: B950
                "version": "1.5.23+12+gef4c5c7e-1",
            }
        ],
        "aur_metadata": [
            {
                "version": "1.5.23+12+gef4c5c7e-1",
                "project_url": "https://github.com/ibus/ibus/wiki",
                "last_update": "2021-02-08T06:12:11+00:00",
                "pkgname": "ibus-git",
            }
        ],
    },
    {
        "url": "https://aur.archlinux.org/libervia-web-hg.git",
        "artifacts": [
            {
                "filename": "libervia-web-hg.tar.gz",
                "url": "https://aur.archlinux.org/cgit/aur.git/snapshot/libervia-web-hg.tar.gz",  # noqa: B950
                "version": "0.9.0.r1492.3a34d78f2717-1",
            }
        ],
        "aur_metadata": [
            {
                "version": "0.9.0.r1492.3a34d78f2717-1",
                "project_url": "http://salut-a-toi.org/",
                "last_update": "2022-02-26T15:30:58+00:00",
                "pkgname": "libervia-web-hg",
            }
        ],
    },
    {
        "url": "https://aur.archlinux.org/tealdeer-git.git",
        "artifacts": [
            {
                "filename": "tealdeer-git.tar.gz",
                "url": "https://aur.archlinux.org/cgit/aur.git/snapshot/tealdeer-git.tar.gz",  # noqa: B950
                "version": "r255.30b7c5f-1",
            }
        ],
        "aur_metadata": [
            {
                "version": "r255.30b7c5f-1",
                "project_url": "https://github.com/dbrgn/tealdeer",
                "last_update": "2020-09-04T20:36:52+00:00",
                "pkgname": "tealdeer-git",
            }
        ],
    },
    {
        "url": "https://aur.archlinux.org/a-fake-one.git",
        "artifacts": [
            {
                "filename": "a-fake-one.tar.gz",
                "url": "https://aur.archlinux.org/cgit/aur.git/snapshot/a-fake-one.tar.gz",  # noqa: B950
                "version": "0.0.1",
            },
        ],
        "aur_metadata": [
            {
                "version": "0.0.1",
                "project_url": "https://nowhere/a-fake-one",
                "last_update": "2022-02-02T22:22:22+00:00",
                "pkgname": "a-fake-one",
            }
        ],
    },
]


def test_get_versions(swh_storage):
    loader = AurLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[0]["url"],
        artifacts=EXPECTED_PACKAGES[0]["artifacts"],
        aur_metadata=EXPECTED_PACKAGES[0]["aur_metadata"],
    )

    assert loader.get_versions() == [
        "10.5.2-1",
    ]


def test_get_default_version(requests_mock_datadir, swh_storage):
    loader = AurLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[0]["url"],
        artifacts=EXPECTED_PACKAGES[0]["artifacts"],
        aur_metadata=EXPECTED_PACKAGES[0]["aur_metadata"],
    )
    assert loader.get_default_version() == "10.5.2-1"


def test_aur_loader_load_one_version(datadir, requests_mock_datadir, swh_storage):
    loader = AurLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[0]["url"],
        artifacts=EXPECTED_PACKAGES[0]["artifacts"],
        aur_metadata=EXPECTED_PACKAGES[0]["aur_metadata"],
    )
    actual_load_status = loader.load()
    assert actual_load_status["status"] == "eventful"
    assert actual_load_status["snapshot_id"] is not None

    expected_snapshot_id = "fb9ff853036ea48c94f5e5366a9e49d7610d98ed"
    expected_release_id = "35ddfe3106bb47f259a9316898de5cab5bf15864"

    assert expected_snapshot_id == actual_load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(actual_load_status["snapshot_id"]),
        branches={
            b"releases/10.5.2-1/hg-evolve.tar.gz": SnapshotBranch(
                target=hash_to_bytes(expected_release_id),
                target_type=TargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/10.5.2-1/hg-evolve.tar.gz",
                target_type=TargetType.ALIAS,
            ),
        },
    )

    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 1,
        "directory": 2,
        "origin": 1,
        "origin_visit": 1,
        "release": 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    assert swh_storage.release_get([hash_to_bytes(expected_release_id)])[0] == Release(
        name=b"10.5.2-1",
        message=b"Synthetic release for Aur source package hg-evolve version "
        b"10.5.2-1\n\nFlexible evolution of Mercurial history\n",
        target=hash_to_bytes("cc4079be57e7cc0dbf2ecc76c81f5d84782ba632"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
        author=EMPTY_AUTHOR,
        date=TimestampWithTimezone.from_iso8601("2022-07-16T00:08:41+00:00"),
        id=hash_to_bytes(expected_release_id),
    )

    assert_last_visit_matches(
        swh_storage,
        url=EXPECTED_PACKAGES[0]["url"],
        status="full",
        type="aur",
        snapshot=expected_snapshot.id,
    )


def test_aur_loader_load_expected_packages(datadir, requests_mock_datadir, swh_storage):
    # Exclude the last 'fake' package from EXPECTED_PACKAGES
    for package in EXPECTED_PACKAGES[:-1]:
        loader = AurLoader(
            swh_storage,
            url=package["url"],
            artifacts=package["artifacts"],
            aur_metadata=package["aur_metadata"],
        )
        actual_load_status = loader.load()
        assert actual_load_status["status"] == "eventful"
        assert actual_load_status["snapshot_id"] is not None

    stats = get_stats(swh_storage)
    assert {
        "content": 1 + 1 + 1 + 1,
        "directory": 2 + 2 + 2 + 2,
        "origin": 1 + 1 + 1 + 1,
        "origin_visit": 1 + 1 + 1 + 1,
        "release": 1 + 1 + 1 + 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1 + 1 + 1 + 1,
    } == stats


def test_aur_invalid_origin_not_found(swh_storage, requests_mock_datadir):
    url = "http://nowhere/packages/42.git"
    loader = AurLoader(
        swh_storage,
        url,
        artifacts=[
            {
                "version": "0.0.1",
                "url": "https://myforge.nowhere/42/42.tar.gz",
                "filename": "42.tar.gz",
            },
        ],
        aur_metadata=[
            {
                "pkgname": "42",
                "version": "0.0.1",
                "project_url": "https://myforge.nowhere/42",
                "last_update": "2022-04-07T21:08:14",
            },
        ],
    )

    load_status = loader.load()
    assert load_status["status"] == "uneventful"


def test_aur_parse_srcinfo(swh_storage, requests_mock_datadir):
    """Ensure that multiple lines of `pkgdesc` in .SRCINFO results in `description`
    string"""

    loader = AurLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[-1]["url"],
        artifacts=EXPECTED_PACKAGES[-1]["artifacts"],
        aur_metadata=EXPECTED_PACKAGES[-1]["aur_metadata"],
    )
    loader.load()

    expected_release_id = "2af50761854fee5589b75ff0ecd6886d1185377e"

    assert swh_storage.release_get([hash_to_bytes(expected_release_id)])[0] == Release(
        name=b"0.0.1",
        message=b"Synthetic release for Aur source package a-fake-one version 0.0.1\n\n"
        b"A first line of description.\nA second line for more information.\n",
        target=hash_to_bytes("82c770b7d8b1aa573e57b13864831e141d40fe26"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
        author=EMPTY_AUTHOR,
        date=TimestampWithTimezone.from_iso8601("2022-02-02T22:22:22+00:00"),
        id=hash_to_bytes(expected_release_id),
    )
