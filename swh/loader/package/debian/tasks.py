# Copyright (C) 2019-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.package.debian.loader import DebianLoader


@shared_task(name=__name__ + ".LoadDebian")
def load_deb(**kwargs):
    """Load Debian package"""
    loader = DebianLoader.from_configfile(**kwargs)
    return loader.load()
