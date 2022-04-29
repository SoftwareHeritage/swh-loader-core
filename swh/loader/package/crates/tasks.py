# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.package.crates.loader import CratesLoader


@shared_task(name=__name__ + ".LoadCrates")
def load_crates(*, url=None, package_name: str, version: str, checksum=None):
    """Load Rust crate package"""
    return CratesLoader.from_configfile(
        url=url, package_name=package_name, version=version, checksum=checksum
    ).load()
