# Copyright (C) 2019-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.deposit"


@pytest.fixture
def deposit_lister():
    return Lister(name="deposit", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def deposit_listed_origin(deposit_lister):
    return ListedOrigin(
        lister_id=deposit_lister.id,
        url="https://example.org/project",
        visit_type="deposit",
        extra_loader_arguments={"deposit_id": "some-d-id"},
    )


def test_deposit_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    deposit_lister,
    deposit_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.DepositLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadDeposit",
        lister=deposit_lister,
        listed_origin=deposit_listed_origin,
    )
