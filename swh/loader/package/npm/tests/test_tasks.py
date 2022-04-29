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
def npm_lister():
    return Lister(name="npm-lister", instance_name="npm", id=uuid.uuid4())


@pytest.fixture
def npm_listed_origin(npm_lister):
    return ListedOrigin(
        lister_id=npm_lister.id,
        url="https://www.npmjs.com/package/some-package",
        visit_type="npm",
    )


def test_tasks_npm_loader(
    mocker,
    swh_scheduler_celery_app,
):
    mock_load = mocker.patch("swh.loader.package.npm.loader.NpmLoader.load")
    mock_load.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.npm.tasks.LoadNpm",
        kwargs=dict(url="https://www.npmjs.com/package/some-package"),
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}


def test_tasks_npm_loader_for_listed_origin(
    mocker, swh_scheduler_celery_app, npm_lister, npm_listed_origin
):
    mock_load = mocker.patch("swh.loader.package.npm.loader.NpmLoader.load")
    mock_load.return_value = {"status": "eventful"}

    task_dict = create_origin_task_dict(npm_listed_origin, npm_lister)

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.npm.tasks.LoadNpm",
        kwargs=task_dict["arguments"]["kwargs"],
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}
