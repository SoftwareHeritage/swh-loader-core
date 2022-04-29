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
def archive_lister():
    return Lister(name="archive-lister", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def archive_listed_origin(archive_lister):
    return ListedOrigin(
        lister_id=archive_lister.id,
        url="https://example.org/archives",
        visit_type="tar",
        extra_loader_arguments={
            "artifacts": [],
            "snapshot_append": True,
        },
    )


def test_tasks_archive_loader(
    mocker,
    swh_scheduler_celery_app,
):
    mock_load = mocker.patch("swh.loader.package.archive.loader.ArchiveLoader.load")
    mock_load.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.archive.tasks.LoadArchive",
        kwargs=dict(url="https://gnu.org/", artifacts=[]),
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}


def test_tasks_archive_loader_snapshot_append(
    mocker,
    swh_scheduler_celery_app,
):
    mock_load = mocker.patch("swh.loader.package.archive.loader.ArchiveLoader.load")
    mock_load.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.archive.tasks.LoadArchive",
        kwargs=dict(url="https://gnu.org/", artifacts=[], snapshot_append=True),
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}


def test_tasks_archive_loader_for_listed_origin(
    mocker,
    swh_scheduler_celery_app,
    archive_lister,
    archive_listed_origin,
):
    mock_load = mocker.patch("swh.loader.package.archive.loader.ArchiveLoader.load")
    mock_load.return_value = {"status": "eventful"}

    task_dict = create_origin_task_dict(archive_listed_origin, archive_lister)

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.archive.tasks.LoadArchive",
        kwargs=task_dict["arguments"]["kwargs"],
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}
