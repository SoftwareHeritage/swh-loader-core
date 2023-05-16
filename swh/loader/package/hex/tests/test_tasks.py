# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.hex"

ORIGIN_URL = "https://hex.pm/packages/gpio"

RELEASES = {
    "0.6.0": {
        "name": "gpio",
        "release_url": "https://hex.pm/api/packages/gpio/releases/0.6.0",
        "inserted_at": "2023-02-05T09:55:17.707695Z",
    }
}


@pytest.fixture
def hex_lister():
    return Lister(name="hex", instance_name="hex", id=uuid.uuid4())


@pytest.fixture
def hex_listed_origin(hex_lister):
    return ListedOrigin(
        lister_id=hex_lister.id,
        url=ORIGIN_URL,
        visit_type="hex",
        extra_loader_arguments={
            "releases": RELEASES,
        },
    )


def test_rpm_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    hex_lister,
    hex_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.HexLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadHex",
        lister=hex_lister,
        listed_origin=hex_listed_origin,
    )
