# Copyright (C) 2022-2025  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from swh.loader.package.golang.loader import GolangLoader
from swh.model.model import SnapshotTargetType, TimestampOverflowException


def test_golang_loader_first_visit(swh_storage, requests_mock_datadir):
    url = "https://pkg.go.dev/example.com/basic-go-module"
    loader = GolangLoader(swh_storage, url)

    assert loader.load()["status"] == "eventful"


def test_golang_loader_package_or_version_name_with_uppercase_characters(
    swh_storage, requests_mock_datadir
):
    url = "https://pkg.go.dev/github.com/adam-hanna/arrayOperations"
    loader = GolangLoader(swh_storage, url)

    assert loader.load()["status"] == "eventful"
    assert set(loader.last_snapshot().branches) == {
        b"releases/v1.0.1",
        b"releases/v1.0.1-RC1",
        b"HEAD",
    }


def test_golang_loader_package_with_dev_version_only(
    swh_storage, requests_mock_datadir
):
    url = "https://pkg.go.dev/github.com/xgdapg/daemon"
    loader = GolangLoader(swh_storage, url)

    assert loader.load()["status"] == "eventful"


def test_golang_latest_version_not_found(
    swh_storage, requests_mock_datadir, requests_mock
):
    url = "https://pkg.go.dev/github.com/adam-hanna/arrayOperations"
    requests_mock.get(
        "https://proxy.golang.org/github.com/adam-hanna/array!operations/@latest",
        status_code=404,
    )
    loader = GolangLoader(swh_storage, url)

    assert loader.load()["status"] == "eventful"
    assert set(loader.last_snapshot().branches) == {
        b"releases/v1.0.1",
        b"releases/v1.0.1-RC1",
        b"HEAD",
    }


def test_golang_release_date_timestamp_overflow(
    swh_storage, requests_mock_datadir, requests_mock, mocker
):

    mocker.patch(
        "swh.loader.package.golang.loader.TimestampWithTimezone.__init__"
    ).side_effect = TimestampOverflowException()
    url = "https://pkg.go.dev/github.com/adam-hanna/arrayOperations"

    loader = GolangLoader(swh_storage, url)

    assert loader.load()["status"] == "eventful"
    for branch in loader.last_snapshot().branches.values():
        if branch.target_type == SnapshotTargetType.RELEASE:
            release = swh_storage.release_get([branch.target])[0]
            assert release.date is None
