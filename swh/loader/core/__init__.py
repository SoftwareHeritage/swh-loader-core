# Copyright (C) 2022-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from importlib.metadata import PackageNotFoundError, version
from typing import Any, Mapping

try:
    __version__ = version("swh.loader.core")
except PackageNotFoundError:
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
