# Copyright (C) 2022-2023 zimoun and the Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import base64
import hashlib
import io
import os
from pathlib import Path
import stat
from typing import Dict, List, Optional

import click

from swh.core.cli import CONTEXT_SETTINGS
from swh.core.cli import swh as swh_cli_group
from swh.model.hashutil import hash_to_hex

CHUNK_SIZE = 65536


class Nar:
    """NAR serializer.

    This builds the NAR structure and serializes it as per the phd thesis from Eelco
    Dolstra thesis. See https://edolstra.github.io/pubs/phd-thesis.pdf.

    For example, this tree on a filesystem:

    .. code::

       $ tree foo
       foo
       ├── bar
       │   └── exe
       └── baz

       1 directory, 2 files

    serializes as:

    .. code::

       nix-archive-1(typedirectoryentry(namebarnode(typedirectoryentry(nameexenode(typeregularexecutablecontents<Content of file foo/bar/exe>))))entry(namebaznode(typeregularcontents<Content of file foo/baz>)))

    For reability, the debug mode prints the following:

    .. code::

       nix-archive-1
         (
         type
         directory
           entry
           (
           name
           bar
           node
             (
             type
             directory
               entry
               (
               name
               exe
               node
                 (
                 type
                 regular
                 executable

                 contents
                 <Content of file foo/bar/exe>
                 )
               )
             )
           )
           entry
           (
           name
           baz
           node
             (
             type
             regular
             contents
             <Content of file foo/baz>
            )
          )
        )

    Note: "<Content of file $name>" is a placeholder for the actual file content

    """  # noqa

    def __init__(
        self,
        hash_names: List[str],
        format_output: str = "hex",
        exclude_vcs: bool = False,
        vcs_type: Optional[str] = "git",
        debug: bool = False,
    ):
        self.hash_names = hash_names
        self.updater = {
            hash_name: hashlib.sha256()
            if hash_name.lower() == "sha256"
            else hashlib.sha1()
            for hash_name in hash_names
        }
        format_output = format_output.lower()
        self.exclude_vcs = exclude_vcs
        self.vcs_type = vcs_type

        self.__debug = debug
        self.__indent = 0

    def str_(self, thing):
        """Compute the nar serialization format on 'thing' and compute its hash.

        This is the function named named 'str' in Figure 5.2 p.93 (page 101 of pdf) [1]

        [1] https://edolstra.github.io/pubs/phd-thesis.pdf
        """
        if self.__debug and isinstance(thing, (str, io.BufferedReader)):
            indent = "".join(["  " for _ in range(self.__indent)])
            if isinstance(thing, io.BufferedReader):
                msg = f"{indent} <Content of file {thing.name}>"
            else:
                msg = f"{indent}{thing}"
            print(msg)

        # named 'int'
        if isinstance(thing, str):
            byte_sequence = thing.encode("utf-8")
            length = len(byte_sequence)
        elif isinstance(thing, io.BufferedReader):
            length = os.stat(thing.name).st_size
        # ease reading of _serialize
        elif isinstance(thing, list):
            for stuff in thing:
                self.str_(stuff)
            return
        else:
            raise ValueError("not string nor file")

        blen = length.to_bytes(8, byteorder="little")  # 64-bit little endian
        self.update(blen)

        # first part of 'pad'
        if isinstance(thing, str):
            self.update(byte_sequence)
        elif isinstance(thing, io.BufferedReader):
            for chunk in iter(lambda: thing.read(CHUNK_SIZE), b""):
                self.update(chunk)

        # second part of 'pad
        m = length % 8
        if m == 0:
            offset = 0
        else:
            offset = 8 - m
        boffset = bytearray(offset)
        self.update(boffset)

    def update(self, chunk):
        for hash_name in self.hash_names:
            self.updater[hash_name].update(chunk)

    def _filter_and_serialize(self, fso: Path) -> None:
        """On the first level of the main tree, we may have to skip some paths (e.g.
        .git, ...). Once those are ignored, we can serialize the remaining part of the
        entries.

        """
        path_to_ignore = (
            f"{fso}/.{self.vcs_type}" if self.exclude_vcs and self.vcs_type else None
        )
        for path in sorted(Path(fso).iterdir()):
            if path_to_ignore is None or not path.match(path_to_ignore):
                self._serializeEntry(path)

    def _only_serialize(self, fso: Path) -> None:
        """Every other level of the nested tree, we do not have to check for any path so
        we can just serialize the entries of the tree.

        """
        for path in sorted(Path(fso).iterdir()):
            self._serializeEntry(path)

    def _serialize(self, fso: Path):
        if self.__debug:
            self.__indent += 1
        self.str_("(")

        mode = os.lstat(fso).st_mode

        if stat.S_ISREG(mode):
            self.str_(["type", "regular"])
            if mode & 0o111 != 0:
                self.str_(["executable", ""])
            self.str_("contents")
            with open(str(fso), "rb") as f:
                self.str_(f)

        elif stat.S_ISLNK(mode):
            self.str_(["type", "symlink", "target"])
            self.str_(os.readlink(fso))

        elif stat.S_ISDIR(mode):
            self.str_(["type", "directory"])
            self._filter_and_serialize(fso)
        else:
            raise ValueError("unsupported file type")

        self.str_(")")
        if self.__debug:
            self.__indent -= 1

    def _serializeEntry(self, fso: Path) -> None:
        if self.__debug:
            self.__indent += 1
        self.str_(["entry", "(", "name", fso.name, "node"])
        self._serialize(fso)
        self.str_(")")
        if self.__debug:
            self.__indent -= 1

    def serialize(self, fso: Path) -> None:
        self.str_("nix-archive-1")
        self._serialize(fso)

    def _compute_result(self, convert_fn):
        return {
            hash_name: convert_fn(self.updater[hash_name].digest())
            for hash_name in self.hash_names
        }

    def digest(self) -> Dict[str, bytes]:
        """Compute the hash results with bytes format."""
        return self._compute_result(_identity)

    def hexdigest(self) -> Dict[str, str]:
        """Compute the hash results with hex format."""
        return self._compute_result(hash_to_hex)

    def b64digest(self) -> Dict[str, str]:
        """Compute the hash results with b64 format."""
        return self._compute_result(_convert_b64)

    def b32digest(self) -> Dict[str, str]:
        """Compute the hash results with b32 format."""
        return self._compute_result(_convert_b32)


def _identity(hsh: bytes) -> bytes:
    return hsh


def _convert_b64(hsh: str) -> str:
    hsh_hex = hash_to_hex(hsh)
    return base64.b64encode(bytes.fromhex(hsh_hex)).decode()


def _convert_b32(hsh: str) -> str:
    hsh_hex = hash_to_hex(hsh)
    return base64.b32encode(bytes.fromhex(hsh_hex)).decode().lower()


@swh_cli_group.command(name="nar", context_settings=CONTEXT_SETTINGS)
@click.argument("directory")
@click.option(
    "--exclude-vcs",
    "-x",
    help="Exclude version control directories",
    is_flag=True,
)
@click.option(
    "--vcs-type",
    "-t",
    help="Type of version control system to exclude directories",
    default="git",
)
@click.option(
    "--hash-algo",
    "-H",
    "hash_names",
    multiple=True,
    default=["sha256"],
    type=click.Choice(["sha256", "sha1"]),
)
@click.option(
    "--format-output",
    "-f",
    default="hex",
    type=click.Choice(["hex", "base32", "base64"], case_sensitive=False),
)
@click.option("--debug/--no-debug", default=lambda: os.environ.get("DEBUG", False))
def cli(exclude_vcs, vcs_type, directory, hash_names, format_output, debug):
    """Compute NAR hashes on a directory."""

    nar = Nar(hash_names, format_output, exclude_vcs, vcs_type, debug=debug)

    convert_fn = {
        "base64": nar.b64digest,
        "base32": nar.b32digest,
        "hex": nar.hexdigest,
    }

    nar.serialize(directory)
    result = convert_fn[format_output]()

    if len(hash_names) == 1:
        print(result[hash_names[0]])
    else:
        print(result)
