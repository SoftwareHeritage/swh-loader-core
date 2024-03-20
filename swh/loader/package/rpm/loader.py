# Copyright (C) 2022-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from __future__ import annotations

import json
import logging
from os import path, walk
import string
import subprocess
import tempfile
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

import attr

from swh.core.tarball import uncompress
from swh.loader.core.utils import EMPTY_AUTHOR, cached_method, release_name
from swh.loader.package.loader import BasePackageInfo, PackageLoader
from swh.model import from_disk
from swh.model.model import ObjectType, Release, Sha1Git, TimestampWithTimezone
from swh.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


@attr.s
class RpmPackageInfo(BasePackageInfo):
    name = attr.ib(type=str)
    intrinsic_version = attr.ib(type=str)
    """Intrinsic version of the package, independent from the distribution (e.g. 1.18.0-5)"""
    build_time = attr.ib(type=str, default=None)
    """Build time of the package in iso format. (e.g. 2017-02-10T04:59:31+00:00)"""
    checksums_str = attr.ib(type=str, default=None)

    EXTID_TYPE = "rpm-sha256"
    MANIFEST_FORMAT = string.Template("$name $intrinsic_version $checksums_str")

    @classmethod
    def from_metadata(cls, a_metadata: Dict[str, Any], version: str) -> RpmPackageInfo:
        filename = a_metadata["url"].split("/")[-1]
        assert filename.endswith(".rpm")

        return cls(
            name=a_metadata["name"],  # nginx
            url=a_metadata["url"],  # url of the .rpm file
            filename=filename,  # nginx-1.18.0-5.fc34.src.rpm
            version=version,  # 34/Everything/1.18.0-5
            intrinsic_version=a_metadata["version"],  # 1.18.0-5
            build_time=a_metadata["build_time"],
            checksums=a_metadata["checksums"],
            checksums_str=json.dumps(a_metadata["checksums"], sort_keys=True),
        )


class RpmLoader(PackageLoader[RpmPackageInfo]):
    visit_type = "rpm"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        packages: Dict[str, Dict[str, Any]],
        **kwargs: Any,
    ):
        """RPM Loader implementation.

        Args:
            url: Origin url (e.g. rpm://Fedora/packages/nginx)
            packages: versioned packages and associated artifacts, example::

              {
                '34/Everything/1.18.0-5': {
                  'name': 'nginx',
                  'version': '1.18.0-5',
                  'release': 34,
                  'edition': 'Everything',
                  'build_time': '2022-11-01T12:00:55+00:00',
                  'url': 'https://archives.fedoraproject.org/nginx-1.18.0-5.fc34.src.rpm',
                  'checksums': {
                    'sha256': 'ac68fa26886c661b77bfb97bbe234a6c37d36a16c1eca126eabafbfc7fcb',
                  }
                },
                # ...
              }

        """
        super().__init__(storage=storage, url=url, **kwargs)
        self.url = url
        self.packages = packages
        self.tarball_branches: Dict[bytes, Mapping[str, Any]] = {}

    @cached_method
    def get_versions(self) -> Sequence[str]:
        """Returns the package versions sorted by build time"""
        return list(sorted(self.packages, key=lambda p: self.packages[p]["build_time"]))

    def get_default_version(self) -> str:
        """Get the latest release version of a rpm package"""
        return self.get_versions()[-1]

    def get_package_info(self, version: str) -> Iterator[Tuple[str, RpmPackageInfo]]:
        yield (
            release_name(version),
            RpmPackageInfo.from_metadata(self.packages[version], version),
        )

    def uncompress(
        self, dl_artifacts: List[Tuple[str, Mapping[str, Any]]], dest: str
    ) -> str:
        rpm_path, _ = dl_artifacts[0]
        return extract_rpm_package(rpm_path, dest=dest)

    def build_release(
        self, p_info: RpmPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:
        # extract tarballs that might be located in the root directory of the rpm
        # package and adds a dedicated branch for it in the snapshot
        root, _, files = next(walk(uncompressed_path))
        for file in files:
            file_path = path.join(root, file)
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    uncompress(file_path, tmpdir)
                except Exception:
                    # not a tarball
                    continue

                tarball_dir = from_disk.Directory.from_disk(
                    path=tmpdir.encode("utf-8"),
                    max_content_length=self.max_content_size,
                )

                contents, skipped_contents, directories = from_disk.iter_directory(
                    tarball_dir
                )
                self.storage.skipped_content_add(skipped_contents)
                self.storage.content_add(contents)
                self.storage.directory_add(directories)

                self.tarball_branches[file.encode()] = {
                    "target_type": "directory",
                    "target": tarball_dir.hash,
                }

        msg = (
            f"Synthetic release for RPM source package {p_info.name} "
            f"version {p_info.intrinsic_version}\n"
        )

        return Release(
            name=p_info.intrinsic_version.encode(),
            message=msg.encode(),
            author=EMPTY_AUTHOR,
            date=TimestampWithTimezone.from_iso8601(p_info.build_time),
            target=directory,
            target_type=ObjectType.DIRECTORY,
            synthetic=True,
        )

    def extra_branches(self) -> Dict[bytes, Mapping[str, Any]]:
        return self.tarball_branches


def extract_rpm_package(rpm_path: str, dest: str) -> str:
    """Extracts an RPM package."""
    logger.debug("rpm path: %s", rpm_path)
    if not path.exists(rpm_path):
        raise FileNotFoundError(f"RPM package {rpm_path} not found")

    destdir = path.join(dest, "extracted")
    logfile = path.join(dest, "extract.log")
    logger.debug(
        "extract RPM source package %s in %s" % (rpm_path, destdir),
        extra={
            "swh_type": "rpm_extract",
            "swh_rpm": rpm_path,
            "swh_destdir": destdir,
        },
    )

    try:
        with open(logfile, "w") as stdout:
            rpm2cpio = subprocess.Popen(
                ("rpm2cpio", rpm_path), stdout=subprocess.PIPE, stderr=stdout
            )
            subprocess.check_call(
                ("cpio", "-idmv", "-D", destdir),
                stdin=rpm2cpio.stdout,
                stdout=stdout,
                stderr=stdout,
            )
            rpm2cpio.wait()

    except subprocess.CalledProcessError as e:
        logdata = open(logfile, "r").read()
        raise ValueError(
            "rpm2cpio | cpio exited with code %s: %s" % (e.returncode, logdata)
        ) from None

    return destdir
