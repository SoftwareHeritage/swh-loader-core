# Copyright (C) 2022-2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from typing import Any, Mapping

import pkg_resources

try:
    __version__ = pkg_resources.get_distribution("swh.loader.core").version
except pkg_resources.DistributionNotFound:
    __version__ = "devel"


def register_content() -> Mapping[str, Any]:
    """Register the current worker module's definition"""
    from swh.loader.core.loader import ContentLoader

    return {
        "task_modules": [f"{__name__}.tasks"],
        "loader": ContentLoader,
    }


def register_directory() -> Mapping[str, Any]:
    """Register the current worker module's definition"""
    from swh.loader.core.loader import TarballDirectoryLoader

    return {
        "task_modules": [f"{__name__}.tasks"],
        "loader": TarballDirectoryLoader,
    }
