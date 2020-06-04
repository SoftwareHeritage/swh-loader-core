# Copyright (C) 2019  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import os
import logging

from typing import Any, Dict, Generator, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse
from pkginfo import UnpackedSDist

from swh.model.model import (
    Person,
    Sha1Git,
    TimestampWithTimezone,
    Revision,
    RevisionType,
)

from swh.loader.package.loader import PackageLoader
from swh.loader.package.utils import api_info, release_name, EMPTY_AUTHOR

logger = logging.getLogger(__name__)


class PyPILoader(PackageLoader):
    """Load pypi origin's artifact releases into swh archive.

    """

    visit_type = "pypi"

    def __init__(self, url):
        super().__init__(url=url)
        self._info = None
        self.provider_url = pypi_api_url(self.url)

    @property
    def info(self) -> Dict:
        """Return the project metadata information (fetched from pypi registry)

        """
        if not self._info:
            self._info = api_info(self.provider_url)
        return self._info

    def get_versions(self) -> Sequence[str]:
        return self.info["releases"].keys()

    def get_default_version(self) -> str:
        return self.info["info"]["version"]

    def get_package_info(
        self, version: str
    ) -> Generator[Tuple[str, Mapping[str, Any]], None, None]:
        res = []
        for meta in self.info["releases"][version]:
            if meta["packagetype"] != "sdist":
                continue
            filename = meta["filename"]
            p_info = {
                "url": meta["url"],
                "filename": filename,
                "raw": meta,
            }
            res.append((version, p_info))

        if len(res) == 1:
            version, p_info = res[0]
            yield release_name(version), p_info
        else:
            for version, p_info in res:
                yield release_name(version, p_info["filename"]), p_info

    def resolve_revision_from(
        self, known_artifacts: Dict, artifact_metadata: Dict
    ) -> Optional[bytes]:
        return artifact_to_revision_id(known_artifacts, artifact_metadata)

    def build_revision(
        self, a_metadata: Dict, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Revision]:
        i_metadata = extract_intrinsic_metadata(uncompressed_path)
        if not i_metadata:
            return None

        # from intrinsic metadata
        name = i_metadata["version"]
        _author = author(i_metadata)

        # from extrinsic metadata
        message = a_metadata.get("comment_text", "")
        message = "%s: %s" % (name, message) if message else name
        date = TimestampWithTimezone.from_iso8601(a_metadata["upload_time"])

        return Revision(
            type=RevisionType.TAR,
            message=message.encode("utf-8"),
            author=_author,
            date=date,
            committer=_author,
            committer_date=date,
            parents=(),
            directory=directory,
            synthetic=True,
            metadata={
                "intrinsic": {"tool": "PKG-INFO", "raw": i_metadata,},
                "extrinsic": {
                    "provider": self.provider_url,
                    "when": self.visit_date.isoformat(),
                    "raw": a_metadata,
                },
            },
        )


def artifact_to_revision_id(
    known_artifacts: Dict, artifact_metadata: Dict
) -> Optional[bytes]:
    """Given metadata artifact, solves the associated revision id.

    The following code allows to deal with 2 metadata formats (column metadata
    in 'revision')

    - old format sample::

        {
            'original_artifact': {
                'sha256': '6975816f2c5ad4046acc676ba112f2fff945b01522d63948531f11f11e0892ec',  # noqa
                ...
            },
            ...
        }

    - new format sample::

        {
            'original_artifact': [{
                'checksums': {
                    'sha256': '6975816f2c5ad4046acc676ba112f2fff945b01522d63948531f11f11e0892ec',  # noqa
                    ...
                },
            }],
            ...
        }

    """
    sha256 = artifact_metadata["digests"]["sha256"]
    for rev_id, known_artifact in known_artifacts.items():
        original_artifact = known_artifact["original_artifact"]
        if isinstance(original_artifact, dict):
            # previous loader-pypi version stored metadata as dict
            original_sha256 = original_artifact["sha256"]
            if sha256 == original_sha256:
                return rev_id
            continue
        # new pypi loader actually store metadata dict differently...
        assert isinstance(original_artifact, list)
        # current loader-pypi stores metadata as list of dict
        for original_artifact in known_artifact["original_artifact"]:
            if sha256 == original_artifact["checksums"]["sha256"]:
                return rev_id
    return None


def pypi_api_url(url: str) -> str:
    """Compute api url from a project url

    Args:
        url (str): PyPI instance's url (e.g: https://pypi.org/project/requests)
        This deals with correctly transforming the project's api url (e.g
        https://pypi.org/pypi/requests/json)

    Returns:
        api url

    """
    p_url = urlparse(url)
    project_name = p_url.path.rstrip("/").split("/")[-1]
    url = "%s://%s/pypi/%s/json" % (p_url.scheme, p_url.netloc, project_name)
    return url


def extract_intrinsic_metadata(dir_path: str) -> Dict:
    """Given an uncompressed path holding the pkginfo file, returns a
       pkginfo parsed structure as a dict.

       The release artifact contains at their root one folder. For example:
       $ tar tvf zprint-0.0.6.tar.gz
       drwxr-xr-x root/root         0 2018-08-22 11:01 zprint-0.0.6/
       ...

    Args:

        dir_path (str): Path to the uncompressed directory
                        representing a release artifact from pypi.

    Returns:
        the pkginfo parsed structure as a dict if any or None if
        none was present.

    """
    # Retrieve the root folder of the archive
    if not os.path.exists(dir_path):
        return {}
    lst = os.listdir(dir_path)
    if len(lst) != 1:
        return {}
    project_dirname = lst[0]
    pkginfo_path = os.path.join(dir_path, project_dirname, "PKG-INFO")
    if not os.path.exists(pkginfo_path):
        return {}
    pkginfo = UnpackedSDist(pkginfo_path)
    raw = pkginfo.__dict__
    raw.pop("filename")  # this gets added with the ondisk location
    return raw


def author(data: Dict) -> Person:
    """Given a dict of project/release artifact information (coming from
       PyPI), returns an author subset.

    Args:
        data (dict): Representing either artifact information or
                     release information.

    Returns:
        swh-model dict representing a person.

    """
    name = data.get("author")
    email = data.get("author_email")
    fullname = None  # type: Optional[str]

    if email:
        fullname = "%s <%s>" % (name, email)
    else:
        fullname = name

    if not fullname:
        return EMPTY_AUTHOR

    if name is not None:
        name = name.encode("utf-8")

    if email is not None:
        email = email.encode("utf-8")

    return Person(fullname=fullname.encode("utf-8"), name=name, email=email)
