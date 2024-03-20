# Copyright (C) 2018-2024 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import copy
from datetime import datetime, timezone
import functools
import io
import itertools
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import tempfile
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union
from urllib.parse import unquote, urlparse, urlsplit
from urllib.request import urlopen

from billiard import Process, Queue  # type: ignore
from dateutil.parser import parse
import psutil
import requests
from tenacity.before_sleep import before_sleep_log

from swh.core.retry import http_retry
from swh.core.tarball import uncompress
from swh.loader.core import __version__
from swh.loader.core.nar import Nar
from swh.loader.exception import NotFound
from swh.model.hashutil import HASH_BLOCK_SIZE, MultiHash
from swh.model.model import Person

logger = logging.getLogger(__name__)


DEFAULT_PARAMS: Dict[str, Any] = {
    "headers": {"User-Agent": "Software Heritage Loader (%s)" % (__version__)}
}
DOWNLOAD_HASHES = set(["sha1", "sha256", "length"])
EMPTY_AUTHOR = Person.from_fullname(b"")


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


def compute_hashes(filepath: str, hash_names: List[str] = ["sha256"]) -> Dict[str, str]:
    """Compute checksums dict out of a filepath"""
    return MultiHash.from_path(filepath, hash_names=hash_names).hexdigest()


def compute_nar_hashes(
    filepath: Path,
    hash_names: List[str] = ["sha256"],
    is_tarball=True,
    top_level=True,
) -> Dict[str, str]:
    """Compute nar checksums dict out of a filepath (tarball or plain file).

    If it's a tarball, this uncompresses the tarball in a temporary directory to compute
    the nar hashes (and then cleans it up).

    Args:
        filepath: The tarball (if is_tarball is True) or a filepath
        hash_names: The list of checksums to compute
        is_tarball: Whether filepath represents a tarball or not
        top_level: Whether we want to compute the top-level directory (of the tarball)
            hashes. This is only useful when used with 'is_tarball' at True.

    Returns:
        The dict of checksums values whose keys are present in hash_names.

    """
    with tempfile.TemporaryDirectory() as tmpdir:
        if is_tarball:
            directory_path = Path(tmpdir)
            directory_path.mkdir(parents=True, exist_ok=True)
            uncompress(str(filepath), dest=str(directory_path))

            if top_level:
                # Default behavior, pass the extracted tarball path root directory
                path_on_disk = directory_path
            else:
                # Pass along the first directory of the tarball
                path_on_disk = next(iter(directory_path.iterdir()))
        else:
            path_on_disk = filepath

        nar = Nar(hash_names)
        nar.serialize(path_on_disk)
        hashes = nar.hexdigest()

    return hashes


@http_retry(
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_url_body(url: str, **extra_params) -> bytes:
    """Basic HTTP client to retrieve information on software package,
    typically JSON metadata from a REST API.

    Args:
        url (str): An HTTP URL

    Raises:
        NotFound in case of query failures (for some reasons: 404, ...)

    Returns:
        The associated response's information

    """
    logger.debug("Fetching %s", url)
    response = requests.get(url, **{**DEFAULT_PARAMS, **extra_params})
    if response.status_code == 404:
        raise NotFound(f"Fail to query '{url}'. Reason: {response.status_code}")
    response.raise_for_status()
    return response.content


def _content_disposition_filename(header: str) -> Optional[str]:
    fname = None
    fnames = re.findall(r"filename[\*]?=([^;]+)", header)
    if fnames and "utf-8''" in fnames[0].lower():
        #  RFC 5987
        fname = re.sub("utf-8''", "", fnames[0], flags=re.IGNORECASE)
        fname = unquote(fname)
    elif fnames:
        fname = fnames[0]
    if fname:
        fname = os.path.basename(fname.strip().strip('"'))
    return fname


@http_retry(
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def download(
    url: str,
    dest: str,
    hashes: Dict = {},
    filename: Optional[str] = None,
    auth: Optional[Tuple[str, str]] = None,
    extra_request_headers: Optional[Dict[str, str]] = None,
) -> Tuple[str, Dict]:
    """Download a remote file from url, and compute swh hashes on it.

    Args:
        url: Artifact uri to fetch and hash
        dest: Directory to write the archive to
        hashes: Dict of expected hashes (key is the hash algo) for the artifact
            to download (those hashes are expected to be hex string). The supported
            algorithms are defined in the :data:`swh.model.hashutil.ALGORITHMS` set.
        auth: Optional tuple of login/password (for http authentication
            service, e.g. deposit)

    Raises:
        ValueError in case of any error when fetching/computing (length,
        checksums mismatched...)

    Returns:
        Tuple of local (filepath, hashes of filepath)

    """
    params = copy.deepcopy(DEFAULT_PARAMS)
    if auth is not None:
        params["auth"] = auth
    if extra_request_headers is not None:
        params["headers"].update(extra_request_headers)
    # so the connection does not hang indefinitely (read/connection timeout)
    timeout = params.get("timeout", 60)

    parsed_url = urlparse(url)
    if parsed_url.scheme == "ftp":
        response = urlopen(url, timeout=timeout)
        chunks = (response.read(HASH_BLOCK_SIZE) for _ in itertools.count())
    elif parsed_url.scheme == "file":
        response = open(parsed_url.path, "rb")
        chunks = (response.read(HASH_BLOCK_SIZE) for _ in itertools.count())
    else:
        # request artifact raw bytes without extra compression as requests set
        # Accept-Encoding header to "gzip, deflate" by default
        params["headers"]["Accept-Encoding"] = "identity"
        response = requests.get(url, **params, timeout=timeout, stream=True)
        response.raise_for_status()
        # update URL to response one as requests follow redirection by default
        # on GET requests
        url = response.url
        # try to extract filename from content-disposition header if available
        if filename is None and "content-disposition" in response.headers:
            filename = _content_disposition_filename(
                response.headers["content-disposition"]
            )
        content_type = response.headers.get("content-type")
        content_encoding = response.headers.get("content-encoding", "")
        if (
            content_type
            in {"application/x-gzip", "application/gzip", "application/x-gunzip"}
            and "gzip" in content_encoding
        ):
            # prevent automatic deflate of response bytes by requests
            chunks = response.raw.stream(HASH_BLOCK_SIZE, decode_content=False)
        else:
            chunks = response.iter_content(chunk_size=HASH_BLOCK_SIZE)

    response_data = itertools.takewhile(bool, chunks)

    filename = filename if filename else os.path.basename(urlsplit(url).path)

    logger.debug("filename: %s", filename)
    filepath = os.path.join(dest, filename)
    logger.debug("filepath: %s", filepath)

    h = MultiHash(hash_names=DOWNLOAD_HASHES | set(hashes.keys()))
    with open(filepath, "wb") as f:
        for chunk in response_data:
            h.update(chunk)
            f.write(chunk)

    response.close()

    # Also check the expected hashes if provided
    if hashes:
        actual_hashes = h.hexdigest()
        for algo_hash in hashes.keys():
            actual_digest = actual_hashes[algo_hash]
            expected_digest = hashes[algo_hash]
            if actual_digest != expected_digest:
                raise ValueError(
                    "Failure when fetching %s. "
                    "Checksum mismatched: %s != %s"
                    % (url, expected_digest, actual_digest)
                )

    computed_hashes = h.hexdigest()
    length = computed_hashes.pop("length")
    extrinsic_metadata = {
        "length": length,
        "filename": filename,
        "checksums": computed_hashes,
        "url": url,
    }

    logger.debug("extrinsic_metadata: %s", extrinsic_metadata)

    return filepath, extrinsic_metadata


def release_name(version: str, filename: Optional[str] = None) -> str:
    if filename:
        return "releases/%s/%s" % (version, filename)
    return "releases/%s" % version


_UNDEFINED = object()
TReturn = TypeVar("TReturn")
TSelf = TypeVar("TSelf")


def cached_method(f: Callable[[TSelf], TReturn]) -> Callable[[TSelf], TReturn]:
    cache_name = f"_cached_{f.__name__}"

    @functools.wraps(f)
    def newf(self):
        value = getattr(self, cache_name, _UNDEFINED)
        if value is _UNDEFINED:
            value = f(self)
            setattr(self, cache_name, value)
        return value

    return newf
