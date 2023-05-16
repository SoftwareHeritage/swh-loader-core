# Copyright (C) 2018 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


from datetime import datetime, timezone
import io
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
import traceback
from typing import Callable, Dict, List, Optional, Union

from billiard import Process, Queue  # type: ignore
from dateutil.parser import parse
import psutil

from swh.core.tarball import uncompress
from swh.loader.core.nar import Nar


def clean_dangling_folders(dirpath: str, pattern_check: str, log=None) -> None:
    """Clean up potential dangling temporary working folder rooted at `dirpath`. Those
       folders must match a dedicated pattern and not belonging to a live pid.

    Args:
        dirpath: Path to check for dangling files
        pattern_check: A dedicated pattern to check on first level directory (e.g
            `swh.loader.mercurial.`, `swh.loader.svn.`)
        log (Logger): Optional logger

    """
    if not os.path.exists(dirpath):
        return
    for filename in os.listdir(dirpath):
        path_to_cleanup = os.path.join(dirpath, filename)
        try:
            # pattern: `swh.loader.{loader-type}-pid.{noise}`
            if (
                pattern_check not in filename or "-" not in filename
            ):  # silently ignore unknown patterns
                continue
            _, pid_ = filename.split("-")
            pid = int(pid_.split(".")[0])
            if psutil.pid_exists(pid):
                if log:
                    log.debug("PID %s is live, skipping", pid)
                continue
            # could be removed concurrently, so check before removal
            if os.path.exists(path_to_cleanup):
                shutil.rmtree(path_to_cleanup)
        except Exception as e:
            if log:
                log.warn("Fail to clean dangling path %s: %s", path_to_cleanup, e)


class CloneTimeout(Exception):
    pass


class CloneFailure(Exception):
    pass


def _clone_task(clone_func: Callable[[], None], errors: Queue) -> None:
    try:
        clone_func()
    except Exception as e:
        exc_buffer = io.StringIO()
        traceback.print_exc(file=exc_buffer)
        errors.put_nowait(exc_buffer.getvalue())
        raise e


def clone_with_timeout(
    src: str, dest: str, clone_func: Callable[[], None], timeout: float
) -> None:
    """Clone a repository with timeout.

    Args:
        src: clone source
        dest: clone destination
        clone_func: callable that does the actual cloning
        timeout: timeout in seconds
    """
    errors: Queue = Queue()
    process = Process(target=_clone_task, args=(clone_func, errors))
    process.start()
    process.join(timeout)

    if process.is_alive():
        process.terminate()
        # Give it literally a second (in successive steps of 0.1 second),
        # then kill it.
        # Can't use `process.join(1)` here, billiard appears to be bugged
        # https://github.com/celery/billiard/issues/270
        killed = False
        for _ in range(10):
            time.sleep(0.1)
            if not process.is_alive():
                break
        else:
            killed = True
            os.kill(process.pid, signal.SIGKILL)
        raise CloneTimeout(src, timeout, killed)

    if not errors.empty():
        raise CloneFailure(src, dest, errors.get())


def parse_visit_date(visit_date: Optional[Union[datetime, str]]) -> Optional[datetime]:
    """Convert visit date from either None, a string or a datetime to either None or
    datetime.

    """
    if visit_date is None:
        return None

    if isinstance(visit_date, datetime):
        return visit_date

    if visit_date == "now":
        return datetime.now(tz=timezone.utc)

    if isinstance(visit_date, str):
        return parse(visit_date)

    raise ValueError(f"invalid visit date {visit_date!r}")


def compute_nar_hashes(
    filepath: Path,
    hash_names: List[str] = ["sha256"],
    is_tarball=True,
) -> Dict[str, str]:
    """Compute nar checksums dict out of a filepath (tarball or plain file).

    If it's a tarball, this uncompresses the tarball in a temporary directory to compute
    the nar hashes (and then cleans it up).

    Args:
        filepath: The tarball (if is_tarball is True) or a filepath
        hash_names: The list of checksums to compute
        is_tarball: Whether filepath represents a tarball or not

    Returns:
        The dict of checksums values whose keys are present in hash_names.

    """
    with tempfile.TemporaryDirectory() as tmpdir:
        if is_tarball:
            directory_path = Path(tmpdir)
            directory_path.mkdir(parents=True, exist_ok=True)
            uncompress(str(filepath), dest=str(directory_path))
            path_on_disk = next(directory_path.iterdir())
        else:
            path_on_disk = filepath

        nar = Nar(hash_names)
        nar.serialize(path_on_disk)
        hashes = nar.hexdigest()

    return hashes
