# Copyright (C) 2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from typing import Any, Mapping


def register() -> Mapping[str, Any]:
    """Register the current worker module's definition"""
    from .loader import HexLoader

    return {
        "task_modules": [f"{__name__}.tasks"],
        "loader": HexLoader,
    }
