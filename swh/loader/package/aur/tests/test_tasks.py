# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.aur"


@pytest.fixture
def aur_lister():
    return Lister(name="aur", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def aur_listed_origin(aur_lister):
    return ListedOrigin(
        lister_id=aur_lister.id,
        url="https://somewhere/some-package.git",
        visit_type="aur",
        extra_loader_arguments={
            "artifacts": [
                {
                    "filename": "some-package.tar.gz",
                    "url": "https://somewhere/some-package.tar.gz",
                    "version": "0.0.1",
                }
            ],
            "aur_metadata": [
                {
                    "version": "0.0.1",
                    "project_url": "https://somewhere/some-package",
                    "last_update": "1970-01-01T21:08:14",
                    "pkgname": "some-package",
                }
            ],
        },
    )


def test_aur_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    aur_lister,
    aur_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.AurLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadAur",
        lister=aur_lister,
        listed_origin=aur_listed_origin,
    )
