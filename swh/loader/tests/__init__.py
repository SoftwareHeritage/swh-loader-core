# Copyright (C) 2018-2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from collections import defaultdict
import os
from pathlib import PosixPath
import subprocess
import tempfile
from typing import Dict, Iterable, List, Optional, Tuple, Union

from swh.loader.core.nar import Nar
from swh.model.hashutil import hash_to_bytes
from swh.model.model import ExtID, OriginVisitStatus, Snapshot, SnapshotTargetType
from swh.model.swhids import ObjectType
from swh.storage.algos.origin import origin_get_latest_visit_status
from swh.storage.algos.snapshot import snapshot_get_all_branches
from swh.storage.interface import StorageInterface
from swh.vault.to_disk import DirectoryBuilder


def assert_last_visit_matches(
    storage,
    url: str,
    status: str,
    type: Optional[str] = None,
    snapshot: Optional[bytes] = None,
) -> OriginVisitStatus:
    """This retrieves the last visit and visit_status which are expected to exist.

    This also checks that the {visit|visit_status} have their respective properties
    correctly set.

    This returns the last visit_status for that given origin.

    Args:
        url: Origin url
        status: Check that the visit status has the given status
        type: Check that the returned visit has the given type
        snapshot: Check that the visit status points to the given snapshot

    Raises:
        AssertionError in case visit or visit status is not found, or any of the type,
        status and snapshot mismatch

    Returns:
        the visit status for further check during the remaining part of the test.

    """
    __tracebackhide__ = True  # Hide from pytest tracebacks on failure
    visit_status = origin_get_latest_visit_status(storage, url)
    assert visit_status is not None, f"Origin {url} has no visits"
    if type:
        assert (
            visit_status.type == type
        ), f"Visit has type {visit_status.type} instead of {type}"
    assert (
        visit_status.status == status
    ), f"Visit_status has status {visit_status.status} instead of {status}"
    if snapshot is not None:
        assert visit_status.snapshot is not None
        assert visit_status.snapshot == snapshot, (
            f"Visit_status points to snapshot {visit_status.snapshot.hex()} "
            f"instead of {snapshot.hex()}"
        )

    return visit_status


def prepare_repository_from_archive(
    archive_path: str,
    filename: Optional[str] = None,
    tmp_path: Union[PosixPath, str] = "/tmp",
) -> str:
    """Given an existing archive_path, uncompress it.
    Returns a file repo url which can be used as origin url.

    This does not deal with the case where the archive passed along does not exist.

    """
    if not isinstance(tmp_path, str):
        tmp_path = str(tmp_path)
    # uncompress folder/repositories/dump for the loader to ingest
    subprocess.check_output(["tar", "xf", archive_path, "-C", tmp_path])
    # build the origin url (or some derivative form)
    _fname = filename if filename else os.path.basename(archive_path)
    repo_url = f"file://{tmp_path}/{_fname}"
    return repo_url


def encode_target(target: Dict) -> Dict:
    """Test helper to ease readability in test"""
    if not target:
        return target
    target_type = target["target_type"]
    target_data = target["target"]
    if target_type == "alias" and isinstance(target_data, str):
        encoded_target = target_data.encode("utf-8")
    elif isinstance(target_data, str):
        encoded_target = hash_to_bytes(target_data)
    else:
        encoded_target = target_data

    return {"target": encoded_target, "target_type": target_type}


class InconsistentAliasBranchError(AssertionError):
    """When an alias branch targets an inexistent branch."""

    pass


class InexistentObjectsError(AssertionError):
    """When a targeted branch reference does not exist in the storage"""

    pass


def check_snapshot(
    expected_snapshot: Snapshot,
    storage: StorageInterface,
    allowed_empty: Iterable[Tuple[SnapshotTargetType, bytes]] = [],
) -> Snapshot:
    """Check that:
    - snapshot exists in the storage and match
    - each object reference up to the revision/release targets exists

    Args:
        expected_snapshot: full snapshot to check for existence and consistency
        storage: storage to lookup information into
        allowed_empty: Iterable of branch we allow to be empty (some edge case loaders
          allows this case to happen, nixguix for example allows the branch evaluation"
          to target the nixpkgs git commit reference, which may not yet be resolvable at
          loading time)

    Returns:
        the snapshot stored in the storage for further test assertion if any is
        needed.

    """
    __tracebackhide__ = True  # Hide from pytest tracebacks on failure
    if not isinstance(expected_snapshot, Snapshot):
        raise AssertionError(
            f"argument 'expected_snapshot' must be a snapshot: {expected_snapshot!r}"
        )

    snapshot = snapshot_get_all_branches(storage, expected_snapshot.id)
    if snapshot is None:
        raise AssertionError(f"Snapshot {expected_snapshot.id.hex()} is not found")

    assert snapshot == expected_snapshot

    objects_by_target_type = defaultdict(list)
    object_to_branch = {}
    for branch, target in expected_snapshot.branches.items():
        if (target.target_type, branch) in allowed_empty:
            # safe for those elements to not be checked for existence
            continue
        objects_by_target_type[target.target_type].append(target.target)
        object_to_branch[target.target] = branch

    # check that alias references target something that exists, otherwise raise
    aliases: List[bytes] = objects_by_target_type.get(SnapshotTargetType.ALIAS, [])
    for alias in aliases:
        if alias not in expected_snapshot.branches:
            raise InconsistentAliasBranchError(
                f"Alias branch {alias.decode('utf-8')} "
                f"should be in {list(expected_snapshot.branches)}"
            )

    revs = objects_by_target_type.get(SnapshotTargetType.REVISION)
    if revs:
        revisions = storage.revision_get(revs)
        not_found = [rev_id for rev_id, rev in zip(revs, revisions) if rev is None]
        if not_found:
            missing_objs = ", ".join(
                str((object_to_branch[rev], rev.hex())) for rev in not_found
            )
            raise InexistentObjectsError(
                f"Branch/Revision(s) {missing_objs} should exist in storage"
            )
        # retrieve information from revision
        for revision in revisions:
            assert revision is not None
            objects_by_target_type[SnapshotTargetType.DIRECTORY].append(
                revision.directory
            )
            object_to_branch[revision.directory] = revision.id

    rels = objects_by_target_type.get(SnapshotTargetType.RELEASE)
    if rels:
        not_found = list(storage.release_missing(rels))
        if not_found:
            missing_objs = ", ".join(
                str((object_to_branch[rel], rel.hex())) for rel in not_found
            )
            raise InexistentObjectsError(
                f"Branch/Release(s) {missing_objs} should exist in storage"
            )

    # first level dirs exist?
    dirs = objects_by_target_type.get(SnapshotTargetType.DIRECTORY)
    if dirs:
        not_found = list(storage.directory_missing(dirs))
        if not_found:
            missing_objs = ", ".join(
                str((object_to_branch[dir_].hex(), dir_.hex())) for dir_ in not_found
            )
            raise InexistentObjectsError(
                f"Missing directories {missing_objs}: "
                "(revision exists, directory target does not)"
            )
        for dir_ in dirs:  # retrieve new objects to check for existence
            paths = storage.directory_ls(dir_, recursive=True)
            for path in paths:
                if path["type"] == "dir":
                    target_type = SnapshotTargetType.DIRECTORY
                else:
                    target_type = SnapshotTargetType.CONTENT
                target = path["target"]
                objects_by_target_type[target_type].append(target)
                object_to_branch[target] = dir_

    # check nested directories
    dirs = objects_by_target_type.get(SnapshotTargetType.DIRECTORY)
    if dirs:
        not_found = list(storage.directory_missing(dirs))
        if not_found:
            missing_objs = ", ".join(
                str((object_to_branch[dir_].hex(), dir_.hex())) for dir_ in not_found
            )
            raise InexistentObjectsError(
                f"Missing directories {missing_objs}: "
                "(revision exists, directory target does not)"
            )

    # check contents directories
    cnts = objects_by_target_type.get(SnapshotTargetType.CONTENT)
    if cnts:
        not_found = list(storage.content_missing_per_sha1_git(cnts))
        if not_found:
            missing_objs = ", ".join(
                str((object_to_branch[cnt].hex(), cnt.hex())) for cnt in not_found
            )
            raise InexistentObjectsError(f"Missing contents {missing_objs}")

    return snapshot


def get_stats(storage) -> Dict:
    """Adaptation utils to unify the stats counters across storage
    implementation.

    """
    storage.refresh_stat_counters()
    stats = storage.stat_counters()

    keys = [
        "content",
        "directory",
        "origin",
        "origin_visit",
        "release",
        "revision",
        "skipped_content",
        "snapshot",
    ]
    return {k: stats.get(k) for k in keys}


def fetch_extids_from_checksums(
    storage: StorageInterface,
    checksum_layout: str,
    checksums: Dict[str, str],
    extid_version: int = 0,
) -> List[ExtID]:
    extids = []
    extid_type = None
    if checksum_layout == "nar":
        extid_type = "nar-%s"
    elif checksum_layout == "standard":
        extid_type = "checksum-%s"

    if extid_type:
        for hash_algo, checksum in checksums.items():
            id_type = extid_type % hash_algo
            ids = [hash_to_bytes(checksum)]
            extid = storage.extid_get_from_extid(id_type, ids, extid_version)
            extids.extend(extid)

        for extid_ in extids:
            if extid_.extid_type.startswith("nar-"):
                # check NAR hashes of archived directory or content match the expected ones
                target_swhid = extid_.target
                with tempfile.TemporaryDirectory() as tmp_dir:
                    nar = Nar(hash_names=list(checksums.keys()))
                    if target_swhid.object_type == ObjectType.DIRECTORY:
                        dir_builder = DirectoryBuilder(
                            storage=storage,
                            root=tmp_dir.encode(),
                            dir_id=target_swhid.object_id,
                        )
                        dir_builder.build()
                        path_to_hash = tmp_dir
                    else:
                        path_to_hash = os.path.join(tmp_dir, "content")
                        content_bytes = storage.content_get_data(
                            {"sha1_git": target_swhid.object_id}
                        )
                        assert content_bytes is not None
                        with open(path_to_hash, "wb") as content:
                            content.write(content_bytes)

                    nar.serialize(PosixPath(path_to_hash))
                    assert nar.hexdigest() == checksums

    return extids


def assert_task_and_visit_type_match(tasks_module_name: str) -> None:
    """This checks the tasks declared in the ``tasks_module_name`` have their loader visit
    type and their associated task name matching. If that's not the case, that poses
    issues when scheduling visits.

    Args:
        tasks_module_name: Fully qualified name of SWH module defining celery tasks

    Raises:
        AssertionError: when there is a discrepancy between a visit type of a loader and
          the task name

    """
    from importlib import import_module

    mod = import_module(tasks_module_name)
    task_names = [x for x in dir(mod) if x.startswith("load_")]
    loaders = [x for x in dir(mod) if x.endswith("Loader")]

    for loader in loaders:
        loader_cls = getattr(mod, loader)
        visit_type = loader_cls.visit_type
        task_function_name = f"load_{visit_type.replace('-', '_')}"
        assert task_function_name in task_names, (
            f"task function {task_function_name} for visit type {visit_type } "
            f"is missing in {tasks_module_name}"
        )


def assert_module_tasks_are_scheduler_ready(
    packages: Iterable, passthrough: List = []
) -> None:
    """This iterates over a list of packages and check that "tasks" modules declare
    tasks ready to be scheduled. If any discrepancy exist between a task and its loader
    visit type, those will never get picked up by the scheduler, they are not scheduler
    ready. This is an incorrect behavior that needs to be fixed immediately. This check
    ensures that any improper configured task/loader will be reported so developer can
    fix it.

    Args:
        packages: List of imported swh packages
        passthrough: List of authorized modules to not pass any checks. Those would be
          module with loader whose visit type already hit the archive.

    Raises:
        AssertionError: when there is any discrepancy between a loader's visit type and
          its associated task name in the ``packages`` list.

    """

    import pkgutil

    for package in packages:
        for _, modname, _ in pkgutil.walk_packages(
            package.__path__, prefix=f"{package.__name__}."
        ):
            if modname in passthrough:
                continue
            if modname.endswith(".tasks"):
                assert_task_and_visit_type_match(modname)
