# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

from .test_cpan import (
    API_BASE_URL,
    ORIGIN_ARTIFACTS,
    ORIGIN_MODULE_METADATA,
    ORIGIN_URL,
)

NAMESPACE = "swh.loader.package.cpan"


@pytest.fixture
def cpan_lister():
    return Lister(name="cpan", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def cpan_listed_origin(cpan_lister):
    return ListedOrigin(
        lister_id=cpan_lister.id,
        url=ORIGIN_URL,
        visit_type="cpan",
        extra_loader_arguments={
            "api_base_url": API_BASE_URL,
            "artifacts": ORIGIN_ARTIFACTS,
            "module_metadata": ORIGIN_MODULE_METADATA,
        },
    )


def test_cpan_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    cpan_lister,
    cpan_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.CpanLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadCpan",
        lister=cpan_lister,
        listed_origin=cpan_listed_origin,
    )
