# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from swh.loader.package.rubygems.loader import RubyGemsLoader
from swh.loader.tests import get_stats


def test_rubygems_loader(swh_storage, requests_mock_datadir):
    url = "https://rubygems.org/gems/mercurial-wrapper"
    loader = RubyGemsLoader(swh_storage, url)

    assert loader.load()["status"] == "eventful"

    stats = get_stats(swh_storage)
    assert {
        "content": 8,
        "directory": 4,
        "origin": 1,
        "origin_visit": 1,
        "release": 2,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats
