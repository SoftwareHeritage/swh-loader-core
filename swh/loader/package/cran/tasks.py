# Copyright (C) 2019  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.package.cran.loader import CRANLoader


@shared_task(name=__name__ + '.LoadCran')
def load_cran(url=None, version=None):
    """Load archive's artifacts (e.g gnu, etc...)"""
    return CRANLoader(url, version).load()