# Copyright (C) 2021-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.package.maven.loader import MavenLoader


@shared_task(name=__name__ + ".LoadMaven")
def load_maven(**kwargs):
    """Load maven jar artifacts."""
    loader = MavenLoader.from_configfile(**kwargs)
    return loader.load()
