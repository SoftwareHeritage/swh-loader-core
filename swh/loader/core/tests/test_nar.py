# Copyright (C) 2023-2024  The Software Heritage developers
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

    nar = Nar(hash_names=list(nar_hashes.keys()))
    nar.serialize(directory_path)
    assert nar.hexdigest() == nar_hashes


def test_nar_tarball_with_executable(tmpdir, tarball_with_executable_with_nar_hashes):
    """Compute nar on tarball with executable files inside should not mismatch"""
    tarball_path, nar_hashes = tarball_with_executable_with_nar_hashes

    directory_path = Path(tmpdir)
    directory_path.mkdir(parents=True, exist_ok=True)
    uncompress(str(tarball_path), dest=str(directory_path))

    nar = Nar(hash_names=list(nar_hashes.keys()))
    nar.serialize(directory_path)
    assert nar.hexdigest() == nar_hashes


def test_nar_content(content_with_nar_hashes):
    content_path, nar_hashes = content_with_nar_hashes

    nar = Nar(hash_names=list(nar_hashes.keys()))
    nar.serialize(content_path)
    assert nar.hexdigest() == nar_hashes


def test_nar_executable(executable_with_nar_hashes):
    """Compute nar on file with executable bit set should not mismatch"""
    content_path, nar_hashes = executable_with_nar_hashes

    nar = Nar(hash_names=list(nar_hashes.keys()))
    nar.serialize(content_path)
    assert nar.hexdigest() == nar_hashes


def test_nar_exclude_vcs(tmpdir, mocker):
    directory_path = Path(tmpdir)

    file_path = directory_path / "file"
    file_path.write_text("file")

    git_path = directory_path / ".git"
    git_path.mkdir()

    git_file_path = git_path / "foo"
    git_file_path.write_text("foo")

    subdir_path = directory_path / "bar"
    subdir_path.mkdir()

    git_subdir_path = subdir_path / ".git"
    git_subdir_path.mkdir()

    svn_subdir_path = subdir_path / ".svn"
    svn_subdir_path.mkdir()

    git_subdir_file_path = git_subdir_path / "baz"
    git_subdir_file_path.write_text("baz")

    nar = Nar(hash_names=["sha1"], exclude_vcs=True, vcs_type="git")

    serializeEntry = mocker.spy(nar, "_serializeEntry")

    nar.serialize(directory_path)

    # check .git subdirs were not taken into account for nar hash computation
    assert mocker.call(Path(git_path)) not in serializeEntry.mock_calls
    assert mocker.call(Path(git_subdir_path)) not in serializeEntry.mock_calls

    # check .svn subdir was taken into account for nar hash computation
    serializeEntry.assert_any_call(Path(svn_subdir_path))

    assert nar.hexdigest() == {"sha1": "f1b641c46888a1002e340c9425ef8ec890605858"}


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

    assert list(nar_hashes.keys()) == ["sha256"]

    result = cli_runner.invoke(cli_nar, ["--hash-algo", "sha256", str(directory_path)])

    assert result.exit_code == 0
    assert_output_contains(result.output, nar_hashes["sha256"])


def test_nar_cli_content(cli_runner, cli_nar, content_with_nar_hashes):
    content_path, nar_hashes = content_with_nar_hashes

    result = cli_runner.invoke(cli_nar, ["-H", "sha256", "-f", "hex", content_path])

    assert result.exit_code == 0

    assert_output_contains(result.output, nar_hashes["sha256"])
