# Copyright (C) 2021-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


class NotFound(ValueError):
    """An exception raised when some information to retrieve is not found (e.g origin,
    artifact, ...)

    """

    pass


class MissingOptionalDependency(ValueError):
    """An exception raised when an optional runtime dependency is missing."""

    pass


class UnsupportedChecksumComputation(ValueError):
    """An exception raised when loader cannot compute such checksums."""

    pass
