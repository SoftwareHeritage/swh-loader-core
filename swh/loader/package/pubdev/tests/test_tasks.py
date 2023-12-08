# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.pubdev"


@pytest.fixture
def pubdev_lister():
    return Lister(name="pubdev", instance_name="example", id=uuid.uuid4())


@pytest.fixture
def pubdev_listed_origin(pubdev_lister):
    return ListedOrigin(
        lister_id=pubdev_lister.id,
        url="https://pub.dev/packages/some-package",
        visit_type="pubdev",
    )


def test_pubdev_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    pubdev_lister,
    pubdev_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.PubDevLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadPubDev",
        lister=pubdev_lister,
        listed_origin=pubdev_listed_origin,
    )
