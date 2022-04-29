# Copyright (C) 2019-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister
from swh.scheduler.utils import create_origin_task_dict


@pytest.fixture(autouse=True)
def celery_worker_and_swh_config(swh_scheduler_celery_worker, swh_config):
    pass


@pytest.fixture
def debian_lister():
    return Lister(name="debian-lister", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def debian_listed_origin(debian_lister):
    return ListedOrigin(
        lister_id=debian_lister.id,
        url="https://debian.example.org/package",
        visit_type="debian",
        extra_loader_arguments={"packages": {}},
    )


def test_tasks_debian_loader(mocker, swh_scheduler_celery_app):
    mock_load = mocker.patch("swh.loader.package.debian.loader.DebianLoader.load")
    mock_load.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.debian.tasks.LoadDebian",
        kwargs=dict(url="some-url", packages={}),
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}


def test_tasks_debian_loader_for_listed_origin(
    mocker, swh_scheduler_celery_app, debian_lister, debian_listed_origin
):
    mock_load = mocker.patch("swh.loader.package.debian.loader.DebianLoader.load")
    mock_load.return_value = {"status": "eventful"}

    task_dict = create_origin_task_dict(debian_listed_origin, debian_lister)

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.debian.tasks.LoadDebian",
        kwargs=task_dict["arguments"]["kwargs"],
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}
