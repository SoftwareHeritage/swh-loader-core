# Copyright (C) 2019-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.npm"


@pytest.fixture
def npm_lister():
    return Lister(name="npm", instance_name="npm", id=uuid.uuid4())


@pytest.fixture
def npm_listed_origin(npm_lister):
    return ListedOrigin(
        lister_id=npm_lister.id,
        url="https://www.npmjs.com/package/some-package",
        visit_type="npm",
    )


def test_npm_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    npm_lister,
    npm_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.NpmLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadNpm",
        lister=npm_lister,
        listed_origin=npm_listed_origin,
    )
