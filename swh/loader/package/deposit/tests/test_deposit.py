# Copyright (C) 2019-2021  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import json
import re
from typing import List

import pytest

from swh.core.pytest_plugin import requests_mock_datadir_factory
from swh.loader.package.deposit.loader import ApiClient, DepositLoader
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
    Revision,
    RevisionType,
    Snapshot,
    SnapshotBranch,
    TargetType,
    Timestamp,
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

    assert loader.url == url
    assert loader.client is not None
    assert loader.client.base_url == swh_loader_config["deposit"]["url"]


def test_deposit_from_configfile(swh_config):
    """Ensure the deposit instantiation is ok

    """
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
    ignore_urls=[f"{DEPOSIT_URL}/666/raw/",]
)


def test_deposit_loading_failure_to_retrieve_1_artifact(
    swh_storage, deposit_client, requests_mock_datadir_missing_one
):
    """Deposit with missing artifact ends up with an uneventful/partial visit

    """
    # private api url form: 'https://deposit.s.o/1/private/hal/666/raw/'
    url = "some-url-2"
    deposit_id = 666
    requests_mock_datadir_missing_one.put(re.compile("https"))
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
                "Failed to load branch HEAD for some-url-2: Fail to query "
                "'https://deposit.softwareheritage.org/1/private/666/raw/'. Reason: 404"
            ]
        },
    }

    assert body == expected_body


def test_deposit_loading_ok(swh_storage, deposit_client, requests_mock_datadir):
    url = "https://hal-test.archives-ouvertes.fr/some-external-id"
    deposit_id = 666
    loader = DepositLoader(
        swh_storage, url, deposit_id, deposit_client, default_filename="archive.zip"
    )

    actual_load_status = loader.load()
    expected_snapshot_id = "b2b327b33dc85818bd23c3ccda8b7e675a66ecbd"
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

    revision_id_hex = "637318680351f5d78856d13264faebbd91efe9bb"
    revision_id = hash_to_bytes(revision_id_hex)

    expected_snapshot = Snapshot(
        id=hash_to_bytes(expected_snapshot_id),
        branches={
            b"HEAD": SnapshotBranch(
                target=revision_id, target_type=TargetType.REVISION,
            ),
        },
    )
    check_snapshot(expected_snapshot, storage=loader.storage)

    revision = loader.storage.revision_get([revision_id])[0]
    date = TimestampWithTimezone(
        timestamp=Timestamp(seconds=1507389428, microseconds=0),
        offset=0,
        negative_utc=False,
    )
    person = Person(
        fullname=b"Software Heritage",
        name=b"Software Heritage",
        email=b"robot@softwareheritage.org",
    )
    assert revision == Revision(
        id=revision_id,
        message=b"hal: Deposit 666 in collection hal",
        author=person,
        committer=person,
        date=date,
        committer_date=date,
        type=RevisionType.TAR,
        directory=b"\xfd-\xf1-\xc5SL\x1d\xa1\xe9\x18\x0b\x91Q\x02\xfbo`\x1d\x19",
        synthetic=True,
        metadata=None,
        parents=(),
        extra_headers=(),
    )

    # check metadata

    fetcher = MetadataFetcher(name="swh-deposit", version="0.0.1",)

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
    all_metadata_raw: List[str] = raw_meta["metadata_raw"]
    # 2 raw metadata xml + 1 json dict
    assert len(orig_meta.results) == len(all_metadata_raw) + 1
    orig_meta0 = orig_meta.results[0]
    assert orig_meta0.authority == authority
    assert orig_meta0.fetcher == fetcher

    # Check directory metadata
    directory_swhid = CoreSWHID(
        object_type=ObjectType.DIRECTORY, object_id=revision.directory
    )
    actual_dir_meta = loader.storage.raw_extrinsic_metadata_get(
        directory_swhid, authority
    )
    assert actual_dir_meta.next_page_token is None
    assert len(actual_dir_meta.results) == len(all_metadata_raw)
    for dir_meta in actual_dir_meta.results:
        assert dir_meta.authority == authority
        assert dir_meta.fetcher == fetcher
        assert dir_meta.metadata.decode() in all_metadata_raw

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
        "revision_id": revision_id_hex,
        "directory_id": hash_to_hex(revision.directory),
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
        "release": 0,
        "revision": 1,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats


def test_deposit_loading_ok_2(swh_storage, deposit_client, requests_mock_datadir):
    """Field dates should be se appropriately

    """
    external_id = "some-external-id"
    url = f"https://hal-test.archives-ouvertes.fr/{external_id}"
    deposit_id = 777
    loader = DepositLoader(
        swh_storage, url, deposit_id, deposit_client, default_filename="archive.zip"
    )

    actual_load_status = loader.load()
    expected_snapshot_id = "3e68440fdd7c81d283f8f3aebb6f0c8657864192"

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

    revision_id = "564d18943d71be80d0d73b43a77cfb205bcde96c"
    expected_snapshot = Snapshot(
        id=hash_to_bytes(expected_snapshot_id),
        branches={
            b"HEAD": SnapshotBranch(
                target=hash_to_bytes(revision_id), target_type=TargetType.REVISION
            )
        },
    )

    check_snapshot(expected_snapshot, storage=loader.storage)

    raw_meta = loader.client.metadata_get(deposit_id)
    # Ensure the date fields are set appropriately in the revision

    # Retrieve the revision
    revision = loader.storage.revision_get([hash_to_bytes(revision_id)])[0]
    assert revision
    assert revision.date.to_dict() == raw_meta["deposit"]["author_date"]
    assert revision.committer_date.to_dict() == raw_meta["deposit"]["committer_date"]
    assert not revision.metadata

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

    fetcher = MetadataFetcher(name="swh-deposit", version="0.0.1",)

    authority = MetadataAuthority(
        type=MetadataAuthorityType.DEPOSIT_CLIENT,
        url="https://hal-test.archives-ouvertes.fr/",
    )

    # Check the origin metadata swh side
    origin_extrinsic_metadata = loader.storage.raw_extrinsic_metadata_get(
        Origin(url).swhid(), authority
    )
    assert origin_extrinsic_metadata.next_page_token is None
    all_metadata_raw: List[str] = raw_meta["metadata_raw"]
    # 1 raw metadata xml + 1 json dict
    assert len(origin_extrinsic_metadata.results) == len(all_metadata_raw) + 1

    origin_swhid = Origin(url).swhid()

    expected_metadata = []
    for idx, raw_meta in enumerate(all_metadata_raw):
        origin_meta = origin_extrinsic_metadata.results[idx]
        expected_metadata.append(
            RawExtrinsicMetadata(
                target=origin_swhid,
                discovery_date=origin_meta.discovery_date,
                metadata=raw_meta.encode(),
                format="sword-v2-atom-codemeta-v2",
                authority=authority,
                fetcher=fetcher,
            )
        )

    origin_metadata = {
        "metadata": all_metadata_raw,
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

    # Check the revision metadata swh side
    directory_swhid = ExtendedSWHID(
        object_type=ExtendedObjectType.DIRECTORY, object_id=revision.directory
    )
    actual_directory_metadata = loader.storage.raw_extrinsic_metadata_get(
        directory_swhid, authority
    )

    assert actual_directory_metadata.next_page_token is None
    assert len(actual_directory_metadata.results) == len(all_metadata_raw)

    revision_swhid = CoreSWHID(
        object_type=ObjectType.REVISION, object_id=hash_to_bytes(revision_id)
    )
    dir_metadata_template = RawExtrinsicMetadata(
        target=directory_swhid,
        format="sword-v2-atom-codemeta-v2",
        authority=authority,
        fetcher=fetcher,
        origin=url,
        revision=revision_swhid,
        # to satisfy the constructor
        discovery_date=now(),
        metadata=b"",
    )

    expected_directory_metadata = []
    for idx, raw_meta in enumerate(all_metadata_raw):
        dir_metadata = actual_directory_metadata.results[idx]
        expected_directory_metadata.append(
            RawExtrinsicMetadata.from_dict(
                {
                    **{
                        k: v
                        for (k, v) in dir_metadata_template.to_dict().items()
                        if k != "id"
                    },
                    "discovery_date": dir_metadata.discovery_date,
                    "metadata": raw_meta.encode(),
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
        "revision_id": revision_id,
        "directory_id": hash_to_hex(revision.directory),
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
    loader = DepositLoader(swh_storage, url, deposit_id, deposit_client)

    actual_load_status = loader.load()
    expected_snapshot_id = "0ac7b54c042a026389f2087dc16f1d5c644ed0e4"

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
