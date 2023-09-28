# Copyright (C) 2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import uuid

import pytest

from swh.scheduler.model import ListedOrigin, Lister

NAMESPACE = "swh.loader.package.bioconductor"

ORIGIN_URL = "https://bioconductor.org/packages/annotation"

PACKAGES = {
    "3.17/bioc/1.24.1": {
        "package": "annotation",
        "release": "3.17",
        "tar_url": (
            "https://www.bioconductor.org/packages/3.17/"
            "bioc/src/contrib/annotation_1.24.1.tar.gz"
        ),
        "version": "1.24.1",
        "category": "bioc",
    },
    "3.17/workflows/1.24.1": {
        "package": "annotation",
        "release": "3.17",
        "tar_url": (
            "https://www.bioconductor.org/packages/3.17/"
            "workflows/src/contrib/annotation_1.24.1.tar.gz"
        ),
        "version": "1.24.1",
        "category": "workflows",
    },
}


@pytest.fixture
def bioconductor_lister():
    return Lister(name="bioconductor", instance_name="Bioconductor", id=uuid.uuid4())


@pytest.fixture
def bioconductor_listed_origin(bioconductor_lister):
    return ListedOrigin(
        lister_id=bioconductor_lister.id,
        url=ORIGIN_URL,
        visit_type="biocondutor",
        extra_loader_arguments={
            "packages": PACKAGES,
        },
    )


def test_bioconductor_loader_task_for_listed_origin(
    loading_task_creation_for_listed_origin_test,
    bioconductor_lister: Lister,
    bioconductor_listed_origin: ListedOrigin,
):
    loading_task_creation_for_listed_origin_test(
        loader_class_name=f"{NAMESPACE}.loader.BioconductorLoader",
        task_function_name=f"{NAMESPACE}.tasks.LoadBioconductor",
        lister=bioconductor_lister,
        listed_origin=bioconductor_listed_origin,
    )
