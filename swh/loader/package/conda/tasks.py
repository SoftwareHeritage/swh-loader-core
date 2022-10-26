# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.package.conda.loader import CondaLoader


@shared_task(name=__name__ + ".LoadConda")
def load_conda(**kwargs):
    """Load packages from Conda"""
    return CondaLoader.from_configfile(**kwargs).load()
