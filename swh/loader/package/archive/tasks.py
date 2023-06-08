# Copyright (C) 2019-2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.package.archive.loader import TarballLoader


@shared_task(name=__name__ + ".LoadTarball")
def load_tarball(**kwargs):
    """Load archive's artifacts (e.g gnu, etc...)"""
    loader = TarballLoader.from_configfile(**kwargs)
    return loader.load()
