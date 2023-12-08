# Copyright (C) 2019-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.opam"

OPAM_LOADER_ARGS = {
    "url": "opam+https://opam.ocaml.org/packages/agrid",
    "opam_root": "/tmp/test_tasks_opam_loader",
    "opam_instance": "test_tasks_opam_loader",
    "opam_url": "https://opam.ocaml.org",
    "opam_package": "agrid",
}


@pytest.fixture
def opam_lister():
    return Lister(name="opam", instance_name="example", id=uuid.uuid4())


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


def test_opam_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    opam_lister,
    opam_listed_origin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.OpamLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadOpam",
        lister=opam_lister,
        listed_origin=opam_listed_origin,
    )
