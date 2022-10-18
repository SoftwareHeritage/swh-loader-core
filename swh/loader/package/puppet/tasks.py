# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.package.puppet.loader import PuppetLoader


@shared_task(name=__name__ + ".LoadPuppet")
def load_puppet(**kwargs):
    """Load Puppet modules from puppet.com"""
    return PuppetLoader.from_configfile(**kwargs).load()
