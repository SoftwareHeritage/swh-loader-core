# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.hackage"


@pytest.fixture
def hackage_lister():
    return Lister(name="hackage", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def hackage_listed_origin(hackage_lister):
    return ListedOrigin(
        lister_id=hackage_lister.id,
        url="https://hackage.haskell.org/package/package_name",
        visit_type="hackage",
    )


def test_hackage_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    hackage_lister,
    hackage_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.HackageLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadHackage",
        lister=hackage_lister,
        listed_origin=hackage_listed_origin,
    )
