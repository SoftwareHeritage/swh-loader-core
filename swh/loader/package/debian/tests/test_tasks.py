# Copyright (C) 2019-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.debian"


@pytest.fixture
def debian_lister():
    return Lister(name="debian", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def debian_listed_origin(debian_lister):
    return ListedOrigin(
        lister_id=debian_lister.id,
        url="https://debian.example.org/package",
        visit_type="debian",
        extra_loader_arguments={"packages": {}},
    )


def test_debian_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    debian_lister,
    debian_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.DebianLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadDebian",
        lister=debian_lister,
        listed_origin=debian_listed_origin,
    )
