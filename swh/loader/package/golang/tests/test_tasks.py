# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.golang"


@pytest.fixture
def golang_lister():
    return Lister(name="golang", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def golang_listed_origin(golang_lister):
    return ListedOrigin(
        lister_id=golang_lister.id,
        url="https://pkg.go.dev/golang.org/whatever/package",
        visit_type="golang",
    )


def test_golang_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    golang_lister,
    golang_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.GolangLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadGolang",
        lister=golang_lister,
        listed_origin=golang_listed_origin,
    )
