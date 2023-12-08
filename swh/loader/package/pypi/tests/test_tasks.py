# Copyright (C) 2019-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.pypi"


@pytest.fixture
def pypi_lister():
    return Lister(name="pypi", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def pypi_listed_origin(pypi_lister):
    return ListedOrigin(
        lister_id=pypi_lister.id,
        url="https://pypi.example.org/package",
        visit_type="pypi",
    )


def test_pypi_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    pypi_lister,
    pypi_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.PyPILoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadPyPI",
        lister=pypi_lister,
        listed_origin=pypi_listed_origin,
    )
