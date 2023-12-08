# Copyright (C) 2022-2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.loader.tests import assert_task_and_visit_type_match
from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.core"


LISTER = Lister(name="nixguix", instance_name="example", id=uuid.uuid4())
# make mypy happy
assert LISTER is not None and LISTER.id is not None


@pytest.fixture
def nixguix_lister():
    return LISTER


LISTED_ORIGIN = ListedOrigin(
    lister_id=LISTER.id,
    url="https://nixguix.example.org/",
    visit_type="nixguix",
    extra_loader_arguments={
        "checksum_layout": "standard",
        "fallback_urls": ["https://example.org/mirror/artifact-0.0.1.pkg.xz"],
        "checksums": {"sha256": "some-valid-checksum"},
    },
)


LISTED_ORIGIN2 = ListedOrigin(
    lister_id=LISTER.id,
    url="https://nixguix.example.org/",
    visit_type="nixguix",
    extra_loader_arguments={
        "fallback_urls": ["https://example.org/mirror/artifact-0.0.1.pkg.xz"],
        "checksums": {"sha256": "some-valid-checksum"},
    },
)


LISTED_ORIGIN_COMPAT = ListedOrigin(
    lister_id=LISTER.id,
    url="https://nixguix.example.org/",
    visit_type="nixguix",
    extra_loader_arguments={
        # Compatibility parameter task name
        "checksums_computation": "standard",
        "fallback_urls": ["https://example.org/mirror/artifact-0.0.1.pkg.xz"],
        "checksums": {"sha256": "some-valid-checksum"},
    },
)


@pytest.mark.parametrize("loader_name", ["Content", "TarballDirectory"])
@pytest.mark.parametrize(
    "listed_origin", [LISTED_ORIGIN, LISTED_ORIGIN2, LISTED_ORIGIN_COMPAT]
)
def test_loader_tasks_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    nixguix_lister,
    loader_name,
    listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.{loader_name}Loader",
        task_function_name=f"{NAMESPACE}.tasks.Load{loader_name}",
        lister=nixguix_lister,
        listed_origin=listed_origin,
    )


def test_check_no_discrepancy_between_task_and_visit_type():
    """For scheduling purposes the task names and the loader's visit type must match"""
    assert_task_and_visit_type_match("swh.loader.core.tasks")
