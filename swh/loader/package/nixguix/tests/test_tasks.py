# Copyright (C) 2020-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.nixguix"


@pytest.fixture
def nixguix_lister():
    return Lister(name="nixguix", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def nixguix_listed_origin(nixguix_lister):
    return ListedOrigin(
        lister_id=nixguix_lister.id,
        url="https://nixguix.example.org/",
        visit_type="nixguix",
    )


def test_nixguix_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    nixguix_lister,
    nixguix_listed_origin,
):

    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.NixGuixLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadNixguix",
        lister=nixguix_lister,
        listed_origin=nixguix_listed_origin,
    )
