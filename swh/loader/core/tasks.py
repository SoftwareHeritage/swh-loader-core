# Copyright (C) 2022-2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.core.loader import ContentLoader, TarballDirectoryLoader


@shared_task(name=__name__ + ".LoadContent")
def load_content(**kwargs):
    """Load Content package"""
    return ContentLoader.from_configfile(**kwargs).load()


@shared_task(name=__name__ + ".LoadTarballDirectory")
def load_tarball_directory(**kwargs):
    """Load Directory packaged in a tarball."""
    return TarballDirectoryLoader.from_configfile(**kwargs).load()
