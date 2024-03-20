# Copyright (C) 2019-2022 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import datetime

from click.formatting import HelpFormatter
from click.testing import CliRunner
import pytest

from swh.loader.cli import SUPPORTED_LOADERS, get_loader
from swh.loader.cli import loader as loader_cli
from swh.loader.core.utils import compute_hashes
from swh.loader.package.loader import PackageLoader


def test_get_loader_wrong_input(swh_config):
    """Unsupported loader should raise"""
    loader_type = "unknown"
    assert loader_type not in SUPPORTED_LOADERS
    with pytest.raises(ValueError, match="Invalid loader"):
        get_loader(loader_type, url="db-url")


def test_get_loader(swh_loader_config):
    """Instantiating a supported loader should be ok"""
    loader_input = {
        "archive": {"url": "some-url", "artifacts": []},
        "debian": {
            "url": "some-url",
            "packages": [],
        },
        "npm": {
            "url": "https://www.npmjs.com/package/onepackage",
        },
        "pypi": {
            "url": "some-url",
        },
    }
    for loader_type, kwargs in loader_input.items():
        kwargs["storage"] = swh_loader_config["storage"]
        loader = get_loader(loader_type, **kwargs)
        assert isinstance(loader, PackageLoader)


def _write_usage(command, args, max_width=80):
    hf = HelpFormatter(width=max_width)
    hf.write_usage(command, args)
    return hf.getvalue()[:-1]


def test_run_help(swh_config):
    """Usage message should contain list of available loaders"""
    runner = CliRunner()

    result = runner.invoke(loader_cli, ["run", "-h"])

    assert result.exit_code == 0

    # Syntax depends on dependencies' versions
    supported_loaders = "|".join(SUPPORTED_LOADERS)
    usage_prefix = _write_usage("loader run", "[OPTIONS] [%s]\n" % supported_loaders)
    usage_prefix2 = _write_usage("loader run", "[OPTIONS] {%s}\n" % supported_loaders)
    assert result.output.startswith((usage_prefix, usage_prefix2))


def test_run_directory_loader_success(swh_config, datadir):
    """Loading success should exit with 0."""

    tarball_path = f"{datadir}/0805nexter-1.1.0.tar.gz"
    checksums = compute_hashes(tarball_path, ["sha1", "sha256", "sha512"])
    tarball_url = f"file://{tarball_path}"

    runner = CliRunner()
    result = runner.invoke(
        loader_cli,
        [
            "-C",
            swh_config,
            "run",
            "directory",
            tarball_url,
            f"checksums={checksums}",
        ],
    )
    assert result.exit_code == 0


def test_run_directory_loader_failure(swh_config):
    """Loading failure should exit with 1."""

    tarball_url = "file://non/existent/path"

    runner = CliRunner()
    result = runner.invoke(
        loader_cli,
        [
            "-C",
            swh_config,
            "run",
            "directory",
            tarball_url,
            "checksums={}",
        ],
    )
    assert result.exit_code == 1


def test_run_with_visit_date(mocker, swh_config):
    """iso visit_date parameter should be parsed as datetime"""
    mock_loader = mocker.patch("swh.loader.cli.get_loader")

    runner = CliRunner()
    input_date = "2016-05-03 15:16:32+00"
    runner.invoke(
        loader_cli, ["run", "npm", "https://some-url", f"visit_date='{input_date}'"]
    )

    expected_parsed_date = datetime.datetime(
        2016, 5, 3, 15, 16, 32, tzinfo=datetime.timezone.utc
    )
    mock_loader.assert_called_once_with(
        "npm",
        storage={"cls": "memory"},
        url="https://some-url",
        visit_date=expected_parsed_date,
        metadata_fetcher_credentials=None,
    )


def test_list_help(mocker, swh_config):
    """Usage message should contain list of available loaders"""
    runner = CliRunner()
    result = runner.invoke(loader_cli, ["list", "--help"])
    assert result.exit_code == 0
    usage_prefix = _write_usage(
        "loader list", f"[OPTIONS] [[{'|'.join(['all'] + SUPPORTED_LOADERS)}]]"
    )
    expected_help_msg = f"""{usage_prefix}

  List supported loaders and optionally their arguments

Options:
  -h, --help  Show this message and exit.
"""
    assert result.output.startswith(expected_help_msg)


def test_list_help_npm(mocker, swh_config):
    """Triggering a load should be ok"""
    runner = CliRunner()
    result = runner.invoke(loader_cli, ["list", "npm"])
    assert result.exit_code == 0
    expected_help_msg = """
Loader: Load npm origin's artifact releases into swh archive.
"""
    assert result.output.startswith(expected_help_msg[1:])
