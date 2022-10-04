# Copyright (C) 2018-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from os import path
import shutil
from typing import Dict, List, Union

import pytest

from swh.model.hashutil import MultiHash

nix_store_missing = shutil.which("nix-store") is None


@pytest.fixture
def tarball_path(datadir):
    """Return tarball filepath fetched by DirectoryLoader test runs."""
    return path.join(datadir, "https_example.org", "archives_dummy-hello.tar.gz")


def compute_hashes(
    filepath: str, cksum_algos: Union[str, List[str]] = "sha256"
) -> Dict[str, str]:
    """Compute checksums dict out of a filepath"""
    checksum_algos = {cksum_algos} if isinstance(cksum_algos, str) else set(cksum_algos)
    return MultiHash.from_path(filepath, hash_names=checksum_algos).hexdigest()


@pytest.fixture
def tarball_with_std_hashes(tarball_path):
    return (
        tarball_path,
        compute_hashes(tarball_path, ["sha1", "sha256", "sha512"]),
    )


@pytest.fixture
def tarball_with_nar_hashes(tarball_path):
    # FIXME: compute it instead of hard-coding it
    return (
        tarball_path,
        {"sha256": "23fb1fe278aeb2de899f7d7f10cf892f63136cea2c07146da2200da4de54b7e4"},
    )
