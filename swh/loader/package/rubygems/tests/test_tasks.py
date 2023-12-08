# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.rubygems"


@pytest.fixture
def rubygems_lister():
    return Lister(name="rubygems", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def rubygems_listed_origin(rubygems_lister):
    return ListedOrigin(
        lister_id=rubygems_lister.id,
        url="https://rubygems.org/gems/whatever-package",
        visit_type="rubygems",
        extra_loader_arguments={
            "artifacts": [
                {
                    "url": "https://rubygems.org/downloads/whatever-package-0.0.1.gem",
                    "length": 1,
                    "version": "0.0.1",
                    "filename": "whatever-package-0.0.1.gem",
                    "checksums": {
                        "sha256": "85a8cf5f41890e9605265eeebfe9e99aa0350a01a3c799f9f55a0615a31a2f5f"  # noqa: B950
                    },
                }
            ],
            "rubygem_metadata": [
                {
                    "date": "2016-11-05T00:00:00+00:00",
                    "authors": "John Dodoe",
                    "version": "0.0.1",
                    "extrinsic_metadata_url": "https://rubygems.org/api/v2/rubygems/whatever-package/versions/0.0.1.json",  # noqa: B950
                },
            ],
        },
    )


def test_rubygems_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    rubygems_lister,
    rubygems_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.RubyGemsLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadRubyGems",
        lister=rubygems_lister,
        listed_origin=rubygems_listed_origin,
    )
