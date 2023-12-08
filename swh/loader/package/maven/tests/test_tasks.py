# Copyright (C) 2019-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.maven"

MVN_ARTIFACTS = [
    {
        "time": 1626109619335,
        "url": "https://repo1.maven.org/maven2/al/aldi/sprova4j/0.1.0/"
        + "sprova4j-0.1.0.jar",
        "gid": "al.aldi",
        "aid": "sprova4j",
        "filename": "sprova4j-0.1.0.jar",
        "version": "0.1.0",
        "base_url": "https://repo1.maven.org/maven2/",
    },
]


@pytest.fixture
def maven_lister():
    return Lister(name="maven", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def maven_listed_origin(maven_lister):
    return ListedOrigin(
        lister_id=maven_lister.id,
        url=MVN_ARTIFACTS[0]["url"],
        visit_type="maven",
        extra_loader_arguments={
            "artifacts": MVN_ARTIFACTS,
        },
    )


def test_maven_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    maven_lister,
    maven_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.MavenLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadMaven",
        lister=maven_lister,
        listed_origin=maven_listed_origin,
    )
