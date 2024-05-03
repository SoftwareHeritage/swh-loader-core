# Copyright (C) 2019-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import os
from typing import Any, Dict

import pytest
import yaml

from swh.loader.core.utils import download, get_url_body
from swh.scheduler.model import ListedOrigin, Lister
from swh.scheduler.utils import create_origin_task


@pytest.fixture
def swh_storage_backend_config(swh_storage_postgresql) -> Dict[str, Any]:
    return {
        "cls": "retry",
        "storage": {
            "cls": "filter",
            "storage": {
                "cls": "buffer",
                "storage": {
                    "cls": "postgresql",
                    "db": swh_storage_postgresql.info.dsn,
                    "objstorage": {"cls": "memory"},
                },
            },
        },
    }


@pytest.fixture
def swh_loader_config(swh_storage_backend_config) -> Dict[str, Any]:
    return {
        "storage": swh_storage_backend_config,
    }


@pytest.fixture
def swh_config(swh_loader_config, monkeypatch, tmp_path) -> str:
    conffile = os.path.join(str(tmp_path), "loader.yml")
    with open(conffile, "w") as f:
        f.write(yaml.dump(swh_loader_config))
        monkeypatch.setenv("SWH_CONFIG_FILENAME", conffile)
    return conffile


@pytest.fixture(autouse=True, scope="session")
def swh_proxy():
    """Automatically inject this fixture in all tests to ensure no outside
    connection takes place.

    """
    os.environ["http_proxy"] = "http://localhost:999"
    os.environ["https_proxy"] = "http://localhost:999"


@pytest.fixture
def loading_task_creation_for_listed_origin_test(
    mocker,
    swh_scheduler_celery_app,
    swh_scheduler_celery_worker,
    swh_config,
):
    def test_implementation(
        loader_class_name: str,
        task_function_name: str,
        lister: Lister,
        listed_origin: ListedOrigin,
    ):
        mock_load = mocker.patch(f"{loader_class_name}.load")
        mock_load.return_value = {"status": "eventful"}

        task = create_origin_task(listed_origin, lister)

        res = swh_scheduler_celery_app.send_task(
            task_function_name,
            kwargs=task.arguments.kwargs,
        )
        assert res
        res.wait()
        assert res.successful()
        assert mock_load.called
        assert res.result == {"status": "eventful"}

    return test_implementation


@pytest.fixture(autouse=True)
def mock_retry_sleep(mocker):
    mocker.patch.object(download.retry, "sleep")
    mocker.patch.object(get_url_body.retry, "sleep")
