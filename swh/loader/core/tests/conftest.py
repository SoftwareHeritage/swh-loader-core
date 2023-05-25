# Copyright (C) 2018-2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from os import path
from typing import Dict, List

import pytest

from swh.loader.core.utils import compute_nar_hashes
from swh.model.hashutil import MultiHash


@pytest.fixture
def tarball_path(datadir):
    """Return tarball filepath fetched by TarballDirectoryLoader test runs."""
    return path.join(datadir, "https_example.org", "archives_dummy-hello.tar.gz")


@pytest.fixture
def content_path(datadir):
    """Return filepath fetched by ContentLoader test runs."""
    return path.join(
        datadir, "https_common-lisp.net", "project_asdf_archives_asdf-3.3.5.lisp"
    )


def compute_hashes(filepath: str, hash_names: List[str] = ["sha256"]) -> Dict[str, str]:
    """Compute checksums dict out of a filepath"""
    return MultiHash.from_path(filepath, hash_names=hash_names).hexdigest()


@pytest.fixture
def tarball_with_std_hashes(tarball_path):
    return (
        tarball_path,
        compute_hashes(tarball_path, ["sha1", "sha256", "sha512"]),
    )


@pytest.fixture
def tarball_with_nar_hashes(tarball_path):
    nar_hashes = compute_nar_hashes(tarball_path, ["sha256"])
    # Ensure it's the same hash as the initial one computed from the cli
    assert (
        nar_hashes["sha256"]
        == "23fb1fe278aeb2de899f7d7f10cf892f63136cea2c07146da2200da4de54b7e4"
    )
    return (tarball_path, nar_hashes)


@pytest.fixture
def content_with_nar_hashes(content_path):
    nar_hashes = compute_nar_hashes(content_path, ["sha256"], is_tarball=False)
    # Ensure it's the same hash as the initial one computed from the cli
    assert (
        nar_hashes["sha256"]
        == "0b555a4d13e530460425d1dc20332294f151067fb64a7e49c7de501f05b0a41a"
    )
    return (content_path, nar_hashes)
