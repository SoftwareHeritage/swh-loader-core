# Copyright (C) 2020-2022  The Software Heritage developers
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
def nixguix_lister():
    return Lister(name="nixguix-lister", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def nixguix_listed_origin(nixguix_lister):
    return ListedOrigin(
        lister_id=nixguix_lister.id,
        url="https://nixguix.example.org/",
        visit_type="nixguix",
    )


def test_tasks_nixguix_loader(
    mocker,
    swh_scheduler_celery_app,
):
    mock_loader = mocker.patch(
        "swh.loader.package.nixguix.loader.NixGuixLoader.from_configfile"
    )
    mock_loader.return_value = mock_loader
    mock_loader.load.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.nixguix.tasks.LoadNixguix", kwargs=dict(url="some-url")
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_loader.called
    assert res.result == {"status": "eventful"}


def test_tasks_nixguix_loader_for_listed_origin(
    mocker, swh_scheduler_celery_app, nixguix_lister, nixguix_listed_origin
):
    mock_loader = mocker.patch(
        "swh.loader.package.nixguix.loader.NixGuixLoader.from_configfile"
    )
    mock_loader.return_value = mock_loader
    mock_loader.load.return_value = {"status": "eventful"}

    task_dict = create_origin_task_dict(nixguix_listed_origin, nixguix_lister)

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.nixguix.tasks.LoadNixguix",
        kwargs=task_dict["arguments"]["kwargs"],
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_loader.called
    assert res.result == {"status": "eventful"}
