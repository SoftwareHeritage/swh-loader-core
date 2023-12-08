# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.crates"


@pytest.fixture
def crates_lister():
    return Lister(name="crates", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def crates_listed_origin(crates_lister):
    return ListedOrigin(
        lister_id=crates_lister.id,
        url="some-url/api/v1/crates/some-package",
        visit_type="crates",
        extra_loader_arguments={
            "artifacts": [{"version": "0.0.1", "url": "some-package-0.0.1.crate"}],
        },
    )


def test_crates_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    crates_lister,
    crates_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.CratesLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadCrates",
        lister=crates_lister,
        listed_origin=crates_listed_origin,
    )
