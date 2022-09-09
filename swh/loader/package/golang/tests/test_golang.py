# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from swh.loader.package.golang.loader import GolangLoader


def test_golang_loader_first_visit(swh_storage, requests_mock_datadir):
    url = "https://pkg.go.dev/example.com/basic-go-module"
    loader = GolangLoader(swh_storage, url)

    assert loader.load()["status"] == "eventful"
