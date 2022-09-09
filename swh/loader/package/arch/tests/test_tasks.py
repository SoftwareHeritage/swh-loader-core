# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


def test_tasks_arch_loader(
    mocker, swh_scheduler_celery_app, swh_scheduler_celery_worker, swh_config
):
    mock_load = mocker.patch("swh.loader.package.arch.loader.ArchLoader.load")
    mock_load.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.arch.tasks.LoadArch",
        kwargs=dict(
            url="some-url/packages/s/some-package",
            artifacts=[
                {
                    "version": "0.0.1",
                    "url": "https://somewhere/some-package-0.0.1.pkg.xz",
                    "filename": "some-package-0.0.1.pkg.xz",
                    "length": 42,
                }
            ],
            arch_metadata=[
                {
                    "version": "0.0.1",
                    "arch": "aarch64",
                    "name": "some-package",
                    "repo": "community",
                    "last_modified": "1970-01-01T21:08:14",
                }
            ],
        ),
    )
    assert res
    res.wait()
    assert res.successful()
    assert mock_load.called
    assert res.result == {"status": "eventful"}
