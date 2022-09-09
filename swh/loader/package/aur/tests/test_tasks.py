# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


def test_tasks_aur_loader(
    mocker, swh_scheduler_celery_app, swh_scheduler_celery_worker, swh_config
):
    mock_load = mocker.patch("swh.loader.package.aur.loader.AurLoader.load")
    mock_load.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.aur.tasks.LoadAur",
        kwargs=dict(
            url="https://somewhere/some-package.git",
            artifacts=[
                {
                    "filename": "some-package.tar.gz",
                    "url": "https://somewhere/some-package.tar.gz",
                    "version": "0.0.1",
                }
            ],
            aur_metadata=[
                {
                    "version": "0.0.1",
                    "project_url": "https://somewhere/some-package",
                    "last_update": "1970-01-01T21:08:14",
                    "pkgname": "some-package",
                }
            ],
        ),
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}
