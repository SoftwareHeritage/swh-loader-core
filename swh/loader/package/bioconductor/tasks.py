# Copyright (C) 2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.package.bioconductor.loader import BioconductorLoader


@shared_task(name=__name__ + ".LoadBioconductor")
def load_bioconductor(**kwargs):
    """Load bioconductor package"""
    loader = BioconductorLoader.from_configfile(**kwargs)
    return loader.load()
