# Copyright (C) 2022-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.crates"


@pytest.fixture
def crates_lister():
    return Lister(name="crates", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def crates_listed_origin(crates_lister):
    return ListedOrigin(
        lister_id=crates_lister.id,
        url="some-url/api/v1/crates/some-package",
        visit_type="crates",
        extra_loader_arguments={
            "artifacts": [
                {
                    "version": "0.0.1",
                    "filename": "some-package-0.0.1.crate",
                    "url": "https://somewhere/some-package-0.0.1.crate",
                    "checksums": {
                        "sha256": "5de32cb59a062672560d6f0842c4aa7714727457b9fe2daf8987d995a176a405",  # noqa: B950
                    },
                },
            ],
        },
    )


def test_crates_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    crates_lister,
    crates_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.CratesLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadCrates",
        lister=crates_lister,
        listed_origin=crates_listed_origin,
    )
