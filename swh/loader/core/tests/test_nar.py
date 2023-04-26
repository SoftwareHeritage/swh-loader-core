# Copyright (C) 2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from pathlib import Path

from click.testing import CliRunner
import pytest

from swh.core.tarball import uncompress
from swh.loader.core.nar import Nar


def test_nar_tarball(tmpdir, tarball_with_nar_hashes):
    tarball_path, nar_hashes = tarball_with_nar_hashes

    directory_path = Path(tmpdir)
    directory_path.mkdir(parents=True, exist_ok=True)
    uncompress(str(tarball_path), dest=str(directory_path))
    path_on_disk = next(directory_path.iterdir())

    nar = Nar(hash_names=list(nar_hashes.keys()))
    nar.serialize(path_on_disk)
    assert nar.hexdigest() == nar_hashes


def test_nar_content(content_with_nar_hashes):
    content_path, nar_hashes = content_with_nar_hashes

    nar = Nar(hash_names=list(nar_hashes.keys()))
    nar.serialize(content_path)
    assert nar.hexdigest() == nar_hashes


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
def cli_nar():
    from swh.loader.core.nar import cli

    return cli


def assert_output_contains(cli_output: str, snippet: str) -> bool:
    for line in cli_output.splitlines():
        if not line:
            continue

        if snippet in line:
            return True
    else:
        assert False, "%r not found in output %r" % (
            snippet,
            cli_output,
        )


def test_nar_cli_help(cli_runner, cli_nar):

    result = cli_runner.invoke(cli_nar, ["--help"])

    assert result.exit_code == 0
    assert_output_contains(result.output, "Compute NAR hashes on a directory.")


def test_nar_cli_tarball(cli_runner, cli_nar, tmpdir, tarball_with_nar_hashes):
    tarball_path, nar_hashes = tarball_with_nar_hashes

    directory_path = Path(tmpdir)
    directory_path.mkdir(parents=True, exist_ok=True)
    uncompress(str(tarball_path), dest=str(directory_path))
    path_on_disk = next(directory_path.iterdir())

    assert list(nar_hashes.keys()) == ["sha256"]

    result = cli_runner.invoke(cli_nar, ["--hash-algo", "sha256", str(path_on_disk)])

    assert result.exit_code == 0
    assert_output_contains(result.output, nar_hashes["sha256"])


def test_nar_cli_content(cli_runner, cli_nar, content_with_nar_hashes):
    content_path, nar_hashes = content_with_nar_hashes

    result = cli_runner.invoke(cli_nar, ["-H", "sha256", "-f", "hex", content_path])

    assert result.exit_code == 0

    assert_output_contains(result.output, nar_hashes["sha256"])
