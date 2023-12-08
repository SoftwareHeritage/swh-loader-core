# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.arch"


@pytest.fixture
def arch_lister():
    return Lister(name="arch", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def arch_listed_origin(arch_lister):
    return ListedOrigin(
        lister_id=arch_lister.id,
        url="some-url/packages/s/some-package",
        visit_type="arch",
        extra_loader_arguments={
            "artifacts": [
                {
                    "version": "0.0.1",
                    "url": "https://somewhere/some-package-0.0.1.pkg.xz",
                    "filename": "some-package-0.0.1.pkg.xz",
                    "length": 42,
                }
            ],
            "arch_metadata": [
                {
                    "version": "0.0.1",
                    "arch": "aarch64",
                    "name": "some-package",
                    "repo": "community",
                    "last_modified": "1970-01-01T21:08:14",
                }
            ],
        },
    )


def test_arch_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    arch_lister,
    arch_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.ArchLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadArch",
        lister=arch_lister,
        listed_origin=arch_listed_origin,
    )
