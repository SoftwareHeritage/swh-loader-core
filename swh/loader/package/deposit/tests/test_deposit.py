# Copyright (C) 2019-2024 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import datetime
import json
import re

import pytest

from swh.core.pytest_plugin import requests_mock_datadir_factory
from swh.loader.package.deposit.loader import (
    ApiClient,
    DepositLoader,
    build_branch_name,
)
from swh.loader.package.loader import now
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.hashutil import hash_to_bytes, hash_to_hex
from swh.model.model import (
    MetadataAuthority,
    MetadataAuthorityType,
    MetadataFetcher,
    Origin,
    Person,
    RawExtrinsicMetadata,
    Release,
    ReleaseTargetType,
    Snapshot,
    SnapshotBranch,
    SnapshotTargetType,
    TimestampWithTimezone,
)
from swh.model.swhids import CoreSWHID, ExtendedObjectType, ExtendedSWHID, ObjectType

DEPOSIT_URL = "https://deposit.softwareheritage.org/1/private"


@pytest.fixture
def requests_mock_datadir(requests_mock_datadir):
    """Enhance default mock data to mock put requests as the loader does some
    internal update queries there.

    """
    requests_mock_datadir.put(re.compile("https"))
    return requests_mock_datadir


def test_deposit_init_ok(swh_storage, deposit_client, swh_loader_config):
    url = "some-url"
    deposit_id = 999
    loader = DepositLoader(
        swh_storage, url, deposit_id, deposit_client, default_filename="archive.zip"
    )  # Something that does not exist

    assert loader.origin.url == url
    assert loader.client is not None
    assert loader.client.base_url == swh_loader_config["deposit"]["url"]


def test_deposit_from_configfile(swh_config):
    """Ensure the deposit instantiation is ok"""
    loader = DepositLoader.from_configfile(
        url="some-url", deposit_id="666", default_filename="archive.zip"
    )

    assert isinstance(loader.client, ApiClient)


def test_deposit_loading_unknown_deposit(
    swh_storage, deposit_client, requests_mock_datadir
):
    """Loading an unknown deposit should fail

    no origin, no visit, no snapshot
    """
    # private api url form: 'https://deposit.s.o/1/private/hal/666/raw/'
    url = "some-url"
    unknown_deposit_id = 667
    loader = DepositLoader(
        swh_storage,
        url,
        unknown_deposit_id,
        deposit_client,
        default_filename="archive.zip",
    )  # does not exist

    actual_load_status = loader.load()
    assert actual_load_status == {"status": "failed"}

    stats = get_stats(loader.storage)

    assert {
        "content": 0,
        "directory": 0,
        "origin": 0,
        "origin_visit": 0,
        "release": 0,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 0,
    } == stats


requests_mock_datadir_missing_one = requests_mock_datadir_factory(
    ignore_urls=[
        f"{DEPOSIT_URL}/666/raw/",
    ]
)


def test_deposit_loading_failure_to_retrieve_1_artifact(
    swh_storage, deposit_client, requests_mock_datadir_missing_one, requests_mock
):
    """Deposit with missing artifact ends up with an uneventful/partial visit"""
    # private api url form: 'https://deposit.s.o/1/private/hal/666/raw/'
    url = "some-url-2"
    deposit_id = 666
    requests_mock_datadir_missing_one.put(re.compile("https"))
    releases = [{"id": deposit_id, "software_version": "1", "origin_url": url}]

    requests_mock_datadir_missing_one.get(
        f"{DEPOSIT_URL}/{deposit_id}/releases/", json=releases
    )
    loader = DepositLoader(
        swh_storage, url, deposit_id, deposit_client, default_filename="archive.zip"
    )

    actual_load_status = loader.load()
    assert actual_load_status["status"] == "uneventful"
    assert actual_load_status["snapshot_id"] is not None

    assert_last_visit_matches(loader.storage, url, status="partial", type="deposit")

    stats = get_stats(loader.storage)
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

    # Retrieve the information for deposit status update query to the deposit
    urls = [
        m
        for m in requests_mock_datadir_missing_one.request_history
        if m.url == f"{DEPOSIT_URL}/{deposit_id}/update/"
    ]

    assert len(urls) == 1
    update_query = urls[0]

    body = update_query.json()
    expected_body = {
        "status": "failed",
        "status_detail": {
            "loading": [
                "Failed to load branch deposit/1 for some-url-2: 404 Client Error: None "
                "for url: https://deposit.softwareheritage.org/1/private/666/raw/"
            ]
        },
    }

    assert body == expected_body


def test_deposit_loading_ok(swh_storage, deposit_client, requests_mock_datadir):
    url = "https://hal-test.archives-ouvertes.fr/some-external-id"
    deposit_id = 666
    releases = [{"id": deposit_id, "software_version": "1", "origin_url": url}]
    requests_mock_datadir.get(f"{DEPOSIT_URL}/{deposit_id}/releases/", json=releases)
    loader = DepositLoader(
        swh_storage, url, deposit_id, deposit_client, default_filename="archive.zip"
    )

    actual_load_status = loader.load()
    expected_snapshot_id = "28d6c5f69c4022a359203de8e2e81bda103b148e"
    assert actual_load_status == {
        "status": "eventful",
        "snapshot_id": expected_snapshot_id,
    }

    assert_last_visit_matches(
        loader.storage,
        url,
        status="full",
        type="deposit",
        snapshot=hash_to_bytes(expected_snapshot_id),
    )

    release_id_1_hex = "c98c19f43ef10a4262345d8e85ca283cea99c7b3"
    release_id_1 = hash_to_bytes(release_id_1_hex)

    expected_snapshot = Snapshot(
        id=hash_to_bytes(expected_snapshot_id),
        branches={
            b"HEAD": SnapshotBranch(
                target=b"deposit/1",
                target_type=SnapshotTargetType.ALIAS,
            ),
            b"deposit/1": SnapshotBranch(
                target=release_id_1,
                target_type=SnapshotTargetType.RELEASE,
            ),
        },
    )

    check_snapshot(expected_snapshot, storage=loader.storage)

    release = loader.storage.release_get([release_id_1])[0]

    date = TimestampWithTimezone.from_datetime(
        datetime.datetime(2017, 10, 7, 15, 17, 8, tzinfo=datetime.timezone.utc)
    )
    person = Person(
        fullname=b"Software Heritage",
        name=b"Software Heritage",
        email=b"robot@softwareheritage.org",
    )

    assert release == Release(
        id=release_id_1,
        name=b"1",
        message=b"hal: Deposit 666 in collection hal\n",
        author=person,
        date=date,
        target_type=ReleaseTargetType.DIRECTORY,
        target=b"\xfd-\xf1-\xc5SL\x1d\xa1\xe9\x18\x0b\x91Q\x02\xfbo`\x1d\x19",
        synthetic=True,
        metadata=None,
    )

    # check metadata

    fetcher = MetadataFetcher(
        name="swh-deposit",
        version="0.0.1",
    )

    authority = MetadataAuthority(
        type=MetadataAuthorityType.DEPOSIT_CLIENT,
        url="https://hal-test.archives-ouvertes.fr/",
    )

    # Check origin metadata
    orig_meta = loader.storage.raw_extrinsic_metadata_get(
        Origin(url).swhid(), authority
    )
    assert orig_meta.next_page_token is None
    raw_meta = loader.client.metadata_get(deposit_id)
    raw_metadata: str = raw_meta["raw_metadata"]
    # 2 raw metadata xml + 1 json dict
    assert len(orig_meta.results) == 2
    orig_meta0 = orig_meta.results[0]
    assert orig_meta0.authority == authority
    assert orig_meta0.fetcher == fetcher

    # Check directory metadata
    assert release.target_type == ReleaseTargetType.DIRECTORY
    directory_swhid = CoreSWHID(
        object_type=ObjectType.DIRECTORY, object_id=release.target
    )
    actual_dir_meta = loader.storage.raw_extrinsic_metadata_get(
        directory_swhid, authority
    )
    assert actual_dir_meta.next_page_token is None
    assert len(actual_dir_meta.results) == 1
    dir_meta = actual_dir_meta.results[0]
    assert dir_meta.authority == authority
    assert dir_meta.fetcher == fetcher
    assert dir_meta.metadata.decode() == raw_metadata

    # Retrieve the information for deposit status update query to the deposit
    urls = [
        m
        for m in requests_mock_datadir.request_history
        if m.url == f"{DEPOSIT_URL}/{deposit_id}/update/"
    ]

    assert len(urls) == 1
    update_query = urls[0]

    body = update_query.json()
    expected_body = {
        "status": "done",
        "release_id": release_id_1_hex,
        "directory_id": hash_to_hex(release.target),
        "snapshot_id": expected_snapshot_id,
        "origin_url": url,
    }

    assert body == expected_body

    stats = get_stats(loader.storage)
    assert {
        "content": 303,
        "directory": 12,
        "origin": 1,
        "origin_visit": 1,
        "release": 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats


def test_deposit_loading_ok_2(swh_storage, deposit_client, requests_mock_datadir):
    """Field dates should be se appropriately"""
    external_id = "some-external-id"
    url = f"https://hal-test.archives-ouvertes.fr/{external_id}"
    deposit_id = 777

    releases = [{"id": deposit_id, "software_version": "1", "origin_url": url}]
    requests_mock_datadir.get(f"{DEPOSIT_URL}/{deposit_id}/releases/", json=releases)

    loader = DepositLoader(
        swh_storage, url, deposit_id, deposit_client, default_filename="archive.zip"
    )

    actual_load_status = loader.load()
    expected_snapshot_id = "ee5789e4f8f5ebde20b1b9e6a7338781d4f65c9b"

    assert actual_load_status == {
        "status": "eventful",
        "snapshot_id": expected_snapshot_id,
    }
    assert_last_visit_matches(
        loader.storage,
        url,
        status="full",
        type="deposit",
        snapshot=hash_to_bytes(expected_snapshot_id),
    )

    release_id_head_hex = "6465706f7369742f31"
    release_id_head = hash_to_bytes(release_id_head_hex)

    release_id_1_hex = "3b7f58c924063e1dc4976e8fb8e5503592fddedd"
    release_id_1 = hash_to_bytes(release_id_1_hex)

    expected_snapshot = Snapshot(
        id=hash_to_bytes(expected_snapshot_id),
        branches={
            b"HEAD": SnapshotBranch(
                target=release_id_head,
                target_type=SnapshotTargetType.ALIAS,
            ),
            b"deposit/1": SnapshotBranch(
                target=release_id_1,
                target_type=SnapshotTargetType.RELEASE,
            ),
        },
    )

    check_snapshot(expected_snapshot, storage=loader.storage)

    raw_meta = loader.client.metadata_get(deposit_id)
    # Ensure the date fields are set appropriately in the release

    # Retrieve the release
    release = loader.storage.release_get([hash_to_bytes(release_id_1)])[0]
    assert release
    # swh-deposit uses the numeric 'offset_minutes' instead of the bytes offset
    # attribute, because its dates are always well-formed, and it can only send
    # JSON-serializable data.
    release_date_dict = {
        "timestamp": release.date.timestamp.to_dict(),
        "offset": release.date.offset_minutes(),
    }

    assert release_date_dict == raw_meta["deposit"]["author_date"]

    assert not release.metadata

    provider = {
        "provider_name": "hal",
        "provider_type": "deposit_client",
        "provider_url": "https://hal-test.archives-ouvertes.fr/",
        "metadata": None,
    }
    tool = {
        "name": "swh-deposit",
        "version": "0.0.1",
        "configuration": {"sword_version": "2"},
    }

    fetcher = MetadataFetcher(
        name="swh-deposit",
        version="0.0.1",
    )

    authority = MetadataAuthority(
        type=MetadataAuthorityType.DEPOSIT_CLIENT,
        url="https://hal-test.archives-ouvertes.fr/",
    )

    # Check the origin metadata swh side
    origin_extrinsic_metadata = loader.storage.raw_extrinsic_metadata_get(
        Origin(url).swhid(), authority
    )
    assert origin_extrinsic_metadata.next_page_token is None
    raw_metadata: str = raw_meta["raw_metadata"]
    # 1 raw metadata xml + 1 json dict
    assert len(origin_extrinsic_metadata.results) == 2

    origin_swhid = Origin(url).swhid()

    expected_metadata = []
    origin_meta = origin_extrinsic_metadata.results[0]
    expected_metadata.append(
        RawExtrinsicMetadata(
            target=origin_swhid,
            discovery_date=origin_meta.discovery_date,
            metadata=raw_metadata.encode(),
            format="sword-v2-atom-codemeta-v2",
            authority=authority,
            fetcher=fetcher,
        )
    )

    origin_metadata = {
        "metadata": [raw_metadata],
        "provider": provider,
        "tool": tool,
    }
    expected_metadata.append(
        RawExtrinsicMetadata(
            target=origin_swhid,
            discovery_date=origin_extrinsic_metadata.results[-1].discovery_date,
            metadata=json.dumps(origin_metadata).encode(),
            format="original-artifacts-json",
            authority=authority,
            fetcher=fetcher,
        )
    )

    assert sorted(origin_extrinsic_metadata.results) == sorted(expected_metadata)

    # Check the release metadata swh side
    assert release.target_type == ReleaseTargetType.DIRECTORY
    directory_swhid = ExtendedSWHID(
        object_type=ExtendedObjectType.DIRECTORY, object_id=release.target
    )
    actual_directory_metadata = loader.storage.raw_extrinsic_metadata_get(
        directory_swhid, authority
    )

    assert actual_directory_metadata.next_page_token is None
    assert len(actual_directory_metadata.results) == 1

    release_swhid = CoreSWHID(
        object_type=ObjectType.RELEASE, object_id=hash_to_bytes(release_id_1)
    )
    dir_metadata_template = RawExtrinsicMetadata(
        target=directory_swhid,
        format="sword-v2-atom-codemeta-v2",
        authority=authority,
        fetcher=fetcher,
        origin=url,
        release=release_swhid,
        # to satisfy the constructor
        discovery_date=now(),
        metadata=b"",
    )

    expected_directory_metadata = []
    dir_metadata = actual_directory_metadata.results[0]
    expected_directory_metadata.append(
        RawExtrinsicMetadata.from_dict(
            {
                **{
                    k: v
                    for (k, v) in dir_metadata_template.to_dict().items()
                    if k != "id"
                },
                "discovery_date": dir_metadata.discovery_date,
                "metadata": raw_metadata.encode(),
            }
        )
    )

    assert sorted(actual_directory_metadata.results) == sorted(
        expected_directory_metadata
    )

    # Retrieve the information for deposit status update query to the deposit
    urls = [
        m
        for m in requests_mock_datadir.request_history
        if m.url == f"{DEPOSIT_URL}/{deposit_id}/update/"
    ]

    assert len(urls) == 1
    update_query = urls[0]

    body = update_query.json()
    expected_body = {
        "status": "done",
        "release_id": release_id_1_hex,
        "directory_id": hash_to_hex(release.target),
        "snapshot_id": expected_snapshot_id,
        "origin_url": url,
    }

    assert body == expected_body


def test_deposit_loading_ok_3(swh_storage, deposit_client, requests_mock_datadir):
    """Deposit loading can happen on tarball artifacts as well

    The latest deposit changes introduce the internal change.

    """
    external_id = "hal-123456"
    url = f"https://hal-test.archives-ouvertes.fr/{external_id}"
    deposit_id = 888

    releases = [{"id": deposit_id, "software_version": "1", "origin_url": url}]
    requests_mock_datadir.get(f"{DEPOSIT_URL}/{deposit_id}/releases/", json=releases)

    loader = DepositLoader(swh_storage, url, deposit_id, deposit_client)

    actual_load_status = loader.load()
    expected_snapshot_id = "2f95506d6194e6c4e71ba87e3b118c65a767fe9d"

    assert actual_load_status == {
        "status": "eventful",
        "snapshot_id": expected_snapshot_id,
    }
    assert_last_visit_matches(
        loader.storage,
        url,
        status="full",
        type="deposit",
        snapshot=hash_to_bytes(expected_snapshot_id),
    )


def test_deposit_loading_ok_release_notes(
    swh_storage, deposit_client, requests_mock_datadir
):
    url = "https://hal-test.archives-ouvertes.fr/some-external-id"
    deposit_id = 999
    releases = [{"id": deposit_id, "software_version": "1", "origin_url": url}]
    requests_mock_datadir.get(f"{DEPOSIT_URL}/{deposit_id}/releases/", json=releases)

    loader = DepositLoader(
        swh_storage, url, deposit_id, deposit_client, default_filename="archive.zip"
    )

    actual_load_status = loader.load()
    expected_snapshot_id = "41cd91cb190ffa82fee8ec5d91dedc5d57fb3b1f"
    assert actual_load_status == {
        "status": "eventful",
        "snapshot_id": expected_snapshot_id,
    }

    assert_last_visit_matches(
        loader.storage,
        url,
        status="full",
        type="deposit",
        snapshot=hash_to_bytes(expected_snapshot_id),
    )

    release_id_1_hex = "a7cae4b6aaaf70f30178d86496aefb7dead0eb77"
    release_id_1 = hash_to_bytes(release_id_1_hex)

    expected_snapshot = Snapshot(
        id=hash_to_bytes(expected_snapshot_id),
        branches={
            b"HEAD": SnapshotBranch(
                target=b"deposit/1",
                target_type=SnapshotTargetType.ALIAS,
            ),
            b"deposit/1": SnapshotBranch(
                target=release_id_1,
                target_type=SnapshotTargetType.RELEASE,
            ),
        },
    )

    check_snapshot(expected_snapshot, storage=loader.storage)

    release = loader.storage.release_get([release_id_1])[0]
    date = TimestampWithTimezone.from_datetime(
        datetime.datetime(2017, 10, 7, 15, 17, 8, tzinfo=datetime.timezone.utc)
    )
    person = Person(
        fullname=b"Software Heritage",
        name=b"Software Heritage",
        email=b"robot@softwareheritage.org",
    )
    assert release == Release(
        id=release_id_1,
        name=b"1",
        message=(
            b"hal: Deposit 999 in collection hal\n\nThis release adds this and that.\n"
        ),
        author=person,
        date=date,
        target_type=ReleaseTargetType.DIRECTORY,
        target=b"\xfd-\xf1-\xc5SL\x1d\xa1\xe9\x18\x0b\x91Q\x02\xfbo`\x1d\x19",
        synthetic=True,
        metadata=None,
    )


def test_deposit_get_versions(swh_storage, deposit_client, requests_mock_datadir):
    external_id = "hal-123456"
    url = f"https://hal-test.archives-ouvertes.fr/{external_id}"
    deposit_id = 888

    releases = [
        {"id": deposit_id, "software_version": "version 1", "origin_url": url},
        {"id": deposit_id, "software_version": "version 2", "origin_url": url},
    ]
    requests_mock_datadir.get(f"{DEPOSIT_URL}/{deposit_id}/releases/", json=releases)

    loader = DepositLoader(swh_storage, url, deposit_id, deposit_client)

    loader.load()
    assert loader.get_versions() == ["version 1", "version 2"]
    assert loader.get_default_version() == "version 2"


def test_deposit_deduplicate_branch_names(
    swh_storage, deposit_client, requests_mock_datadir
):
    external_id = "hal-123456"
    url = f"https://hal-test.archives-ouvertes.fr/{external_id}"
    deposit_id = 888

    releases = [
        {"id": deposit_id, "software_version": "ABC", "origin_url": url},
        {"id": deposit_id, "software_version": "abc", "origin_url": url},
        {"id": deposit_id, "software_version": "a$B$c$", "origin_url": url},
    ]
    requests_mock_datadir.get(f"{DEPOSIT_URL}/{deposit_id}/releases/", json=releases)

    loader = DepositLoader(swh_storage, url, deposit_id, deposit_client)

    status = loader.load()
    # unique branches names for each versions
    snapshot = loader.storage.snapshot_get(hash_to_bytes(status["snapshot_id"]))
    assert len(snapshot["branches"]) == 4
    assert snapshot["branches"][b"deposit/abc"]
    assert snapshot["branches"][b"deposit/abc/1"]
    assert snapshot["branches"][b"deposit/abc/2"]
    assert snapshot["branches"][b"HEAD"]["target"] == b"deposit/abc/2"

    # the deposit will be updated with the right release_id
    release = loader.storage.release_get(
        [snapshot["branches"][b"deposit/abc/2"]["target"]]
    )[0]

    urls = [
        m
        for m in requests_mock_datadir.request_history
        if m.url == f"{DEPOSIT_URL}/{deposit_id}/update/"
    ]
    assert len(urls) == 1
    update_query = urls[0]

    assert update_query.json()["release_id"] == hash_to_hex(release.id)


@pytest.mark.parametrize(
    "version,expected",
    [
        ("0", "deposit/0"),
        ("Weird version Number", "deposit/weird-version-number"),
        ("trailing-", "deposit/trailing"),
        ("1.2.3", "deposit/1.2.3"),
    ],
)
def test_build_branch_name(version, expected):
    assert build_branch_name(version) == expected


@pytest.mark.parametrize(
    "version,expected",
    [
        ("0", "deposit/0"),
        ("Weird version Number", "deposit/weird-version-number"),
        ("trailing-", "deposit/trailing"),
        ("1.2.3", "deposit/1.2.3"),
    ],
)
def test_generate_branch_name(swh_storage, deposit_client, version, expected):
    loader = DepositLoader(swh_storage, "test", 1, deposit_client)
    assert loader.generate_branch_name(version) == expected


def test_generate_branch_name_uniqueness(swh_storage, deposit_client):
    loader = DepositLoader(swh_storage, "test", 1, deposit_client)
    assert loader.generate_branch_name("A") == "deposit/a"
    assert loader.generate_branch_name("a") == "deposit/a/1"
    assert loader.generate_branch_name("a$") == "deposit/a/2"
