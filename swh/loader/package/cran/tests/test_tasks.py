# Copyright (C) 2019-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.cran"


@pytest.fixture
def cran_lister():
    return Lister(name="cran", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def cran_listed_origin(cran_lister):
    return ListedOrigin(
        lister_id=cran_lister.id,
        url="https://cran.example.org/project",
        visit_type="cran",
        extra_loader_arguments={
            "artifacts": [{"version": "1.2.3", "url": "artifact-url"}],
        },
    )


def test_cran_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    cran_lister,
    cran_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.CRANLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadCRAN",
        lister=cran_lister,
        listed_origin=cran_listed_origin,
    )
