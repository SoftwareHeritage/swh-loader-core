# Copyright (C) 2019-2022 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import datetime
import hashlib
from itertools import chain
import json
import os
from pathlib import Path

import pytest

from swh.core.tarball import uncompress
from swh.loader.package import __version__
from swh.loader.package.maven.loader import MavenLoader, MavenPackageInfo
from swh.loader.package.utils import EMPTY_AUTHOR
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.from_disk import Directory, iter_directory
from swh.model.hashutil import hash_to_bytes
from swh.model.model import (
    RawExtrinsicMetadata,
    Release,
    Snapshot,
    SnapshotBranch,
    TargetType,
    TimestampWithTimezone,
)
from swh.model.model import MetadataAuthority, MetadataAuthorityType, MetadataFetcher
from swh.model.model import ObjectType as ModelObjectType
from swh.model.swhids import CoreSWHID, ExtendedObjectType, ExtendedSWHID, ObjectType
from swh.storage.algos.snapshot import snapshot_get_all_branches

REPO_BASE_URL = "https://repo1.maven.org/maven2/"

MVN_ORIGIN_URL = f"{REPO_BASE_URL}al/aldi/sprova4j"

MVN_ARTIFACTS = [
    {
        "time": "2021-07-12 19:06:59.335000",
        "gid": "al.aldi",
        "aid": "sprova4j",
        "filename": "sprova4j-0.1.0-sources.jar",
        "version": "0.1.0",
        "base_url": REPO_BASE_URL,
        "url": f"{REPO_BASE_URL}al/aldi/sprova4j/0.1.0/sprova4j-0.1.0-sources.jar",
    },
    {
        "time": "2021-07-12 19:37:05.534000",
        "gid": "al.aldi",
        "aid": "sprova4j",
        "filename": "sprova4j-0.1.1-sources.jar",
        "version": "0.1.1",
        "base_url": REPO_BASE_URL,
        "url": f"{REPO_BASE_URL}al/aldi/sprova4j/0.1.1/sprova4j-0.1.1-sources.jar",
    },
]

MVN_ARTIFACTS_POM = [
    f"{REPO_BASE_URL}al/aldi/sprova4j/0.1.0/sprova4j-0.1.0.pom",
    f"{REPO_BASE_URL}al/aldi/sprova4j/0.1.1/sprova4j-0.1.1.pom",
]

REL_MSGS = (
    b"Synthetic release for archive at https://repo1.maven.org/maven2/al/aldi/"
    b"sprova4j/0.1.0/sprova4j-0.1.0-sources.jar\n",
    b"Synthetic release for archive at https://repo1.maven.org/maven2/al/aldi/"
    b"sprova4j/0.1.1/sprova4j-0.1.1-sources.jar\n",
)

REL_DATES = (
    TimestampWithTimezone.from_datetime(
        datetime.datetime(2021, 7, 12, 19, 6, 59, 335000, tzinfo=datetime.timezone.utc)
    ),
    TimestampWithTimezone.from_datetime(
        datetime.datetime(2021, 7, 12, 19, 37, 5, 534000, tzinfo=datetime.timezone.utc)
    ),
)


@pytest.fixture
def data_jar_1(datadir):
    content = Path(
        datadir, "https_maven.org", "sprova4j-0.1.0-sources.jar"
    ).read_bytes()
    return content


@pytest.fixture
def data_pom_1(datadir):
    content = Path(datadir, "https_maven.org", "sprova4j-0.1.0.pom").read_bytes()
    return content


@pytest.fixture
def data_jar_2(datadir):
    content = Path(
        datadir, "https_maven.org", "sprova4j-0.1.1-sources.jar"
    ).read_bytes()
    return content


@pytest.fixture
def data_pom_2(datadir):
    content = Path(datadir, "https_maven.org", "sprova4j-0.1.1.pom").read_bytes()
    return content


@pytest.fixture
def jar_dirs(datadir, tmp_path):
    jar_1_path = os.path.join(datadir, "https_maven.org", "sprova4j-0.1.0-sources.jar")
    jar_2_path = os.path.join(datadir, "https_maven.org", "sprova4j-0.1.1-sources.jar")

    jar_1_extract_path = os.path.join(tmp_path, "jar_1")
    jar_2_extract_path = os.path.join(tmp_path, "jar_2")

    uncompress(jar_1_path, jar_1_extract_path)
    uncompress(jar_2_path, jar_2_extract_path)

    jar_1_dir = Directory.from_disk(path=jar_1_extract_path.encode())
    jar_2_dir = Directory.from_disk(path=jar_2_extract_path.encode())

    return [jar_1_dir, jar_2_dir]


@pytest.fixture
def expected_contents_and_directories(jar_dirs):
    jar_1_cnts, _, jar_1_dirs = iter_directory(jar_dirs[0])
    jar_2_cnts, _, jar_2_dirs = iter_directory(jar_dirs[1])

    contents = {cnt.sha1 for cnt in chain(jar_1_cnts, jar_2_cnts)}
    directories = {dir.id for dir in chain(jar_1_dirs, jar_2_dirs)}

    return contents, directories


@pytest.fixture
def expected_releases(jar_dirs):
    return [
        Release(
            name=b"0.1.0",
            message=REL_MSGS[0],
            author=EMPTY_AUTHOR,
            date=REL_DATES[0],
            target_type=ModelObjectType.DIRECTORY,
            target=jar_dirs[0].hash,
            synthetic=True,
            metadata=None,
        ),
        Release(
            name=b"0.1.1",
            message=REL_MSGS[1],
            author=EMPTY_AUTHOR,
            date=REL_DATES[1],
            target_type=ModelObjectType.DIRECTORY,
            target=jar_dirs[1].hash,
            synthetic=True,
            metadata=None,
        ),
    ]


@pytest.fixture
def expected_snapshot(expected_releases):
    return Snapshot(
        branches={
            b"HEAD": SnapshotBranch(
                target_type=TargetType.ALIAS,
                target=b"releases/0.1.1",
            ),
            b"releases/0.1.0": SnapshotBranch(
                target_type=TargetType.RELEASE,
                target=expected_releases[0].id,
            ),
            b"releases/0.1.1": SnapshotBranch(
                target_type=TargetType.RELEASE,
                target=expected_releases[1].id,
            ),
        },
    )


@pytest.fixture
def expected_json_metadata():
    return MVN_ARTIFACTS


@pytest.fixture
def expected_pom_metadata(data_pom_1, data_pom_2):
    return [data_pom_1, data_pom_2]


@pytest.fixture(autouse=True)
def network_requests_mock(
    requests_mock,
    data_jar_1,
    data_pom_1,
    data_jar_2,
    data_pom_2,
):
    requests_mock.get(MVN_ARTIFACTS[0]["url"], content=data_jar_1)
    requests_mock.get(MVN_ARTIFACTS_POM[0], content=data_pom_1)
    requests_mock.get(MVN_ARTIFACTS[1]["url"], content=data_jar_2)
    requests_mock.get(MVN_ARTIFACTS_POM[1], content=data_pom_2)


def test_maven_loader_visit_with_no_artifact_found(swh_storage, requests_mock_datadir):
    origin_url = "https://ftp.g.o/unknown"
    unknown_artifact_url = "https://ftp.g.o/unknown/8sync-0.1.0.tar.gz"
    loader = MavenLoader(
        swh_storage,
        origin_url,
        artifacts=[
            {
                "time": "2021-07-18 08:05:05.187000",
                "url": unknown_artifact_url,  # unknown artifact
                "filename": "8sync-0.1.0.tar.gz",
                "gid": "al/aldi",
                "aid": "sprova4j",
                "version": "0.1.0",
                "base_url": "https://repo1.maven.org/maven2/",
            }
        ],
    )

    actual_load_status = loader.load()
    assert actual_load_status["status"] == "uneventful"
    assert actual_load_status["snapshot_id"] is not None

    expected_snapshot_id = "1a8893e6a86f444e8be8e7bda6cb34fb1735a00e"
    assert actual_load_status["snapshot_id"] == expected_snapshot_id

    stats = get_stats(swh_storage)

    assert_last_visit_matches(swh_storage, origin_url, status="partial", type="maven")

    assert {
        "content": 0,
        "directory": 0,
        "origin": 1,
        "origin_visit": 1,
        "release": 0,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats


def test_maven_loader_jar_visit_inconsistent_base_url(
    swh_storage, requests_mock, data_jar_1, data_pom_1
):
    """With no prior visit, loading a jar ends up with 1 snapshot"""
    with pytest.raises(ValueError, match="more than one Maven instance"):
        MavenLoader(
            swh_storage,
            MVN_ORIGIN_URL,
            artifacts=[
                MVN_ARTIFACTS[0],
                {**MVN_ARTIFACTS[1], "base_url": "http://maven.example/"},
            ],
        )


def test_maven_loader_first_visit(
    swh_storage, expected_contents_and_directories, expected_snapshot, expected_releases
):
    """With no prior visit, loading a jar ends up with 1 snapshot"""

    loader = MavenLoader(swh_storage, MVN_ORIGIN_URL, artifacts=MVN_ARTIFACTS)

    actual_load_status = loader.load()
    assert actual_load_status["status"] == "eventful"

    actual_snapshot = snapshot_get_all_branches(
        swh_storage, hash_to_bytes(actual_load_status["snapshot_id"])
    )

    assert actual_load_status["snapshot_id"] == expected_snapshot.id.hex()
    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert_last_visit_matches(swh_storage, MVN_ORIGIN_URL, status="full", type="maven")

    expected_contents, expected_directories = expected_contents_and_directories
    assert list(swh_storage.content_missing_per_sha1(expected_contents)) == []
    assert list(swh_storage.directory_missing(expected_directories)) == []

    rel_id = actual_snapshot.branches[b"releases/0.1.0"].target
    rel2_id = actual_snapshot.branches[b"releases/0.1.1"].target
    releases = swh_storage.release_get([rel_id, rel2_id])

    assert releases == expected_releases

    assert {
        "content": len(expected_contents),
        "directory": len(expected_directories),
        "origin": 1,
        "origin_visit": 1,
        "release": 2,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats


def test_maven_loader_2_visits_without_change(
    swh_storage, requests_mock, expected_snapshot
):
    """With no prior visit, load a maven project ends up with 1 snapshot"""

    loader = MavenLoader(swh_storage, MVN_ORIGIN_URL, artifacts=MVN_ARTIFACTS)

    actual_load_status = loader.load()
    assert actual_load_status["status"] == "eventful"

    assert actual_load_status["snapshot_id"] == expected_snapshot.id.hex()

    assert_last_visit_matches(swh_storage, MVN_ORIGIN_URL, status="full", type="maven")

    actual_load_status2 = loader.load()
    assert actual_load_status2["status"] == "uneventful"
    assert actual_load_status2["snapshot_id"] is not None
    assert actual_load_status["snapshot_id"] == actual_load_status2["snapshot_id"]

    assert_last_visit_matches(swh_storage, MVN_ORIGIN_URL, status="full", type="maven")

    # Make sure we have only one entry in history for the pom fetch, one for
    # the actual download of jar, and that they're correct.
    urls_history = [str(req.url) for req in list(requests_mock.request_history)]
    assert urls_history == [
        MVN_ARTIFACTS[0]["url"],
        MVN_ARTIFACTS_POM[0],
        MVN_ARTIFACTS[1]["url"],
        MVN_ARTIFACTS_POM[1],
    ]


def test_maven_loader_extrinsic_metadata(
    swh_storage, expected_releases, expected_json_metadata, expected_pom_metadata
):
    """With no prior visit, loading a jar ends up with 1 snapshot.
    Extrinsic metadata is the pom file associated to the source jar.
    """
    loader = MavenLoader(swh_storage, MVN_ORIGIN_URL, artifacts=MVN_ARTIFACTS)

    actual_load_status = loader.load()
    assert actual_load_status["status"] == "eventful"

    for i, expected_release in enumerate(expected_releases):

        expected_release_id = expected_release.id
        release = swh_storage.release_get([expected_release_id])[0]
        assert release is not None

        release_swhid = CoreSWHID(
            object_type=ObjectType.RELEASE, object_id=expected_release_id
        )
        directory_swhid = ExtendedSWHID(
            object_type=ExtendedObjectType.DIRECTORY, object_id=release.target
        )
        metadata_authority = MetadataAuthority(
            type=MetadataAuthorityType.FORGE,
            url=REPO_BASE_URL,
        )

        expected_metadata = [
            RawExtrinsicMetadata(
                target=directory_swhid,
                authority=metadata_authority,
                fetcher=MetadataFetcher(
                    name="swh.loader.package.maven.loader.MavenLoader",
                    version=__version__,
                ),
                discovery_date=loader.visit_date,
                format="maven-pom",
                metadata=expected_pom_metadata[i],
                origin=MVN_ORIGIN_URL,
                release=release_swhid,
            ),
            RawExtrinsicMetadata(
                target=directory_swhid,
                authority=metadata_authority,
                fetcher=MetadataFetcher(
                    name="swh.loader.package.maven.loader.MavenLoader",
                    version=__version__,
                ),
                discovery_date=loader.visit_date,
                format="maven-json",
                metadata=json.dumps(expected_json_metadata[i]).encode(),
                origin=MVN_ORIGIN_URL,
                release=release_swhid,
            ),
        ]

        res = swh_storage.raw_extrinsic_metadata_get(
            directory_swhid, metadata_authority
        )
        assert res.next_page_token is None
        assert set(res.results) == set(expected_metadata)


def test_maven_loader_extrinsic_metadata_no_pom(
    swh_storage, requests_mock, expected_releases, expected_json_metadata
):
    """With no prior visit, loading a jar ends up with 1 snapshot.
    Extrinsic metadata is None if the pom file cannot be retrieved.
    """

    requests_mock.get(MVN_ARTIFACTS_POM[0], status_code="404")
    loader = MavenLoader(swh_storage, MVN_ORIGIN_URL, artifacts=MVN_ARTIFACTS)

    actual_load_status = loader.load()
    assert actual_load_status["status"] == "eventful"

    expected_release_id = expected_releases[0].id
    release = swh_storage.release_get([expected_release_id])[0]
    assert release is not None

    release_swhid = CoreSWHID(
        object_type=ObjectType.RELEASE, object_id=expected_release_id
    )
    directory_swhid = ExtendedSWHID(
        object_type=ExtendedObjectType.DIRECTORY, object_id=release.target
    )
    metadata_authority = MetadataAuthority(
        type=MetadataAuthorityType.FORGE,
        url=REPO_BASE_URL,
    )

    expected_metadata = [
        RawExtrinsicMetadata(
            target=directory_swhid,
            authority=metadata_authority,
            fetcher=MetadataFetcher(
                name="swh.loader.package.maven.loader.MavenLoader",
                version=__version__,
            ),
            discovery_date=loader.visit_date,
            format="maven-pom",
            metadata=b"",
            origin=MVN_ORIGIN_URL,
            release=release_swhid,
        ),
        RawExtrinsicMetadata(
            target=directory_swhid,
            authority=metadata_authority,
            fetcher=MetadataFetcher(
                name="swh.loader.package.maven.loader.MavenLoader",
                version=__version__,
            ),
            discovery_date=loader.visit_date,
            format="maven-json",
            metadata=json.dumps(expected_json_metadata[0]).encode(),
            origin=MVN_ORIGIN_URL,
            release=release_swhid,
        ),
    ]
    res = swh_storage.raw_extrinsic_metadata_get(directory_swhid, metadata_authority)
    assert res.next_page_token is None
    assert set(res.results) == set(expected_metadata)


def test_maven_loader_jar_extid():
    """Compute primary key should return the right identity"""
    metadata = MVN_ARTIFACTS[0]
    p_info = MavenPackageInfo(**metadata)

    expected_manifest = "{gid} {aid} {version} {url} {time}".format(**metadata).encode()
    actual_id = p_info.extid()
    assert actual_id == (
        "maven-jar",
        0,
        hashlib.sha256(expected_manifest).digest(),
    )
