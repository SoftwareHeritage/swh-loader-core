# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.core"


@pytest.fixture
def nixguix_lister():
    return Lister(name="nixguix", instance_name="example", id=uuid.uuid4())


@pytest.mark.parametrize("loader_name", ["Content", "Directory"])
def test_loader_tasks_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    nixguix_lister,
    loader_name,
):

    listed_origin = ListedOrigin(
        lister_id=nixguix_lister.id,
        url="https://example.org/artifact/artifact",
        visit_type=loader_name.lower(),
        extra_loader_arguments={
            "fallback_urls": ["https://example.org/mirror/artifact-0.0.1.pkg.xz"],
            "checksums": {"sha256": "some-valid-checksum"},
        },
    )

    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.{loader_name}Loader",
        task_function_name=f"{NAMESPACE}.tasks.Load{loader_name}",
        lister=nixguix_lister,
        listed_origin=listed_origin,
    )
