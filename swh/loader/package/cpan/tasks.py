# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.package.cpan.loader import CpanLoader


@shared_task(name=__name__ + ".LoadCpan")
def load_cpan(**kwargs):
    """Load packages from Cpan (The Comprehensive Perl Archive Network)"""
    return CpanLoader.from_configfile(**kwargs).load()
