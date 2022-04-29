# Copyright (C) 2019-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister
from swh.scheduler.utils import create_origin_task_dict

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


@pytest.fixture(autouse=True)
def celery_worker_and_swh_config(swh_scheduler_celery_worker, swh_config):
    pass


@pytest.fixture
def maven_lister():
    return Lister(name="maven-lister", instance_name="example", id=uuid.uuid4())


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


def test_tasks_maven_loader(
    mocker,
    swh_scheduler_celery_app,
):
    mock_load = mocker.patch("swh.loader.package.maven.loader.MavenLoader.load")
    mock_load.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.maven.tasks.LoadMaven",
        kwargs=dict(
            url=MVN_ARTIFACTS[0]["url"],
            artifacts=MVN_ARTIFACTS,
        ),
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}


def test_tasks_maven_loader_for_listed_origin(
    mocker, swh_scheduler_celery_app, maven_lister, maven_listed_origin
):
    mock_load = mocker.patch("swh.loader.package.maven.loader.MavenLoader.load")
    mock_load.return_value = {"status": "eventful"}

    task_dict = create_origin_task_dict(maven_listed_origin, maven_lister)

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.maven.tasks.LoadMaven",
        kwargs=task_dict["arguments"]["kwargs"],
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}
