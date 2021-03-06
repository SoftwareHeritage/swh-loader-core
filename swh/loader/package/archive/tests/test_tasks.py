# Copyright (C) 2019  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


def test_archive_loader(
    mocker, swh_scheduler_celery_app, swh_scheduler_celery_worker, swh_config
):
    mock_loader = mocker.patch("swh.loader.package.archive.loader.ArchiveLoader.load")
    mock_loader.return_value = {"status": "eventful"}

    res = swh_scheduler_celery_app.send_task(
        "swh.loader.package.archive.tasks.LoadArchive",
        kwargs={"url": "some-url", "artifacts": []},
    )
    assert res
    res.wait()
    assert res.successful()

    assert res.result == {"status": "eventful"}
