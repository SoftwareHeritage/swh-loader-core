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
def pypi_lister():
    return Lister(name="pypi-lister", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def pypi_listed_origin(pypi_lister):
    return ListedOrigin(
        lister_id=pypi_lister.id,
        url="https://pypi.example.org/package",
        visit_type="pypi",
    )


def test_tasks_pypi_loader(
    mocker,
    swh_scheduler_celery_app,
):
    mock_load = mocker.patch("swh.loader.package.pypi.loader.PyPILoader.load")
    mock_load.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.pypi.tasks.LoadPyPI", kwargs=dict(url="some-url")
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}


def test_tasks_pypi_loader_for_listed_origin(
    mocker,
    swh_scheduler_celery_app,
    pypi_lister,
    pypi_listed_origin,
):
    mock_load = mocker.patch("swh.loader.package.pypi.loader.PyPILoader.load")
    mock_load.return_value = {"status": "eventful"}

    task_dict = create_origin_task_dict(pypi_listed_origin, pypi_lister)

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.pypi.tasks.LoadPyPI",
        kwargs=task_dict["arguments"]["kwargs"],
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}
