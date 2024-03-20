# Copyright (C) 2019-2024 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from datetime import datetime
from io import BytesIO
import json
import os
from pathlib import Path
import signal
from time import sleep
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.parse import quote

import pytest
from requests.exceptions import HTTPError
from urllib3.response import HTTPResponse

import swh.loader.core
from swh.loader.core.utils import (
    CloneFailure,
    CloneTimeout,
    clean_dangling_folders,
    clone_with_timeout,
    compute_nar_hashes,
    download,
    get_url_body,
    parse_visit_date,
    release_name,
)
from swh.model.hashutil import MultiHash


def prepare_arborescence_from(tmpdir, folder_names):
    """Prepare arborescence tree with folders

    Args:
        tmpdir (Either[LocalPath, str]): Root temporary directory
        folder_names (List[str]): List of folder names

    Returns:
        List of folders
    """
    dangling_folders = []
    for dname in folder_names:
        d = str(tmpdir / dname)
        os.mkdir(d)
        dangling_folders.append(d)
    return str(tmpdir), dangling_folders


def assert_dirs(actual_dirs, expected_dirs):
    """Assert that the directory actual and expected match"""
    for d in actual_dirs:
        assert d in expected_dirs
    assert len(actual_dirs) == len(expected_dirs)


def test_clean_dangling_folders_0(tmpdir):
    """Folder does not exist, do nothing"""
    r = clean_dangling_folders("/path/does/not/exist", "unused-pattern")
    assert r is None


@patch("swh.loader.core.utils.psutil.pid_exists", return_value=False)
def test_clean_dangling_folders_1(mock_pid_exists, tmpdir):
    """Folder which matches pattern with dead pid are cleaned up"""
    rootpath, dangling = prepare_arborescence_from(
        tmpdir,
        [
            "something",
            "swh.loader.svn-4321.noisynoise",
        ],
    )

    clean_dangling_folders(rootpath, "swh.loader.svn")

    actual_dirs = os.listdir(rootpath)
    mock_pid_exists.assert_called_once_with(4321)
    assert_dirs(actual_dirs, ["something"])


@patch("swh.loader.core.utils.psutil.pid_exists", return_value=True)
def test_clean_dangling_folders_2(mock_pid_exists, tmpdir):
    """Folder which matches pattern with live pid are skipped"""
    rootpath, dangling = prepare_arborescence_from(
        tmpdir,
        [
            "something",
            "swh.loader.hg-1234.noisynoise",
        ],
    )

    clean_dangling_folders(rootpath, "swh.loader.hg")

    actual_dirs = os.listdir(rootpath)
    mock_pid_exists.assert_called_once_with(1234)
    assert_dirs(
        actual_dirs,
        [
            "something",
            "swh.loader.hg-1234.noisynoise",
        ],
    )


@patch("swh.loader.core.utils.psutil.pid_exists", return_value=False)
@patch(
    "swh.loader.core.utils.shutil.rmtree",
    side_effect=ValueError("Could not remove for reasons"),
)
def test_clean_dangling_folders_3(mock_rmtree, mock_pid_exists, tmpdir):
    """Error in trying to clean dangling folders are skipped"""
    path1 = "thingy"
    path2 = "swh.loader.git-1468.noisy"
    rootpath, dangling = prepare_arborescence_from(
        tmpdir,
        [
            path1,
            path2,
        ],
    )

    clean_dangling_folders(rootpath, "swh.loader.git")

    actual_dirs = os.listdir(rootpath)
    mock_pid_exists.assert_called_once_with(1468)
    mock_rmtree.assert_called_once_with(os.path.join(rootpath, path2))
    assert_dirs(actual_dirs, [path2, path1])


def test_clone_with_timeout_no_error_no_timeout():
    def succeed():
        """This does nothing to simulate a successful clone"""

    clone_with_timeout("foo", "bar", succeed, timeout=0.5)


def test_clone_with_timeout_no_error_timeout():
    def slow():
        """This lasts for more than the timeout"""
        sleep(1)

    with pytest.raises(CloneTimeout):
        clone_with_timeout("foo", "bar", slow, timeout=0.5)


def test_clone_with_timeout_error():
    def raise_something():
        raise RuntimeError("panic!")

    with pytest.raises(CloneFailure):
        clone_with_timeout("foo", "bar", raise_something, timeout=0.5)


def test_clone_with_timeout_sigkill():
    """This also tests that the traceback is useful"""
    src = "https://www.mercurial-scm.org/repo/hello"
    dest = "/dev/null"
    timeout = 0.5
    sleepy_time = 100 * timeout
    assert sleepy_time > timeout

    def ignores_sigterm(*args, **kwargs):
        # ignore SIGTERM to force sigkill
        signal.signal(signal.SIGTERM, lambda signum, frame: None)
        sleep(sleepy_time)  # we make sure we exceed the timeout

    with pytest.raises(CloneTimeout) as e:
        clone_with_timeout(src, dest, ignores_sigterm, timeout)
    killed = True
    assert e.value.args == (src, timeout, killed)


VISIT_DATE_STR = "2021-02-17 15:50:04.518963"
VISIT_DATE = datetime(2021, 2, 17, 15, 50, 4, 518963)


@pytest.mark.parametrize(
    "input_visit_date,expected_date",
    [
        (None, None),
        (VISIT_DATE, VISIT_DATE),
        (VISIT_DATE_STR, VISIT_DATE),
    ],
)
def test_utils_parse_visit_date(input_visit_date, expected_date):
    assert parse_visit_date(input_visit_date) == expected_date


def test_utils_parse_visit_date_now():
    actual_date = parse_visit_date("now")
    assert isinstance(actual_date, datetime)


def test_utils_parse_visit_date_fails():
    with pytest.raises(ValueError, match="invalid"):
        parse_visit_date(10)  # not a string nor a date


def test_compute_nar_hashes_tarball(tarball_with_nar_hashes):
    tarball_path, nar_checksums = tarball_with_nar_hashes

    actual_checksums = compute_nar_hashes(tarball_path, nar_checksums.keys())

    assert actual_checksums == nar_checksums


def test_compute_nar_hashes_file(content_with_nar_hashes):
    content_path, nar_checksums = content_with_nar_hashes

    actual_checksums = compute_nar_hashes(
        content_path, nar_checksums.keys(), is_tarball=False
    )

    assert actual_checksums == nar_checksums


def test_version_generation():
    assert (
        swh.loader.core.__version__ != "devel"
    ), "Make sure swh.loader.core is installed (e.g. pip install -e .)"


@pytest.mark.fs
def test_download_fail_to_download(tmp_path, requests_mock):
    url = "https://pypi.org/pypi/arrow/json"
    status_code = 404
    requests_mock.get(url, status_code=status_code)

    with pytest.raises(
        HTTPError, match=f"{status_code} Client Error: None for url: {url}"
    ):
        download(url, tmp_path)


_filename = "requests-0.0.1.tar.gz"
_data = "this is something"
_hashes = {
    "length": len(_data),
    "sha1": "fdd1ce606a904b08c816ba84f3125f2af44d92b2",
    "sha256": "1d9224378d77925d612c9f926eb9fb92850e6551def8328011b6a972323298d5",
}


def _check_download_ok(url, dest, filename=_filename, hashes=_hashes):
    actual_filepath, _ = download(url, dest, hashes=hashes)
    actual_filename = os.path.basename(actual_filepath)
    assert actual_filename == filename


@pytest.mark.fs
def test_download_ok(tmp_path, requests_mock):
    """Download without issue should provide filename and hashes"""
    url = f"https://pypi.org/pypi/requests/{_filename}"
    requests_mock.get(url, text=_data, headers={"content-length": str(len(_data))})
    _check_download_ok(url, dest=str(tmp_path))


@pytest.mark.fs
def test_download_ok_no_header(tmp_path, requests_mock):
    """Download without issue should provide filename and hashes"""
    url = f"https://pypi.org/pypi/requests/{_filename}"
    requests_mock.get(url, text=_data)  # no header information
    _check_download_ok(url, dest=str(tmp_path))


@pytest.mark.fs
def test_download_ok_with_hashes(tmp_path, requests_mock):
    """Download without issue should provide filename and hashes"""
    url = f"https://pypi.org/pypi/requests/{_filename}"
    requests_mock.get(url, text=_data, headers={"content-length": str(len(_data))})

    # good hashes for such file
    good = {
        "sha1": "fdd1ce606a904b08c816ba84f3125f2af44d92b2",
        "sha256": "1d9224378d77925d612c9f926eb9fb92850e6551def8328011b6a972323298d5",  # noqa
    }

    _check_download_ok(url, dest=str(tmp_path), hashes=good)


@pytest.mark.fs
def test_download_fail_hashes_mismatch(tmp_path, requests_mock):
    """Mismatch hash after download should raise"""
    url = f"https://pypi.org/pypi/requests/{_filename}"
    requests_mock.get(url, text=_data, headers={"content-length": str(len(_data))})

    # good hashes for such file
    good = {
        "sha1": "fdd1ce606a904b08c816ba84f3125f2af44d92b2",
        "sha256": "1d9224378d77925d612c9f926eb9fb92850e6551def8328011b6a972323298d5",  # noqa
    }

    for hash_name in good.keys():
        wrong_hash = good[hash_name].replace("1", "0")
        expected_hashes = good.copy()
        expected_hashes[hash_name] = wrong_hash  # set the wrong hash

        expected_msg = "Failure when fetching %s. " "Checksum mismatched: %s != %s" % (
            url,
            wrong_hash,
            good[hash_name],
        )

        with pytest.raises(ValueError, match=expected_msg):
            download(url, dest=str(tmp_path), hashes=expected_hashes)


@pytest.mark.fs
def test_ftp_download_ok(tmp_path, mocker):
    """Download without issue should provide filename and hashes"""
    url = f"ftp://pypi.org/pypi/requests/{_filename}"

    cm = MagicMock()
    cm.getstatus.return_value = 200
    cm.read.side_effect = [_data.encode(), b""]
    cm.__enter__.return_value = cm
    mocker.patch("swh.loader.core.utils.urlopen").return_value = cm

    _check_download_ok(url, dest=str(tmp_path))


@pytest.mark.fs
def test_ftp_download_ko(tmp_path, mocker):
    """Download without issue should provide filename and hashes"""
    filename = "requests-0.0.1.tar.gz"
    url = "ftp://pypi.org/pypi/requests/%s" % filename

    mocker.patch("swh.loader.core.utils.urlopen").side_effect = URLError("FTP error")

    with pytest.raises(URLError):
        download(url, dest=str(tmp_path))


@pytest.mark.fs
def test_download_with_redirection(tmp_path, requests_mock):
    """Download with redirection should use the targeted URL to extract filename"""
    url = "https://example.org/project/requests/download"
    redirection_url = f"https://example.org/project/requests/files/{_filename}"

    requests_mock.get(url, status_code=302, headers={"location": redirection_url})
    requests_mock.get(
        redirection_url, text=_data, headers={"content-length": str(len(_data))}
    )

    _check_download_ok(url, dest=str(tmp_path))


def test_download_extracting_filename_from_url(tmp_path, requests_mock):
    """Extracting filename from url must sanitize the filename first"""
    url = "https://example.org/project/requests-0.0.1.tar.gz?a=b&c=d&foo=bar"

    requests_mock.get(
        url, status_code=200, text=_data, headers={"content-length": str(len(_data))}
    )

    _check_download_ok(url, dest=str(tmp_path))


@pytest.mark.fs
@pytest.mark.parametrize(
    "filename", [f'"{_filename}"', _filename, '"filename with spaces.tar.gz"']
)
def test_download_filename_from_content_disposition(tmp_path, requests_mock, filename):
    """Filename should be extracted from content-disposition request header
    when available."""
    url = "https://example.org/download/requests/tar.gz/v0.0.1"

    requests_mock.get(
        url,
        text=_data,
        headers={
            "content-length": str(len(_data)),
            "content-disposition": f"attachment; filename={filename}",
        },
    )

    _check_download_ok(url, dest=str(tmp_path), filename=filename.strip('"'))


@pytest.mark.fs
@pytest.mark.parametrize("filename", ['"archive école.tar.gz"', "archive_école.tgz"])
def test_download_utf8_filename_from_content_disposition(
    tmp_path, requests_mock, filename
):
    """Filename should be extracted from content-disposition request header
    when available."""
    url = "https://example.org/download/requests/tar.gz/v0.0.1"
    data = "this is something"

    requests_mock.get(
        url,
        text=data,
        headers={
            "content-length": str(len(data)),
            "content-disposition": f"attachment; filename*=utf-8''{quote(filename)}",
        },
    )

    _check_download_ok(url, dest=str(tmp_path), filename=filename.strip('"'))


def test_api_info_failure(requests_mock):
    """Failure to fetch info/release information should raise"""
    url = "https://pypi.org/pypi/requests/json"
    status_code = 400
    requests_mock.get(url, status_code=status_code)

    with pytest.raises(
        HTTPError, match=f"{status_code} Client Error: None for url: {url}"
    ):
        get_url_body(url)


def test_api_info(requests_mock):
    """Fetching json info from pypi project should be ok"""
    url = "https://pypi.org/pypi/requests/json"
    requests_mock.get(url, text='{"version": "0.0.1"}')
    actual_info = json.loads(get_url_body(url))
    assert actual_info == {
        "version": "0.0.1",
    }


def test_release_name():
    for version, filename, expected_release in [
        ("0.0.1", None, "releases/0.0.1"),
        ("0.0.2", "something", "releases/0.0.2/something"),
    ]:
        assert release_name(version, filename) == expected_release


def test_download_retry(requests_mock, tmp_path):
    url = f"https://example.org/project/requests/files/{_filename}"

    requests_mock.get(
        url,
        [
            {"status_code": 429},
            {"status_code": 429},
            {
                "text": _data,
                "headers": {"content-length": str(len(_data))},
                "status_code": 200,
            },
        ],
    )

    _check_download_ok(url, dest=str(tmp_path))


def test_download_retry_reraise(requests_mock, tmp_path):
    url = f"https://example.org/project/requests/files/{_filename}"

    requests_mock.get(
        url,
        [{"status_code": 429}] * 5,
    )

    with pytest.raises(HTTPError):
        _check_download_ok(url, dest=str(tmp_path))


def test_api_info_retry(requests_mock):
    url = "https://example.org/api/endpoint"
    json_data = {"foo": "bar"}

    requests_mock.get(
        url,
        [
            {"status_code": 429},
            {"status_code": 429},
            {
                "json": json_data,
                "status_code": 200,
            },
        ],
    )

    assert json.loads(get_url_body(url)) == json_data


def test_api_info_retry_reraise(requests_mock):
    url = "https://example.org/api/endpoint"

    requests_mock.get(
        url,
        [{"status_code": 429}] * 5,
    )

    with pytest.raises(HTTPError, match=f"429 Client Error: None for url: {url}"):
        get_url_body(url)


@pytest.mark.parametrize(
    "gzip_content_encoding",
    [True, False],
    ids=["with gzip encoding", "without gzip encoding"],
)
def test_download_prevent_auto_deflate(
    requests_mock, datadir, tmp_path, gzip_content_encoding
):
    url = "https://example.org/archives/dummy-hello.tar.gz"
    data = Path(
        datadir, "https_example.org", "archives_dummy-hello.tar.gz"
    ).read_bytes()

    headers = {
        "content-type": "application/x-gzip",
        "content-length": str(len(data)),
    }

    if gzip_content_encoding:
        headers["content-encoding"] = "gzip"

    requests_mock.get(
        url,
        raw=HTTPResponse(body=BytesIO(data), headers=headers, preload_content=False),
    )

    hashes = MultiHash(hash_names={"md5", "sha1", "sha256"})
    hashes.update(data)

    _check_download_ok(
        url,
        dest=str(tmp_path),
        filename="dummy-hello.tar.gz",
        hashes=hashes.hexdigest(),
    )
