# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister
from swh.scheduler.utils import create_origin_task_dict

NAMESPACE = "swh.loader.core"


@pytest.fixture
def nixguix_lister():
    return Lister(name="nixguix", instance_name="example", id=uuid.uuid4())


@pytest.mark.parametrize("loader_name", ["Content", "Directory"])
def test_tasks_loader_for_listed_origin(
    mocker,
    swh_scheduler_celery_app,
    swh_scheduler_celery_worker,
    swh_config,
    nixguix_lister,
    loader_name,
):
    mock_load = mocker.patch(f"{NAMESPACE}.loader.{loader_name}Loader.load")
    mock_load.return_value = {"status": "eventful"}

    listed_origin = ListedOrigin(
        lister_id=nixguix_lister.id,
        url="https://example.org/artifact/artifact",
        visit_type=loader_name.lower(),
        extra_loader_arguments={
            "fallback_urls": ["https://example.org/mirror/artifact-0.0.1.pkg.xz"],
            "checksums": {"sha256": "some-valid-checksum"},
        },
    )

    task_dict = create_origin_task_dict(listed_origin, nixguix_lister)

    res = swh_scheduler_celery_app.send_task(
        f"{NAMESPACE}.tasks.Load{loader_name}",
        kwargs=task_dict["arguments"]["kwargs"],
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}
