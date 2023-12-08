# Copyright (C) 2019-2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.archive"


@pytest.fixture
def archive_lister():
    return Lister(name="archive-lister", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def archive_listed_origin(archive_lister):
    return ListedOrigin(
        lister_id=archive_lister.id,
        url="https://example.org/archives",
        visit_type="tar",
        extra_loader_arguments={
            "artifacts": [
                {
                    "time": "2010-08-14T01:41:56",
                    "url": "https://example.org/archives/project-v1.0.0.tar.gz",
                    "filename": "project-v1.0.0.tar.gz",
                    "version": "1.0.0",
                    "length": 2500,
                }
            ],
            "snapshot_append": True,
        },
    )


def test_archive_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    archive_lister,
    archive_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.ArchiveLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadTarball",
        lister=archive_lister,
        listed_origin=archive_listed_origin,
    )
