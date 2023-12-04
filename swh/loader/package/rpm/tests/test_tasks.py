# Copyright (C) 2022-2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.rpm"

RPM_ORIGIN_URL = "rpm://Fedora/packages/0xFFFF"

RPM_PACKAGES = {
    "36/Everything/0.10-4": {
        "name": "0xFFFF",
        "version": "0.10-4",
        "release": 36,
        "edition": "Everything",
        "build_time": "2022-01-19T19:13:53+00:00",
        "url": (
            "https://archives.fedoraproject.org/pub/archive/fedora/linux/releases/"
            "36/Everything/source/tree/Packages/0/0xFFFF-0.10-4.fc36.src.rpm"
        ),
        "checksums": {
            "sha256": "45eee8d990d502324ae665233c320b8a5469c25d735f1862e094c1878d6ff2cd"
        },
    }
}


@pytest.fixture
def fedora_lister():
    return Lister(name="rpm", instance_name="Fedora", id=uuid.uuid4())


@pytest.fixture
def fedora_listed_origin(fedora_lister):
    return ListedOrigin(
        lister_id=fedora_lister.id,
        url=RPM_ORIGIN_URL,
        visit_type="rpm",
        extra_loader_arguments={
            "packages": RPM_PACKAGES,
        },
    )


def test_rpm_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    fedora_lister,
    fedora_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.RpmLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadRpm",
        lister=fedora_lister,
        listed_origin=fedora_listed_origin,
    )
