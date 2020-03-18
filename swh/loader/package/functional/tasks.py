# Copyright (C) 2020  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.package.functional.loader import (
    FunctionalLoader
)


@shared_task(name=__name__ + '.LoadFunctional')
def load_functional(*, url=None):
    """Load functional (e.g. guix/nix) package"""
    return FunctionalLoader(url).load()
