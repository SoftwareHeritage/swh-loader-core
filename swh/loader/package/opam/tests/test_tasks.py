# Copyright (C) 2019-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister
from swh.scheduler.utils import create_origin_task_dict

OPAM_LOADER_ARGS = {
    "url": "opam+https://opam.ocaml.org/packages/agrid",
    "opam_root": "/tmp/test_tasks_opam_loader",
    "opam_instance": "test_tasks_opam_loader",
    "opam_url": "https://opam.ocaml.org",
    "opam_package": "agrid",
}


@pytest.fixture(autouse=True)
def celery_worker_and_swh_config(swh_scheduler_celery_worker, swh_config):
    pass


@pytest.fixture
def opam_lister():
    return Lister(name="opam-lister", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def opam_listed_origin(opam_lister):
    return ListedOrigin(
        lister_id=opam_lister.id,
        url=OPAM_LOADER_ARGS["url"],
        visit_type="opam",
        extra_loader_arguments={
            k: v for k, v in OPAM_LOADER_ARGS.items() if k != "url"
        },
    )


def test_tasks_opam_loader(
    mocker,
    swh_scheduler_celery_app,
):
    mock_load = mocker.patch("swh.loader.package.opam.loader.OpamLoader.load")
    mock_load.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.opam.tasks.LoadOpam",
        kwargs=OPAM_LOADER_ARGS,
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}


def test_tasks_opam_loader_for_listed_origin(
    mocker, swh_scheduler_celery_app, opam_lister, opam_listed_origin
):
    mock_load = mocker.patch("swh.loader.package.opam.loader.OpamLoader.load")
    mock_load.return_value = {"status": "eventful"}

    task_dict = create_origin_task_dict(opam_listed_origin, opam_lister)

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.opam.tasks.LoadOpam",
        kwargs=task_dict["arguments"]["kwargs"],
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}
