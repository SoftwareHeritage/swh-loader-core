# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.puppet"


@pytest.fixture
def puppet_lister():
    return Lister(name="puppet", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def puppet_listed_origin(puppet_lister):
    return ListedOrigin(
        lister_id=puppet_lister.id,
        url="some-url/api/packages/some-package",
        visit_type="aur",
        extra_loader_arguments={
            "artifacts": [
                {
                    "url": "https://domain/some-package-1.0.0.tar.gz",
                    "version": "1.0.0",
                    "filename": "some-module-1.0.0.tar.gz",
                    "last_update": "2011-11-20T13:40:30-08:00",
                },
            ]
        },
    )


def test_puppet_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    puppet_lister,
    puppet_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.PuppetLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadPuppet",
        lister=puppet_lister,
        listed_origin=puppet_listed_origin,
    )
