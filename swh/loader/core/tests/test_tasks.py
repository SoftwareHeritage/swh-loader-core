# Copyright (C) 2022-2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

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

    from collections import defaultdict
    from importlib import import_module

    import celery.app.task

    mod = import_module("swh.loader.core.tasks")
    task_names = [x for x in dir(mod) if x.startswith("load_")]
    loaders = [x for x in dir(mod) if x.endswith("Loader")]
    loaders_lower = [loader.lower() for loader in loaders]

    matching_visit_types = defaultdict(bool)
    for task_name in task_names:
        taskobj = getattr(mod, task_name)
        assert isinstance(taskobj, celery.app.task.Task)
        loader_type = task_name.replace("load_", "").replace("_", "")

        for loader_name_lower in loaders_lower:
            if loader_type in loader_name_lower:
                break
        else:
            raise AssertionError(f"No loader matching {loader_type} in {loaders_lower}")

        for loader in loaders:
            if loader_type not in loader.lower():
                continue

            loader_cls = getattr(mod, loader)
            visit_type = loader_cls.visit_type

            matching_visit_type = visit_type.replace("-", "") == loader_type
            assert (
                matching_visit_type is True
            ), f"Visit type <{visit_type}> does not match task name <{task_name}>"
            matching_visit_types[task_name] = matching_visit_type

    # We should have as many task names as we have matching visits
    assert len(task_names) == len(matching_visit_types.values()) and all(
        matching_visit_types.values()
    )
