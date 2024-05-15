# Copyright (C) 2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import functools
from pathlib import Path
from urllib.parse import unquote, urlparse

from swh.loader.package.hackage.loader import HackageLoader
from swh.loader.tests import assert_last_visit_matches, check_snapshot, get_stats
from swh.model.hashutil import hash_to_bytes
from swh.model.model import (
    ObjectType,
    Person,
    Release,
    Snapshot,
    SnapshotBranch,
    SnapshotTargetType,
    TimestampWithTimezone,
)

EXPECTED_PACKAGES = [
    {
        "url": "https://hackage.haskell.org/package/aeson",  # one version
    },
    {
        "url": "https://hackage.haskell.org/package/colors",  # multiple versions
    },
    {
        "url": "https://hackage.haskell.org/package/Hs2lib",  # Caps in keys in .cabal filee  # noqa: B950
    },
    {
        "url": "https://hackage.haskell.org/package/numeric-qq",  # Key and value not in the same line in .cabal file  # noqa: B950
    },
    {
        "url": "https://hackage.haskell.org/package/haskell2010",  # Missing author in .cabal file  # noqa: B950
    },
]


def head_callback(request, context, datadir):
    """Callback for requests_mock that returns an HEAD response with headers.

    It will look for files on the local filesystem based on the requested URL,
    using the following rules:

    - files are searched in the datadir/<hostname> directory

    - the local file name is the path part of the URL with path hierarchy
      markers (aka '/') replaced by '_' and suffixed with '_head'

    Eg. if you use the requests_mock fixture in your test file as:

        requests_mock.head('https://nowhere.com', text=head_callback(datadir=datadir))

    then a call requests.head like:

        requests.head('https://nowhere.com/path_to_resource')

    will look the content of the response in:

        datadir/https_nowhere.com/path_to_resource_head
    """
    unquoted_url = unquote(request.url)
    url = urlparse(unquoted_url)
    dirname = "%s_%s" % (url.scheme, url.hostname)
    filename = url.path[1:]
    if filename.endswith("/"):
        filename = filename[:-1]
    filename = filename.replace("/", "_")
    filepath = Path(datadir, dirname, f"{filename}_head")

    # Convert raw text headers to headers dict
    headers_raw = filepath.read_text()
    lines = headers_raw.splitlines()
    lines = lines[1:]  # Ignore first line
    data = {}
    for line in lines:
        if line:
            k, v = line.split(":", 1)
            data[k] = v.strip()
    # update headers
    context.headers.update(data)
    # No body content to return
    return None


def test_get_versions(requests_mock_datadir, swh_storage):
    loader = HackageLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[1]["url"],
    )
    assert loader.get_versions() == [
        "0.1",
        "0.3.0.2",
    ]


def test_get_default_version(requests_mock_datadir, swh_storage):
    loader = HackageLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[1]["url"],
    )
    assert loader.get_default_version() == "0.3.0.2"


def test_hackage_loader_load_one_version(
    datadir, requests_mock_datadir, swh_storage, requests_mock
):
    requests_mock.head(
        url="https://hackage.haskell.org/package/aeson-2.1.0.0/aeson-2.1.0.0.tar.gz",
        status_code=200,
        text=functools.partial(head_callback, datadir=datadir),
    )

    loader = HackageLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[0]["url"],
    )
    load_status = loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    expected_snapshot_id = "cbe847edb44408826ed11685b34c28b27b160879"
    expected_release_id = "004c2dedccdb27557c083086213d453b62411b63"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/2.1.0.0": SnapshotBranch(
                target=hash_to_bytes(expected_release_id),
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/2.1.0.0",
                target_type=SnapshotTargetType.ALIAS,
            ),
        },
    )

    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 1,
        "directory": 2,
        "origin": 1,
        "origin_visit": 1,
        "release": 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    assert swh_storage.release_get([hash_to_bytes(expected_release_id)])[0] == Release(
        name=b"2.1.0.0",
        message=b"Synthetic release for Haskell source package aeson version 2.1.0.0\n",
        target=hash_to_bytes("3ad8674f6d9b983fa28d9d81d30f119f6252f1bb"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
        author=Person(
            fullname=b"Bryan O'Sullivan <bos@serpentine.com>",
            name=b"Bryan O'Sullivan",
            email=b"bos@serpentine.com",
        ),
        date=TimestampWithTimezone.from_iso8601("2022-08-11T09:04:30Z"),
        id=hash_to_bytes(expected_release_id),
    )

    assert_last_visit_matches(
        swh_storage,
        url=EXPECTED_PACKAGES[0]["url"],
        status="full",
        type="hackage",
        snapshot=expected_snapshot.id,
    )


def test_hackage_loader_load_multiple_version(
    datadir,
    requests_mock_datadir,
    swh_storage,
    requests_mock,
):
    requests_mock.head(
        url="https://hackage.haskell.org/package/colors-0.1/colors-0.1.tar.gz",
        status_code=200,
        text=functools.partial(head_callback, datadir=datadir),
    )

    requests_mock.head(
        url="https://hackage.haskell.org/package/colors-0.3.0.2/colors-0.3.0.2.tar.gz",
        status_code=200,
        text=functools.partial(head_callback, datadir=datadir),
    )

    loader = HackageLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[1]["url"],
    )
    load_status = loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    expected_snapshot_id = "835b2d6ff650c5bfc7e47f7ba4982f3cbfc939dc"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/0.3.0.2": SnapshotBranch(
                target=hash_to_bytes("639ff93de24d0f2ab53c0d4273128b35f04c794d"),
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"releases/0.1": SnapshotBranch(
                target=hash_to_bytes("2c2d247d8c0684ec691e95ae8e8ef59bfb757f29"),
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/0.3.0.2",
                target_type=SnapshotTargetType.ALIAS,
            ),
        },
    )

    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 1 + 1,
        "directory": 2 + 2,
        "origin": 1,
        "origin_visit": 1,
        "release": 1 + 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats


def test_hackage_loader_load_one_version_caps(
    datadir, requests_mock_datadir, swh_storage, requests_mock
):
    """Sometime package names and / or .cabal Keys have Caps"""

    requests_mock.head(
        url="https://hackage.haskell.org/package/Hs2lib-0.6.3/Hs2lib-0.6.3.tar.gz",
        status_code=200,
        text=functools.partial(head_callback, datadir=datadir),
    )

    loader = HackageLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[2]["url"],
    )
    load_status = loader.load()
    assert load_status["status"] == "eventful"
    assert load_status["snapshot_id"] is not None

    expected_snapshot_id = "c725683edf4ad8ab319ecbc50ee4e8f2ced0d4ff"
    expected_release_id = "ccb9c14776146d942d03a5a07c024d8d23d51fa2"

    assert expected_snapshot_id == load_status["snapshot_id"]

    expected_snapshot = Snapshot(
        id=hash_to_bytes(load_status["snapshot_id"]),
        branches={
            b"releases/0.6.3": SnapshotBranch(
                target=hash_to_bytes(expected_release_id),
                target_type=SnapshotTargetType.RELEASE,
            ),
            b"HEAD": SnapshotBranch(
                target=b"releases/0.6.3",
                target_type=SnapshotTargetType.ALIAS,
            ),
        },
    )

    check_snapshot(expected_snapshot, swh_storage)

    stats = get_stats(swh_storage)
    assert {
        "content": 1,
        "directory": 2,
        "origin": 1,
        "origin_visit": 1,
        "release": 1,
        "revision": 0,
        "skipped_content": 0,
        "snapshot": 1,
    } == stats

    assert swh_storage.release_get([hash_to_bytes(expected_release_id)])[0] == Release(
        name=b"0.6.3",
        message=b"Synthetic release for Haskell source package Hs2lib version 0.6.3\n",
        target=hash_to_bytes("fd53df3b6d9baec39effd9a08f1d538878860430"),
        target_type=ObjectType.DIRECTORY,
        synthetic=True,
        author=Person(
            fullname=b"Tamar Christina <tamar (at) zhox.com>",
            name=b"Tamar Christina",
            email=b"tamar (at) zhox.com",
        ),
        date=TimestampWithTimezone.from_iso8601("2015-01-27T11:58:10Z"),
        id=hash_to_bytes(expected_release_id),
    )

    assert_last_visit_matches(
        swh_storage,
        url=EXPECTED_PACKAGES[2]["url"],
        status="full",
        type="hackage",
        snapshot=expected_snapshot.id,
    )


def test_hackage_loader_cabal_file_key_value_not_on_same_line(
    datadir,
    requests_mock_datadir,
    swh_storage,
    requests_mock,
):
    """Sometime key and value in a .cabal file are not on the same line"""

    requests_mock.head(
        url="https://hackage.haskell.org/package/numeric-qq-0.1.0/numeric-qq-0.1.0.tar.gz",
        status_code=200,
        text=functools.partial(head_callback, datadir=datadir),
    )

    loader = HackageLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[3]["url"],
    )
    load_status = loader.load()

    expected_snapshot_id = "44cd282c91b42e2aef105076345f85b919f6ddc1"
    expected_release_id = "b7a5e7d69b6dd9377dad7d5850ae7f1304f824f2"

    assert load_status["status"] == "eventful"
    assert expected_snapshot_id == load_status["snapshot_id"]

    release = swh_storage.release_get([hash_to_bytes(expected_release_id)])[0]

    assert (
        release.message
        == b"Synthetic release for Haskell source package numeric-qq version 0.1.0\n"
    )
    assert release.author == Person(
        fullname=b"Nikita Volkov <nikita.y.volkov@mail.ru>",
        name=b"Nikita Volkov",
        email=b"nikita.y.volkov@mail.ru",
    )


def test_hackage_loader_cabal_file_missing_author(
    datadir,
    requests_mock_datadir,
    swh_storage,
    requests_mock,
):
    """Should not fail if we can't extract ``author``from .cabal file"""

    requests_mock.head(
        url="https://hackage.haskell.org/package/haskell2010-1.0.0.0/haskell2010-1.0.0.0.tar.gz",
        status_code=200,
        text=functools.partial(head_callback, datadir=datadir),
    )

    loader = HackageLoader(
        swh_storage,
        url=EXPECTED_PACKAGES[4]["url"],
    )
    load_status = loader.load()

    expected_snapshot_id = "f85dad18d1974b3c3063a720281e2abbe785bec0"
    expected_release_id = "4bbea2a5f90b5033501ba573758b06bd43bb7d63"

    assert load_status["status"] == "eventful"
    assert expected_snapshot_id == load_status["snapshot_id"]

    release = swh_storage.release_get([hash_to_bytes(expected_release_id)])[0]

    assert release.author.fullname == "HerbertValerioRiedel".encode()
