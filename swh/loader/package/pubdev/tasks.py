# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.package.pubdev.loader import PubDevLoader


@shared_task(name=__name__ + ".LoadPubDev")
def load_pubdev(**kwargs):
    """Load packages from pub.dev (Dart, Flutter)"""
    return PubDevLoader.from_configfile(**kwargs).load()
