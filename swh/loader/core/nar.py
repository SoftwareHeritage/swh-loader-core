# Copyright (C) 2022 zimoun and the Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import base64
import hashlib
import io
import os
from pathlib import Path
import stat
from typing import Callable

import click

from swh.core.cli import CONTEXT_SETTINGS
from swh.core.cli import swh as swh_cli_group

CHUNK_SIZE = 65536


class Nar:
    """NAR serializer.

    This builds the NAR structure and serializes it as per the phd thesis from Eelco
    Dolstra thesis.

    For example, this tree on a filesystem:

    :: code:

       $ tree foo
       foo
       ├── bar
       │   └── exe
       └── baz

       1 directory, 2 files

    serializes as:

    :: code:

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
                 <_io.BufferedReader name='foo/bar/exe'>
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
             <_io.BufferedReader name='foo/baz'>
            )
          )
        )

    """

    def __init__(self, exclude_vcs: bool, updater: Callable, debug: bool = False):
        self.exclude_vcs = exclude_vcs
        self.updater_fn = updater

        self.__debug = debug
        self.__indent = 0

    def str_(self, thing):
        """Compute the nar serialization format on 'thing' and compute its hash."""
        # named 'str' in Figure 5.2 p.93 (page 101 of pdf)

        if self.__debug and isinstance(thing, (str, io.BufferedReader)):
            indent = "".join(["  " for _ in range(self.__indent)])
            print(indent + str(thing))

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
        self.updater_fn(blen)

        # first part of 'pad'
        if isinstance(thing, str):
            self.updater_fn(byte_sequence)
        elif isinstance(thing, io.BufferedReader):
            for chunk in iter(lambda: thing.read(CHUNK_SIZE), b""):
                self.updater_fn(chunk)

        # second part of 'pad
        m = length % 8
        if m == 0:
            offset = 0
        else:
            offset = 8 - m
        boffset = bytearray(offset)
        self.updater_fn(boffset)

    def _filter_and_serialize(self, fso: Path) -> None:
        """On the first level of the main tree, we may have to skip some paths (e.g.
        .git, ...). Once those are ignored, we can serialize the remaining part of the
        entries.

        """
        for path in sorted(Path(fso).iterdir()):
            ignore = False
            for path_to_ignore in self.__paths_to_ignore:
                if path.match(path_to_ignore):  # Ignore specific folder
                    ignore = True
                    break
            if not ignore:
                self._serializeEntry(path)

    def _only_serialize(self, fso: Path) -> None:
        """Every other level of the nested tree, we do not have to check for any path so
        we can just serialize the entries of the tree.

        """
        for path in sorted(Path(fso).iterdir()):
            self._serializeEntry(path)

    def _serialize(self, fso: Path, first_level: bool = False):
        if self.__debug:
            self.__indent += 1
        self.str_("(")

        mode = os.lstat(fso).st_mode

        if stat.S_ISREG(mode):
            self.str_(["type", "regular"])
            if os.access(fso, os.X_OK):
                self.str_(["executable", ""])
            self.str_("contents")
            with fso.open("rb") as f:
                self.str_(f)

        elif stat.S_ISLNK(mode):
            self.str_(["type", "symlink", "target"])
            self.str_(os.readlink(fso))

        elif stat.S_ISDIR(mode):
            self.str_(["type", "directory"])
            serialize_fn = (
                self._filter_and_serialize if first_level else self._only_serialize
            )
            serialize_fn(fso)

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
        self.__paths_to_ignore = (
            [f"{fso}/{folder}" for folder in [".git", ".hg", ".svn"]]
            if self.exclude_vcs
            else []
        )
        self._serialize(fso, first_level=True)
        return


@swh_cli_group.command(name="nar", context_settings=CONTEXT_SETTINGS)
@click.argument("directory")
@click.option(
    "--exclude-vcs", "-x", help="exclude version control directories", is_flag=True
)
@click.option(
    "--hash-algo", "-H", default="sha256", type=click.Choice(["sha256", "sha1"])
)
@click.option(
    "--format-output",
    "-f",
    default="hex",
    type=click.Choice(["hex", "base32", "base64"], case_sensitive=False),
)
@click.option("--debug/--no-debug", default=lambda: os.environ.get("DEBUG", False))
def cli(exclude_vcs, directory, hash_algo, format_output, debug):
    """Compute NAR hashes on a directory."""
    h = hashlib.sha256() if hash_algo == "sha256" else hashlib.sha1()
    updater = h.update
    format_output = format_output.lower()

    def identity(hsh):
        return hsh

    def convert_b64(hsh: str):
        return base64.b64encode(bytes.fromhex(hsh)).decode().lower()

    def convert_b32(hsh: str):
        return base64.b32encode(bytes.fromhex(hsh)).decode().lower()

    convert_fn = {
        "hex": identity,
        "base64": convert_b64,
        "base32": convert_b32,
    }

    nar = Nar(exclude_vcs, updater, debug=debug)
    nar.serialize(directory)
    print(convert_fn[format_output](h.hexdigest()))
