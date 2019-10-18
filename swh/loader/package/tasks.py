# Copyright (C) 2019  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from celery import shared_task

from swh.loader.package.debian import DebianLoader
from swh.loader.package.deposit import DepositLoader
from swh.loader.package.gnu import GNULoader
from swh.loader.package.npm import NpmLoader
from swh.loader.package.pypi import PyPILoader


@shared_task(name=__name__ + '.LoadDebian')
def load_debian(*, url, date, packages):
    return DebianLoader(url, date, packages).load()


@shared_task(name=__name__ + '.LoadDeposit')
def load_deposit(*, url, deposit_id):
    return DepositLoader(url, deposit_id).load()


@shared_task(name=__name__ + '.LoadGNU')
def load_gnu(*, url, tarballs):
    return GNULoader(url, tarballs).load()


@shared_task(name=__name__ + '.LoadNpm')
def load_npm(*, package_name, package_url, package_metadata_url):
    return NpmLoader(package_name, package_url, package_metadata_url).load()


@shared_task(name=__name__ + '.LoadPyPI')
def load_pypi(*, url=None):
    return PyPILoader(url).load()
