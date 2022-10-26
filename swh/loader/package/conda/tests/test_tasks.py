# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.conda"


@pytest.fixture
def conda_lister():
    return Lister(name="conda", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def conda_listed_origin(conda_lister):
    return ListedOrigin(
        lister_id=conda_lister.id,
        url="https://anaconda.org/channel/some-package",
        visit_type="conda",
        extra_loader_arguments={
            "artifacts": [{"version": "0.0.1", "url": "some-package-0.0.1.tar.bz2"}],
        },
    )


def test_conda_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    conda_lister,
    conda_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.CondaLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadConda",
        lister=conda_lister,
        listed_origin=conda_listed_origin,
    )
