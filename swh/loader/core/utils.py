# Copyright (C) 2018-2021  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import os
import shutil

import psutil


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
