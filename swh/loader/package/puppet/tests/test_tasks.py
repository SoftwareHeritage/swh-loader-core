# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


def test_tasks_puppet_loader(
    mocker, swh_scheduler_celery_app, swh_scheduler_celery_worker, swh_config
):
    mock_load = mocker.patch("swh.loader.package.puppet.loader.PuppetLoader.load")
    mock_load.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.puppet.tasks.LoadPuppet",
        kwargs=dict(
            url="some-url/api/packages/some-package",
            artifacts={
                "1.0.0": {
                    "url": "https://domain/some-package-1.0.0.tar.gz",
                    "version": "1.0.0",
                    "filename": "some-module-1.0.0.tar.gz",
                    "last_update": "2011-11-20T13:40:30-08:00",
                },
            },
        ),
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}
