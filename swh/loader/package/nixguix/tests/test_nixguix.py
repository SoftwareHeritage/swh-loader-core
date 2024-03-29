# Copyright (C) 2020-2021 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import json
import logging
import os
from typing import Dict, Optional, Tuple

import pytest

from swh.loader.package import __version__
from swh.loader.package.archive.loader import ArchiveLoader
from swh.loader.package.nixguix.loader import (
    NixGuixLoader,
    clean_sources,
    make_pattern_unsupported_file_extension,
    parse_sources,
    retrieve_sources,
)
from swh.loader.package.utils import download
from swh.loader.tests import assert_last_visit_matches
from swh.loader.tests import check_snapshot as check_snapshot_full
from swh.loader.tests import get_stats
from swh.model.hashutil import hash_to_bytes
from swh.model.model import (
    MetadataAuthority,
    MetadataAuthorityType,
    MetadataFetcher,
    ObjectType,
    Person,
    RawExtrinsicMetadata,
    Release,
    Snapshot,
    SnapshotBranch,
    TargetType,
)
from swh.model.swhids import ExtendedObjectType, ExtendedSWHID
from swh.storage.algos.origin import origin_get_latest_visit_status
from swh.storage.algos.snapshot import snapshot_get_all_branches
from swh.storage.exc import HashCollision
from swh.storage.interface import PagedResult, StorageInterface

sources_url = "https://nix-community.github.io/nixpkgs-swh/sources.json"


@pytest.fixture
def raw_sources(datadir) -> bytes:
    with open(
        os.path.join(
            datadir, "https_nix-community.github.io", "nixpkgs-swh_sources.json"
        ),
        "rb",
    ) as f:
        return f.read()


SNAPSHOT1 = Snapshot(
    id=hash_to_bytes("fafcfe32016d018bd892114fce211f37a36a092a"),
    branches={
        b"evaluation": SnapshotBranch(
            target=hash_to_bytes("cc4e04c26672dd74e5fd0fecb78b435fb55368f7"),
            target_type=TargetType.REVISION,
        ),
        b"https://github.com/owner-1/repository-1/revision-1.tgz": SnapshotBranch(
            target=hash_to_bytes("df7811b9644ed8ef088e2e7add62ed32b0bab15f"),
            target_type=TargetType.RELEASE,
        ),
        b"https://github.com/owner-3/repository-1/revision-1.tgz": SnapshotBranch(
            target=hash_to_bytes("dc7dc10a664396d5c88adc56352904db231bde14"),
            target_type=TargetType.RELEASE,
        ),
    },
)


def check_snapshot(snapshot: Snapshot, storage: StorageInterface):
    # The `evaluation` branch is allowed to be unresolvable. It's possible at current
    # nixguix visit time, it is not yet visited (the git loader is in charge of its
    # visit for now). For more details, check the
    # swh.loader.package.nixguix.NixGuixLoader.extra_branches docstring.
    check_snapshot_full(
        snapshot, storage, allowed_empty=[(TargetType.REVISION, b"evaluation")]
    )

    assert isinstance(snapshot, Snapshot)
    # then ensure the snapshot revisions are structurally as expected
    revision_ids = []
    for name, branch in snapshot.branches.items():
        if name == b"evaluation":
            continue  # skipping that particular branch (cf. previous comment)
        if branch.target_type == TargetType.REVISION:
            revision_ids.append(branch.target)

    revisions = storage.revision_get(revision_ids)
    for rev in revisions:
        assert rev is not None
        metadata = rev.metadata
        assert not metadata


def test_retrieve_sources(swh_storage, requests_mock_datadir):
    j = parse_sources(retrieve_sources(sources_url))
    assert "sources" in j.keys()
    assert len(j["sources"]) == 3


def test_nixguix_url_not_found(swh_storage, requests_mock_datadir):
    """When failing to read from the url, the visit is marked as not_found.

    Here the sources url does not exist, so requests_mock_datadir returns a 404.
    Resulting in a NotFound raised within the package loader's main loop.

    This results in the task with status failed and a visit_status with status
    "not_found".

    """
    unknown_url = "https://non-existing-url/"
    loader = NixGuixLoader(swh_storage, unknown_url)
    # during the retrieval step
    load_status = loader.load()

    assert load_status == {"status": "failed"}

    assert_last_visit_matches(
        swh_storage, unknown_url, status="not_found", type="nixguix", snapshot=None
    )

    assert len(requests_mock_datadir.request_history) == 1
    assert requests_mock_datadir.request_history[0].url == unknown_url


def test_nixguix_url_with_decoding_error(swh_storage, requests_mock_datadir):
    """Other errors during communication with the url, the visit is marked as failed

    requests_mock_datadir will intercept the requests to sources_url. Since the file
    exists, returns a 200 with the requested content of the query. As file.txt is no
    json, fails do decode and raises a JSONDecodeError. In effect failing the visit.

    """
    sources_url = "https://example.com/file.txt"
    loader = NixGuixLoader(swh_storage, sources_url)
    load_status = loader.load()

    assert load_status == {"status": "failed"}

    assert_last_visit_matches(
        swh_storage, sources_url, status="failed", type="nixguix", snapshot=None
    )

    assert len(requests_mock_datadir.request_history) == 1
    assert requests_mock_datadir.request_history[0].url == sources_url


def test_clean_sources_invalid_schema(swh_storage, requests_mock_datadir):
    sources = {}
    with pytest.raises(ValueError, match="sources structure invalid, missing: .*"):
        clean_sources(sources)


def test_clean_sources_invalid_version(swh_storage, requests_mock_datadir):
    for version_ok in [1, "1"]:  # Check those versions are fine
        clean_sources({"version": version_ok, "sources": [], "revision": "my-revision"})

    for version_ko in [0, "0", 2, "2"]:  # Check version != 1 raise an error
        with pytest.raises(
            ValueError, match="sources structure version .* is not supported"
        ):
            clean_sources(
                {"version": version_ko, "sources": [], "revision": "my-revision"}
            )


def test_clean_sources_invalid_sources(swh_storage, requests_mock_datadir):
    valid_sources = [
        # 1 valid source
        {"type": "url", "urls": ["my-url.tar.gz"], "integrity": "my-integrity"},
    ]
    sources = {
        "version": 1,
        "sources": valid_sources
        + [
            # integrity is missing
            {
                "type": "url",
                "urls": ["my-url.tgz"],
            },
            # urls is not a list
            {"type": "url", "urls": "my-url.zip", "integrity": "my-integrity"},
            # type is not url
            {"type": "git", "urls": ["my-url.zip"], "integrity": "my-integrity"},
            # missing fields which got double-checked nonetheless...
            {"integrity": "my-integrity"},
        ],
        "revision": "my-revision",
    }
    clean = clean_sources(sources)

    assert len(clean["sources"]) == len(valid_sources)


def test_make_pattern_unsupported_file_extension():
    unsupported_extensions = ["el", "c", "txt"]
    supported_extensions = ["Z", "7z"]  # for test

    actual_unsupported_pattern = make_pattern_unsupported_file_extension(
        unsupported_extensions
    )

    for supported_ext in supported_extensions:
        assert supported_ext not in unsupported_extensions

        supported_filepath = f"anything.{supported_ext}"
        actual_match = actual_unsupported_pattern.match(supported_filepath)
        assert not actual_match

    for unsupported_ext in unsupported_extensions:
        unsupported_filepath = f"something.{unsupported_ext}"
        actual_match = actual_unsupported_pattern.match(unsupported_filepath)
        assert actual_match


def test_clean_sources_unsupported_artifacts(swh_storage, requests_mock_datadir):
    unsupported_file_extensions = [
        "iso",
        "whl",
        "gem",
        "pom",
        "msi",
        "pod",
        "png",
        "rock",
        "ttf",
        "jar",
        "c",
        "el",
        "rpm",
        "diff",
        "patch",
    ]
    supported_sources = [
        {
            "type": "url",
            "urls": [f"https://server.org/my-url.{ext}"],
            "integrity": "my-integrity",
        }
        for ext in [
            "known-unknown-but-ok",  # this is fine as well with the current approach
            "zip",
            "tar.gz",
            "tgz",
            "tar.bz2",
            "tbz",
            "tbz2",
            "tar.xz",
            "tar",
            "zip",
            "7z",
            "Z",
        ]
    ]

    unsupported_sources = [
        {
            "type": "url",
            "urls": [f"https://server.org/my-url.{ext}"],
            "integrity": "my-integrity",
        }
        for ext in unsupported_file_extensions
    ]

    sources = {
        "version": 1,
        "sources": supported_sources + unsupported_sources,
        "revision": "my-revision",
    }

    clean = clean_sources(sources, unsupported_file_extensions)

    assert len(clean["sources"]) == len(supported_sources)


def test_loader_one_visit(swh_storage, requests_mock_datadir, raw_sources):
    loader = NixGuixLoader(swh_storage, sources_url)
    load_status = loader.load()
    expected_snapshot_id = SNAPSHOT1.id
    expected_snapshot_id_hex = expected_snapshot_id.hex()
    assert load_status == {
        "status": "eventful",
        "snapshot_id": expected_snapshot_id_hex,
    }

    release_id = SNAPSHOT1.branches[
        b"https://github.com/owner-1/repository-1/revision-1.tgz"
    ].target
    check_snapshot(SNAPSHOT1, storage=swh_storage)

    assert swh_storage.release_get([release_id])[0] == Release(
        id=release_id,
        name=b"https://github.com/owner-1/repository-1/revision-1.tgz",
        message=None,
        target=hash_to_bytes("4de2e07d3742718d928e974b8a4c721b9f7b33bf"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
        author=Person.from_fullname(b""),
        date=None,
    )

    stats = get_stats(swh_storage)
    assert {
        "content": 1,
        "directory": 3,
        "origin": 1,
        "origin_visit": 1,
        "release": 2,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    # The visit is partial because urls pointing to non tarball file
    # are not handled yet
    assert_last_visit_matches(
        swh_storage, sources_url, status="partial", type="nixguix"
    )

    visit_status = origin_get_latest_visit_status(swh_storage, sources_url)
    snapshot_swhid = ExtendedSWHID(
        object_type=ExtendedObjectType.SNAPSHOT, object_id=visit_status.snapshot
    )
    metadata_authority = MetadataAuthority(
        type=MetadataAuthorityType.FORGE,
        url=sources_url,
    )
    expected_metadata = [
        RawExtrinsicMetadata(
            target=snapshot_swhid,
            authority=metadata_authority,
            fetcher=MetadataFetcher(
                name="swh.loader.package.nixguix.loader.NixGuixLoader",
                version=__version__,
            ),
            discovery_date=loader.visit_date,
            format="nixguix-sources-json",
            metadata=raw_sources,
            origin=sources_url,
        )
    ]
    assert swh_storage.raw_extrinsic_metadata_get(
        snapshot_swhid,
        metadata_authority,
    ) == PagedResult(
        next_page_token=None,
        results=expected_metadata,
    )


def test_uncompress_failure(swh_storage, requests_mock_datadir):
    """Non tarball files are currently not supported and the uncompress
    function fails on such kind of files.

    However, even in this case of failure (because of the url
    https://example.com/file.txt), a snapshot and a visit has to be
    created (with a status partial since all files are not archived).

    """
    loader = NixGuixLoader(swh_storage, sources_url)
    loader_status = loader.load()

    sources = loader.supported_sources()["sources"]
    urls = [s["urls"][0] for s in sources]
    assert "https://example.com/file.txt" in urls
    assert loader_status["status"] == "eventful"

    # The visit is partial because urls pointing to non tarball files
    # are not handled yet
    assert_last_visit_matches(
        swh_storage, sources_url, status="partial", type="nixguix"
    )


def test_loader_incremental(swh_storage, requests_mock_datadir):
    """Ensure a second visit do not download artifact already
    downloaded by the previous visit.

    """
    loader = NixGuixLoader(swh_storage, sources_url)
    load_status = loader.load()

    loader.load()
    assert load_status == {"status": "eventful", "snapshot_id": SNAPSHOT1.id.hex()}

    assert_last_visit_matches(
        swh_storage,
        sources_url,
        status="partial",
        type="nixguix",
        snapshot=SNAPSHOT1.id,
    )

    check_snapshot(SNAPSHOT1, storage=swh_storage)

    urls = [
        m.url
        for m in requests_mock_datadir.request_history
        if m.url == ("https://github.com/owner-1/repository-1/revision-1.tgz")
    ]
    # The artifact
    # 'https://github.com/owner-1/repository-1/revision-1.tgz' is only
    # visited one time
    assert len(urls) == 1


def test_loader_two_visits(swh_storage, requests_mock_datadir_visits):
    """To ensure there is only one origin, but two visits, two revisions
    and two snapshots are created.

    The first visit creates a snapshot containing one tarball. The
    second visit creates a snapshot containing the same tarball and
    another tarball.

    """
    loader = NixGuixLoader(swh_storage, sources_url)
    load_status = loader.load()
    assert load_status == {"status": "eventful", "snapshot_id": SNAPSHOT1.id.hex()}

    assert_last_visit_matches(
        swh_storage,
        sources_url,
        status="partial",
        type="nixguix",
        snapshot=SNAPSHOT1.id,
    )

    check_snapshot(SNAPSHOT1, storage=swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 1,
        "directory": 3,
        "origin": 1,
        "origin_visit": 1,
        "release": 2,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    loader = NixGuixLoader(swh_storage, sources_url)
    load_status = loader.load()
    expected_snapshot_id_hex = "c1983a0a3f647548e1fb92f30339da6848fe9f7a"
    expected_snapshot_id = hash_to_bytes(expected_snapshot_id_hex)
    assert load_status == {
        "status": "eventful",
        "snapshot_id": expected_snapshot_id_hex,
    }

    assert_last_visit_matches(
        swh_storage,
        sources_url,
        status="partial",
        type="nixguix",
        snapshot=expected_snapshot_id,
    )

    # This ensures visits are incremental. Indeed, if we request a
    # second time an url, because of the requests_mock_datadir_visits
    # fixture, the file has to end with `_visit1`.
    expected_snapshot = Snapshot(
        id=expected_snapshot_id,
        branches={
            b"evaluation": SnapshotBranch(
                target=hash_to_bytes("602140776b2ce6c9159bcf52ada73a297c063d5e"),
                target_type=TargetType.REVISION,
            ),
            b"https://github.com/owner-1/repository-1/revision-1.tgz": SnapshotBranch(
                target=hash_to_bytes("df7811b9644ed8ef088e2e7add62ed32b0bab15f"),
                target_type=TargetType.RELEASE,
            ),
            b"https://github.com/owner-2/repository-1/revision-1.tgz": SnapshotBranch(
                target=hash_to_bytes("5cc0115cd643902b837cb6cfbc9f5865bc5a7cb2"),
                target_type=TargetType.RELEASE,
            ),
        },
    )
    check_snapshot(expected_snapshot, storage=swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 2,
        "directory": 5,
        "origin": 1,
        "origin_visit": 2,
        "release": 3,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 2,
    } == stats


def test_evaluation_branch(swh_storage, requests_mock_datadir):
    loader = NixGuixLoader(swh_storage, sources_url)
    res = loader.load()
    assert res["status"] == "eventful"

    assert_last_visit_matches(
        swh_storage,
        sources_url,
        status="partial",
        type="nixguix",
        snapshot=SNAPSHOT1.id,
    )

    check_snapshot(SNAPSHOT1, storage=swh_storage)


def test_eoferror(swh_storage, requests_mock_datadir):
    """Load a truncated archive which is invalid to make the uncompress
    function raising the exception EOFError. We then check if a
    snapshot is created, meaning this error is well managed.

    """
    sources = (
        "https://nix-community.github.io/nixpkgs-swh/sources-EOFError.json"  # noqa
    )
    loader = NixGuixLoader(swh_storage, sources)
    loader.load()

    expected_snapshot = Snapshot(
        id=hash_to_bytes("4257fa2350168c6bfec726a06452ea27a2c0cb33"),
        branches={
            b"evaluation": SnapshotBranch(
                target=hash_to_bytes("cc4e04c26672dd74e5fd0fecb78b435fb55368f7"),
                target_type=TargetType.REVISION,
            ),
        },
    )

    check_snapshot(expected_snapshot, storage=swh_storage)


def fake_download(
    url: str,
    dest: str,
    hashes: Dict = {},
    filename: Optional[str] = None,
    auth: Optional[Tuple[str, str]] = None,
) -> Tuple[str, Dict]:
    """Fake download which raises HashCollision (for the sake of test simpliciy,
    let's accept that makes sense)

    For tests purpose only.

    """
    if url == "https://example.com/file.txt":
        # instead of failing because it's a file not dealt with by the nix guix
        # loader, make it raise a hash collision
        raise HashCollision("sha1", "f92d74e3874587aaf443d1db961d4e26dde13e9c", [])
    return download(url, dest, hashes, filename, auth)


def test_raise_exception(swh_storage, requests_mock_datadir, mocker):
    mock_download = mocker.patch("swh.loader.package.loader.download")
    mock_download.side_effect = fake_download

    loader = NixGuixLoader(swh_storage, sources_url)
    res = loader.load()

    assert res == {
        "status": "eventful",
        "snapshot_id": SNAPSHOT1.id.hex(),
    }

    # The visit is partial because some artifact downloads failed
    assert_last_visit_matches(
        swh_storage,
        sources_url,
        status="partial",
        type="nixguix",
        snapshot=SNAPSHOT1.id,
    )

    check_snapshot(SNAPSHOT1, storage=swh_storage)

    assert len(mock_download.mock_calls) == 3


def test_load_nixguix_one_common_artifact_from_other_loader(
    swh_storage, datadir, requests_mock_datadir_visits, caplog
):
    """Misformatted revision should be caught and logged, then loading continues"""
    caplog.set_level(logging.ERROR, "swh.loader.package.nixguix.loader")

    # 1. first ingest with for example the archive loader
    gnu_url = "https://ftp.gnu.org/gnu/8sync/"
    release = "0.1.0"
    artifact_url = f"https://ftp.gnu.org/gnu/8sync/8sync-{release}.tar.gz"
    gnu_artifacts = [
        {
            "time": 944729610,
            "url": artifact_url,
            "length": 221837,
            "filename": f"8sync-{release}.tar.gz",
            "version": release,
        }
    ]
    archive_loader = ArchiveLoader(swh_storage, url=gnu_url, artifacts=gnu_artifacts)
    actual_load_status = archive_loader.load()
    expected_snapshot_id = "9efecc835e8f99254934f256b5301b94f348fd17"
    assert actual_load_status["status"] == "eventful"
    assert actual_load_status["snapshot_id"] == expected_snapshot_id  # noqa

    assert_last_visit_matches(
        archive_loader.storage,
        gnu_url,
        status="full",
        type="tar",
        snapshot=hash_to_bytes(expected_snapshot_id),
    )

    # 2. Then ingest with the nixguix loader which lists the same artifact within its
    # sources.json

    # ensure test setup is ok
    data_sources = os.path.join(
        datadir, "https_nix-community.github.io", "nixpkgs-swh_sources_special.json"
    )
    all_sources = json.loads(open(data_sources).read())
    found = False
    for source in all_sources["sources"]:
        if source["urls"][0] == artifact_url:
            found = True
            assert (
                found is True
            ), f"test setup error: {artifact_url} must be in {data_sources}"

    # first visit with a snapshot, ok
    sources_url = "https://nix-community.github.io/nixpkgs-swh/sources_special.json"
    loader = NixGuixLoader(swh_storage, sources_url)
    actual_load_status2 = loader.load()
    assert actual_load_status2["status"] == "eventful"

    snapshot_id = actual_load_status2["snapshot_id"]

    assert_last_visit_matches(
        swh_storage,
        sources_url,
        status="full",
        type="nixguix",
        snapshot=hash_to_bytes(snapshot_id),
    )

    snapshot = snapshot_get_all_branches(swh_storage, hash_to_bytes(snapshot_id))
    assert snapshot
