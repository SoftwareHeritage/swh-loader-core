# Copyright (C) 2019-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import datetime
import hashlib
import logging
import os
import string
from typing import Optional
from unittest.mock import Mock, call, patch

import attr
import pytest

from swh.loader.core.loader import (
    SENTRY_ORIGIN_URL_TAG_NAME,
    SENTRY_VISIT_TYPE_TAG_NAME,
)
from swh.loader.core.utils import EMPTY_AUTHOR
from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.model.model import (
    ExtID,
    Origin,
    OriginVisit,
    OriginVisitStatus,
    Person,
    Release,
    ReleaseTargetType,
    Revision,
    RevisionType,
    Sha1Git,
    Snapshot,
    SnapshotBranch,
    SnapshotTargetType,
    TimestampWithTimezone,
)
from swh.model.swhids import CoreSWHID, ObjectType
from swh.storage import get_storage
from swh.storage.algos.snapshot import snapshot_get_latest


class FakeStorage:
    def origin_add(self, origins):
        raise ValueError("We refuse to add an origin")

    def origin_visit_get_latest(self, origin):
        return None


class FakeStorage2(FakeStorage):
    def origin_add(self, origins):
        pass

    def origin_visit_add(self, visits):
        raise ValueError("We refuse to add an origin visit")


class StubPackageInfo(BasePackageInfo):
    pass


ORIGIN_URL = "https://example.org/package/example"


class StubPackageLoader(PackageLoader[StubPackageInfo]):
    visit_type = "stub"

    def get_loader_version(self) -> str:
        return "devel"

    def get_versions(self):
        return ["v1.0", "v2.0", "v3.0", "v4.0"]

    def get_package_info(self, version):
        filename = f"example-{version}.tar.gz"
        p_info = StubPackageInfo(
            f"{ORIGIN_URL}/{filename}",
            filename,
            version=version,
        )
        extid_type = "extid-type1" if version in ("v1.0", "v2.0") else "extid-type2"
        # Versions 1.0 and 2.0 have an extid of a given type, v3.0 has an extid
        # of a different type
        patch.object(
            p_info,
            "extid",
            return_value=(extid_type, 0, f"extid-of-{version}".encode()),
            autospec=True,
        ).start()
        yield (f"branch-{version}", p_info)

    def build_release(
        self, p_info: StubPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        msg = (
            f"Synthetic release for source package {p_info.url} "
            f"version {p_info.version}\n"
        )

        return Release(
            name=p_info.version.encode(),
            message=msg.encode(),
            date=None,
            author=EMPTY_AUTHOR,
            target_type=ReleaseTargetType.DIRECTORY,
            target=directory,
            synthetic=True,
        )


def test_loader_origin_visit_success(swh_storage, requests_mock_datadir):
    loader = StubPackageLoader(swh_storage, ORIGIN_URL)

    assert loader.load() == {
        "snapshot_id": "dcb9ecef64af73f2cdac7f5463cb6dece6b1db61",
        "status": "eventful",
    }

    assert loader.load_status() == {"status": "eventful"}
    assert loader.visit_status() == "full"

    assert set(loader.last_snapshot().branches.keys()) == {
        f"branch-{version}".encode() for version in loader.get_versions()
    }


def test_loader_origin_visit_failure(swh_storage):
    """Failure to add origin or origin visit should failed immediately"""
    loader = StubPackageLoader(swh_storage, "some-url")
    loader.storage = FakeStorage()

    actual_load_status = loader.load()
    assert actual_load_status == {"status": "failed"}

    assert loader.load_status() == {"status": "failed"}
    assert loader.visit_status() == "failed"

    loader.storage = FakeStorage2()

    actual_load_status2 = loader.load()
    assert actual_load_status2 == {"status": "failed"}

    assert loader.load_status() == {"status": "failed"}
    assert loader.visit_status() == "failed"


def test_resolve_object_from_extids() -> None:
    storage = get_storage("memory")
    target = b"\x01" * 20
    rel1 = Release(
        name=b"aaaa",
        message=b"aaaa",
        target=target,
        target_type=ReleaseTargetType.DIRECTORY,
        synthetic=False,
    )
    rel2 = Release(
        name=b"bbbb",
        message=b"bbbb",
        target=target,
        target_type=ReleaseTargetType.DIRECTORY,
        synthetic=False,
    )
    storage.release_add([rel1, rel2])

    loader = StubPackageLoader(storage, ORIGIN_URL)

    p_info = Mock(wraps=BasePackageInfo(None, None, None))  # type: ignore

    # The PackageInfo does not support extids
    p_info.extid.return_value = None
    known_extids = {("extid-type", 0, b"extid-of-aaaa"): [rel1.swhid()]}
    whitelist = {b"unused"}
    assert loader.resolve_object_from_extids(known_extids, p_info, whitelist) is None

    # Some known extid, and the PackageInfo is not one of them (ie. cache miss)
    p_info.extid.return_value = ("extid-type", 0, b"extid-of-cccc")
    assert loader.resolve_object_from_extids(known_extids, p_info, whitelist) is None

    # Some known extid, and the PackageInfo is one of them (ie. cache hit),
    # but the target release was not in the previous snapshot
    p_info.extid.return_value = ("extid-type", 0, b"extid-of-aaaa")
    assert loader.resolve_object_from_extids(known_extids, p_info, whitelist) is None

    # Some known extid, and the PackageInfo is one of them (ie. cache hit),
    # and the target release was in the previous snapshot
    whitelist = {rel1.id}
    assert (
        loader.resolve_object_from_extids(known_extids, p_info, whitelist)
        == rel1.swhid()
    )

    # Same as before, but there is more than one extid, and only one is an allowed
    # release
    whitelist = {rel1.id}
    known_extids = {("extid-type", 0, b"extid-of-aaaa"): [rel2.swhid(), rel1.swhid()]}
    assert (
        loader.resolve_object_from_extids(known_extids, p_info, whitelist)
        == rel1.swhid()
    )


def test_resolve_object_from_extids_missing_target() -> None:
    storage = get_storage("memory")

    target = b"\x01" * 20
    rel = Release(
        name=b"aaaa",
        message=b"aaaa",
        target=target,
        target_type=ReleaseTargetType.DIRECTORY,
        synthetic=False,
    )

    loader = StubPackageLoader(storage, ORIGIN_URL)

    p_info = Mock(wraps=BasePackageInfo(None, None, None))  # type: ignore

    known_extids = {("extid-type", 0, b"extid-of-aaaa"): [rel.swhid()]}
    p_info.extid.return_value = ("extid-type", 0, b"extid-of-aaaa")
    whitelist = {rel.id}

    # Targeted release is missing from the storage
    assert loader.resolve_object_from_extids(known_extids, p_info, whitelist) is None

    storage.release_add([rel])

    # Targeted release now exists
    assert (
        loader.resolve_object_from_extids(known_extids, p_info, whitelist)
        == rel.swhid()
    )


def test_load_get_known_extids() -> None:
    """Checks PackageLoader.load() fetches known extids efficiently"""
    storage = Mock(wraps=get_storage("memory"))

    loader = StubPackageLoader(storage, ORIGIN_URL)

    loader.load()

    # Calls should be grouped by extid type
    storage.extid_get_from_extid.assert_has_calls(
        [
            call("extid-type1", [b"extid-of-v1.0", b"extid-of-v2.0"], version=0),
            call("extid-type2", [b"extid-of-v3.0", b"extid-of-v4.0"], version=0),
        ],
        any_order=True,
    )


def test_load_extids() -> None:
    """Checks PackageLoader.load() skips iff it should, and writes (only)
    the new ExtIDs"""
    storage = get_storage("memory")

    dir_swhid = CoreSWHID(object_type=ObjectType.DIRECTORY, object_id=b"e" * 20)

    rels = [
        Release(
            name=f"v{i}.0".encode(),
            message=b"blah\n",
            target=dir_swhid.object_id,
            target_type=ReleaseTargetType.DIRECTORY,
            synthetic=True,
        )
        for i in (1, 2, 3, 4)
    ]
    storage.release_add(rels[0:3])

    origin = ORIGIN_URL
    rel1_swhid = rels[0].swhid()
    rel2_swhid = rels[1].swhid()
    rel3_swhid = rels[2].swhid()
    rel4_swhid = rels[3].swhid()

    # Results of a previous load
    storage.extid_add(
        [
            ExtID("extid-type1", b"extid-of-v1.0", rel1_swhid),
            ExtID("extid-type2", b"extid-of-v2.0", rel2_swhid),
        ]
    )
    last_snapshot = Snapshot(
        branches={
            b"v1.0": SnapshotBranch(
                target_type=SnapshotTargetType.RELEASE, target=rel1_swhid.object_id
            ),
            b"v2.0": SnapshotBranch(
                target_type=SnapshotTargetType.RELEASE, target=rel2_swhid.object_id
            ),
            b"v3.0": SnapshotBranch(
                target_type=SnapshotTargetType.RELEASE, target=rel3_swhid.object_id
            ),
        }
    )
    storage.snapshot_add([last_snapshot])
    date = datetime.datetime.now(tz=datetime.timezone.utc)
    storage.origin_add([Origin(url=origin)])
    storage.origin_visit_add(
        [OriginVisit(origin=origin, visit=1, date=date, type="stub")]
    )
    storage.origin_visit_status_add(
        [
            OriginVisitStatus(
                origin=origin,
                visit=1,
                status="full",
                date=date,
                snapshot=last_snapshot.id,
            )
        ]
    )

    loader = StubPackageLoader(storage, origin)
    patch.object(
        loader,
        "_load_release",
        return_value=(rel4_swhid.object_id, dir_swhid.object_id),
        autospec=True,
    ).start()

    loader.load()

    assert loader.load_status() == {"status": "eventful"}
    assert loader.visit_status() == "full"

    assert loader._load_release.mock_calls == [  # type: ignore
        # v1.0: not loaded because there is already its (extid_type, extid, rel)
        #       in the storage.
        # v2.0: loaded, because there is already a similar extid, but different type
        call(
            StubPackageInfo(
                f"{origin}/example-v2.0.tar.gz", "example-v2.0.tar.gz", "v2.0"
            ),
            Origin(url=origin),
        ),
        # v3.0: loaded despite having an (extid_type, extid) in storage, because
        #       the target of the extid is not in the previous snapshot
        call(
            StubPackageInfo(
                f"{origin}/example-v3.0.tar.gz", "example-v3.0.tar.gz", "v3.0"
            ),
            Origin(url=origin),
        ),
        # v4.0: loaded, because there isn't its extid
        call(
            StubPackageInfo(
                f"{origin}/example-v4.0.tar.gz", "example-v4.0.tar.gz", "v4.0"
            ),
            Origin(url=origin),
        ),
    ]

    # then check the snapshot has all the branches.
    # versions 2.0 to 4.0 all point to rel4_swhid (instead of the value of the last
    # snapshot), because they had to be loaded (mismatched extid), and the mocked
    # _load_release always returns rel4_swhid.
    snapshot = Snapshot(
        branches={
            b"branch-v1.0": SnapshotBranch(
                target_type=SnapshotTargetType.RELEASE, target=rel1_swhid.object_id
            ),
            b"branch-v2.0": SnapshotBranch(
                target_type=SnapshotTargetType.RELEASE, target=rel4_swhid.object_id
            ),
            b"branch-v3.0": SnapshotBranch(
                target_type=SnapshotTargetType.RELEASE, target=rel4_swhid.object_id
            ),
            b"branch-v4.0": SnapshotBranch(
                target_type=SnapshotTargetType.RELEASE, target=rel4_swhid.object_id
            ),
        }
    )
    assert snapshot_get_latest(storage, origin) == snapshot

    extids = storage.extid_get_from_target(
        ObjectType.RELEASE,
        [
            rel1_swhid.object_id,
            rel2_swhid.object_id,
            rel3_swhid.object_id,
            rel4_swhid.object_id,
        ],
    )

    assert set(extids) == {
        # What we inserted at the beginning of the test:
        ExtID("extid-type1", b"extid-of-v1.0", rel1_swhid),
        ExtID("extid-type2", b"extid-of-v2.0", rel2_swhid),
        # Added by the loader:
        ExtID("extid-type1", b"extid-of-v2.0", rel4_swhid),
        ExtID("extid-type2", b"extid-of-v3.0", rel4_swhid),
        ExtID("extid-type2", b"extid-of-v4.0", rel4_swhid),
    }


def test_load_upgrade_from_revision_extids(caplog):
    """Tests that, when loading incrementally based on a snapshot made by an old
    version of the loader, the loader will convert revisions to releases
    and add them to the storage.

    Also checks that, if an extid exists pointing to a non-existent revision
    (which should never happen, but you never know...), the release is loaded from
    scratch."""

    storage = get_storage("memory")

    origin = ORIGIN_URL
    dir1_swhid = CoreSWHID(object_type=ObjectType.DIRECTORY, object_id=b"d" * 20)
    dir2_swhid = CoreSWHID(object_type=ObjectType.DIRECTORY, object_id=b"e" * 20)

    date = TimestampWithTimezone.from_datetime(
        datetime.datetime.now(tz=datetime.timezone.utc)
    )
    person = Person.from_fullname(b"Jane Doe <jdoe@example.org>")

    rev1 = Revision(
        message=b"blah",
        author=person,
        date=date,
        committer=person,
        committer_date=date,
        directory=dir1_swhid.object_id,
        type=RevisionType.TAR,
        synthetic=True,
    )

    rel1 = Release(
        name=b"v1.0",
        message=b"blah\n",
        author=person,
        date=date,
        target=dir1_swhid.object_id,
        target_type=ReleaseTargetType.DIRECTORY,
        synthetic=True,
    )

    rev1_swhid = rev1.swhid()
    rel1_swhid = rel1.swhid()
    rev2_swhid = CoreSWHID(object_type=ObjectType.REVISION, object_id=b"b" * 20)
    rel2_swhid = CoreSWHID(object_type=ObjectType.RELEASE, object_id=b"c" * 20)

    # Results of a previous load
    storage.extid_add(
        [
            ExtID("extid-type1", b"extid-of-v1.0", rev1_swhid, 0),
            ExtID("extid-type1", b"extid-of-v2.0", rev2_swhid, 0),
        ]
    )
    storage.revision_add([rev1])
    last_snapshot = Snapshot(
        branches={
            b"v1.0": SnapshotBranch(
                target_type=SnapshotTargetType.REVISION, target=rev1_swhid.object_id
            ),
            b"v2.0": SnapshotBranch(
                target_type=SnapshotTargetType.REVISION, target=rev2_swhid.object_id
            ),
        }
    )
    storage.snapshot_add([last_snapshot])
    date = datetime.datetime.now(tz=datetime.timezone.utc)
    storage.origin_add([Origin(url=origin)])
    storage.origin_visit_add(
        [OriginVisit(origin=origin, visit=1, date=date, type="stub")]
    )
    storage.origin_visit_status_add(
        [
            OriginVisitStatus(
                origin=origin,
                visit=1,
                status="full",
                date=date,
                snapshot=last_snapshot.id,
            )
        ]
    )

    loader = StubPackageLoader(storage, origin)
    patch.object(
        loader,
        "_load_release",
        return_value=(rel2_swhid.object_id, dir2_swhid.object_id),
        autospec=True,
    ).start()
    patch.object(
        loader,
        "get_versions",
        return_value=["v1.0", "v2.0", "v3.0"],
        autospec=True,
    ).start()

    caplog.set_level(logging.ERROR)

    loader.load()

    assert loader.load_status() == {"status": "eventful"}
    assert loader.visit_status() == "full"

    assert len(caplog.records) == 1
    (record,) = caplog.records
    assert record.levelname == "ERROR"
    assert "Failed to upgrade branch branch-v2.0" in record.message

    assert loader._load_release.mock_calls == [
        # v1.0: not loaded because there is already a revision matching it
        # v2.0: loaded, as the revision is missing from the storage even though there
        #       is an extid
        call(
            StubPackageInfo(
                f"{origin}/example-v2.0.tar.gz", "example-v2.0.tar.gz", "v2.0"
            ),
            Origin(url=origin),
        ),
        # v3.0: loaded (did not exist yet)
        call(
            StubPackageInfo(
                f"{origin}/example-v3.0.tar.gz", "example-v3.0.tar.gz", "v3.0"
            ),
            Origin(url=origin),
        ),
    ]

    snapshot = Snapshot(
        branches={
            b"branch-v1.0": SnapshotBranch(
                target_type=SnapshotTargetType.RELEASE, target=rel1_swhid.object_id
            ),
            b"branch-v2.0": SnapshotBranch(
                target_type=SnapshotTargetType.RELEASE, target=rel2_swhid.object_id
            ),
            b"branch-v3.0": SnapshotBranch(
                target_type=SnapshotTargetType.RELEASE, target=rel2_swhid.object_id
            ),
        }
    )
    assert snapshot_get_latest(storage, origin) == snapshot

    extids = storage.extid_get_from_target(
        ObjectType.RELEASE,
        [
            rel1_swhid.object_id,
            rel2_swhid.object_id,
        ],
    )

    assert set(extids) == {
        ExtID("extid-type1", b"extid-of-v1.0", rel1_swhid),
        ExtID("extid-type1", b"extid-of-v2.0", rel2_swhid),
        ExtID("extid-type2", b"extid-of-v3.0", rel2_swhid),
    }


def test_manifest_extid():
    """Compute primary key should return the right identity"""

    @attr.s
    class TestPackageInfo(BasePackageInfo):
        a = attr.ib()
        b = attr.ib()
        length = attr.ib()
        filename = attr.ib()

        MANIFEST_FORMAT = string.Template("$a $b")

    p_info = TestPackageInfo(
        url="http://example.org/",
        a=1,
        b=2,
        length=221837,
        filename="8sync-0.1.0.tar.gz",
        version="0.1.0",
    )

    actual_id = p_info.extid()
    assert actual_id == ("package-manifest-sha256", 0, hashlib.sha256(b"1 2").digest())


def test_no_env_swh_config_filename_raise(monkeypatch):
    """No SWH_CONFIG_FILENAME environment variable makes package loader init raise"""

    class DummyPackageLoader(PackageLoader):
        """A dummy package loader for test purpose"""

        pass

    monkeypatch.delenv("SWH_CONFIG_FILENAME", raising=False)

    with pytest.raises(
        AssertionError, match="SWH_CONFIG_FILENAME environment variable is undefined"
    ):
        DummyPackageLoader.from_configfile(url="some-url")


class StubPackageLoaderWithError(StubPackageLoader):
    def get_versions(self, *args, **kwargs):
        raise Exception("error")


def test_loader_sentry_tags_on_error(swh_storage, sentry_events):
    origin_url = ORIGIN_URL
    loader = StubPackageLoaderWithError(swh_storage, origin_url)
    loader.load()
    assert loader.load_status() == {"status": "failed"}
    assert loader.visit_status() == "failed"
    sentry_tags = sentry_events[0]["tags"]
    assert sentry_tags.get(SENTRY_ORIGIN_URL_TAG_NAME) == origin_url
    assert (
        sentry_tags.get(SENTRY_VISIT_TYPE_TAG_NAME)
        == StubPackageLoaderWithError.visit_type
    )


class StubPackageLoaderWithPackageInfoFailure(StubPackageLoader):
    def get_package_info(self, version):
        if version == "v2.0":
            raise Exception("Error when getting package info")
        else:
            return super().get_package_info(version)


def test_loader_origin_with_package_info_failure(swh_storage, requests_mock_datadir):
    loader = StubPackageLoaderWithPackageInfoFailure(swh_storage, ORIGIN_URL)

    assert loader.load() == {
        "snapshot_id": "b4cce7081d661fb7f4d7a1db96e8044b752eb0b0",
        "status": "eventful",
    }

    assert loader.load_status() == {"status": "eventful"}
    assert loader.visit_status() == "partial"

    assert set(loader.last_snapshot().branches.keys()) == {
        f"branch-v{i}.0".encode() for i in (1, 3, 4)
    }


def test_loader_with_dangling_branch_in_last_snapshot(
    swh_storage, requests_mock_datadir
):
    loader = StubPackageLoader(swh_storage, ORIGIN_URL)

    assert loader.load() == {
        "snapshot_id": "dcb9ecef64af73f2cdac7f5463cb6dece6b1db61",
        "status": "eventful",
    }

    last_snapshot = loader.last_snapshot()

    class StubPackageLoaderWithDanglingBranchInLastSnapshot(StubPackageLoader):
        def last_snapshot(self):
            snapshot = last_snapshot.to_dict()
            snapshot["branches"][b"branch-v1.0"] = None
            return Snapshot.from_dict(snapshot)

    loader = StubPackageLoaderWithDanglingBranchInLastSnapshot(swh_storage, ORIGIN_URL)

    assert loader.load() == {
        "snapshot_id": "dcb9ecef64af73f2cdac7f5463cb6dece6b1db61",
        "status": "eventful",
    }


class StubPackageLoaderDuplicatedReleases(StubPackageLoader):
    def get_versions(self):
        return ["v1.0", "v1", "v2.0", "v2", "v3.0", "v3", "v4.0", "v4"]

    def get_package_info(self, version):
        filename = f"example-{version}.tar.gz"
        filepath = os.path.join(
            os.path.dirname(__file__),
            "data",
            "https_example.org",
            f"package_example_{filename}",
        )
        with open(filepath, "rb") as file:
            sha256_checksum = hashlib.sha256(file.read())

        p_info = StubPackageInfo(
            f"{ORIGIN_URL}/{filename}",
            filename,
            version=version,
            checksums={"sha256": sha256_checksum.hexdigest()},
        )
        extid_type = "extid-stub-sha256"

        patch.object(
            p_info,
            "extid",
            return_value=(extid_type, 1, sha256_checksum.digest()),
            autospec=True,
        ).start()
        yield (f"branch-{version}", p_info)


def test_loader_with_duplicated_releases(swh_storage, requests_mock_datadir, mocker):
    """Check each package release is downloaded and processed only once."""
    loader = StubPackageLoaderDuplicatedReleases(swh_storage, ORIGIN_URL)

    load_release = mocker.spy(loader, "_load_release")

    assert loader.load() == {
        "status": "eventful",
        "snapshot_id": "a01fb6280bedbfc3609d3b6ae06e70bf2b4186fa",
    }

    # versions v{i}.0 and v{i} target the same release so load_release
    # should have been called once per unique release
    assert len(load_release.mock_calls) == len(loader.get_versions()) / 2

    snasphot = loader.last_snapshot()

    # all referenced versions should be found in the snapshot
    assert len(snasphot.branches) == len(loader.get_versions())

    # check branch-v{i}.0 and branch-v{i} target the same release
    for i in range(1, 5):
        assert (
            snasphot.branches[f"branch-v{i}.0".encode()]
            == snasphot.branches[f"branch-v{i}".encode()]
        )
