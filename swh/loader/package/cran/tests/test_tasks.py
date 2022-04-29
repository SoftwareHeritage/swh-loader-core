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
def cran_lister():
    return Lister(name="cran-lister", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def cran_listed_origin(cran_lister):
    return ListedOrigin(
        lister_id=cran_lister.id,
        url="https://cran.example.org/project",
        visit_type="cran",
        extra_loader_arguments={
            "artifacts": [{"version": "1.2.3", "url": "artifact-url"}],
        },
    )


def test_tasks_cran_loader(
    mocker,
    swh_scheduler_celery_app,
):
    mock_load = mocker.patch("swh.loader.package.cran.loader.CRANLoader.load")
    mock_load.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.cran.tasks.LoadCRAN",
        kwargs=dict(
            url="some-url",
            artifacts=[{"version": "1.2.3", "url": "artifact-url"}],
        ),
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}


def test_tasks_cran_loader_for_listed_origin(
    mocker,
    swh_scheduler_celery_app,
    cran_lister,
    cran_listed_origin,
):
    mock_load = mocker.patch("swh.loader.package.cran.loader.CRANLoader.load")
    mock_load.return_value = {"status": "eventful"}

    task_dict = create_origin_task_dict(cran_listed_origin, cran_lister)

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.cran.tasks.LoadCRAN",
        kwargs=task_dict["arguments"]["kwargs"],
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}
