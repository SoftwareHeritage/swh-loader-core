# Copyright (C) 2022-2025  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import gzip
import logging
import os
import string
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple, cast

import attr
import chardet
import yaml

from swh.loader.core.utils import EMPTY_AUTHOR, get_url_body, release_name
from swh.loader.package.loader import (
    BasePackageInfo,
    PackageLoader,
    RawExtrinsicMetadataCore,
)
from swh.model import from_disk
from swh.model.model import (
    MetadataAuthority,
    MetadataAuthorityType,
    ObjectType,
    Person,
    Release,
    Sha1Git,
    TimestampWithTimezone,
)
from swh.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


@attr.s
class RubyGemsPackageInfo(BasePackageInfo):
    name = attr.ib(type=str)
    """Name of the package"""

    version = attr.ib(type=str)
    """Current version"""

    built_at = attr.ib(type=Optional[TimestampWithTimezone])
    """Version build date"""

    sha256 = attr.ib(type=str)
    """Extid as sha256"""

    MANIFEST_FORMAT = string.Template(
        "name $name\nshasum $sha256\nurl $url\nversion $version\nlast_update $built_at"
    )
    EXTID_TYPE = "rubygems-manifest-sha256"
    EXTID_VERSION = 0


class RubyGemsLoader(PackageLoader[RubyGemsPackageInfo]):
    """Load ``.gem`` files from ``RubyGems.org`` into the SWH archive."""

    visit_type = "rubygems"

    def __init__(
        self,
        storage: StorageInterface,
        url: str,
        artifacts: List[Dict[str, Any]],
        rubygem_metadata: List[Dict[str, Any]],
        max_content_size: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(storage, url, max_content_size=max_content_size, **kwargs)
        # Lister URLs are in the ``https://rubygems.org/gems/{pkgname}`` format
        assert url.startswith("https://rubygems.org/gems/"), (
            "Expected rubygems.org url, got '%s'" % url
        )
        # Convert list of artifacts and rubygem_metadata to a mapping of version
        self.artifacts: Dict[str, Dict] = {
            artifact["version"]: artifact for artifact in artifacts
        }
        self.rubygem_metadata: Dict[str, Dict] = {
            data["version"]: data for data in rubygem_metadata
        }

    def get_versions(self) -> Sequence[str]:
        """Return all versions sorted for the gem being loaded"""
        return list(self.artifacts)

    def get_metadata_authority(self):
        return MetadataAuthority(
            type=MetadataAuthorityType.FORGE,
            url="https://rubygems.org/",
        )

    def _load_directory(
        self, dl_artifacts: List[Tuple[str, Mapping[str, Any]]], tmpdir: str
    ) -> Tuple[str, from_disk.Directory]:
        """Override the directory loading to point it to the actual code.

        Gem files are uncompressed tarballs containing:
            - ``metadata.gz``: the metadata about this gem
            - ``data.tar.gz``: the code and possible binary artifacts
            - ``checksums.yaml.gz``: checksums
        """
        logger.debug("Unpacking gem file to point to the actual code")
        uncompressed_path = self.uncompress(dl_artifacts, dest=tmpdir)
        source_code_tarball = os.path.join(uncompressed_path, "data.tar.gz")
        return super()._load_directory(
            [(source_code_tarball, {})], os.path.join(tmpdir, "data")
        )

    def get_package_info(
        self, version: str
    ) -> Iterator[Tuple[str, RubyGemsPackageInfo]]:
        artifact = self.artifacts[version]
        rubygem_metadata = self.rubygem_metadata[version]
        filename = artifact["filename"]
        gem_name = filename.split(f"-{version}.gem")[0]
        checksums = artifact["checksums"]

        # Get extrinsic metadata
        extrinsic_metadata_url = rubygem_metadata["extrinsic_metadata_url"]
        extrinsic_metadata = get_url_body(extrinsic_metadata_url)

        p_info = RubyGemsPackageInfo(
            url=artifact["url"],
            filename=filename,
            version=version,
            built_at=TimestampWithTimezone.from_iso8601(rubygem_metadata["date"]),
            name=gem_name,
            checksums=checksums,  # sha256 checksum
            sha256=checksums["sha256"],  # sha256 for EXTID
            directory_extrinsic_metadata=[
                RawExtrinsicMetadataCore(
                    format="rubygem-release-json",
                    metadata=extrinsic_metadata,
                ),
            ],
        )
        yield release_name(version), p_info

    def extract_authors_from_metadata(self, metadata_bytes: bytes) -> List[Person]:
        def gem_spec_constructor(loader, node):
            # discard not used metadata fields to simplify yaml parsing
            # and avoid issues
            filtered_nodes = []
            for child_nodes in node.value:
                if child_nodes[0].value in ("authors", "email"):
                    filtered_nodes.append(child_nodes)

            return loader.construct_mapping(
                yaml.MappingNode(tag=node.tag, value=filtered_nodes)
            )

        # need to add such constructor or yaml parsing fails
        yaml.add_constructor("!ruby/object:Gem::Specification", gem_spec_constructor)

        try:
            # try to decode from utf-8 first
            text = metadata_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # detect encoding with chardet otherwise
            result = chardet.detect(metadata_bytes)
            text = metadata_bytes.decode(
                cast(str, result.get("encoding", "utf-8")), "backslashreplace"
            )

        try:
            metadata = yaml.load(text, Loader=yaml.Loader)
        except yaml.error.YAMLError:
            return []

        persons = []
        # extract authors list from metadata
        authors = metadata.get("authors", [])
        if authors and isinstance(authors[0], list):
            # some gems metadata have malformed authors field with nested lists
            authors = authors[0]
        # extract authors emails
        email = metadata.get("email", "")
        if isinstance(email, str):
            # email can be a string
            emails = email.split(",")
        else:
            # or a list
            emails = email

        for i, author in enumerate(authors):
            if not author:
                continue

            try:
                # check if author name has characters non ascii encodable
                author.encode("ascii")
            except UnicodeEncodeError:
                try:
                    # some gem metadata have authors list containing string with
                    # hex-digits Unicode code point:
                    #
                    # authors:
                    # - Scott Chacon
                    # - "Mislav Marohni\xC4\x87"
                    # - Flurin Egger
                    #
                    # we need to encode such string with raw-unicode-escape codec
                    # in order to properly decode it to utf-8
                    author = author.encode("raw-unicode-escape").decode()
                except UnicodeDecodeError:
                    # string was already utf-8 encoded
                    pass

            persons.append(
                Person.from_dict(
                    {
                        "name": author.strip().encode(),
                        "email": (
                            emails[i].strip().encode()
                            # co-author emails are not always available
                            if emails and len(emails) > i and emails[i]
                            else None
                        ),
                    }
                )
            )
        return persons

    def build_release(
        self, p_info: RubyGemsPackageInfo, uncompressed_path: str, directory: Sha1Git
    ) -> Optional[Release]:

        persons = []
        author = EMPTY_AUTHOR
        # metadata.gz was previously extracted from the gem file
        metadata_path = os.path.join(uncompressed_path, "../../src/metadata.gz")
        if os.path.exists(metadata_path):
            with gzip.open(metadata_path) as metadata_stream:

                metadata_bytes = metadata_stream.read()

                # store gem YAML metadata as raw extrinsic metadata as it is not
                # bundled in the data.tar.gz tarball containing ruby code plus it
                # contains more info about the gem than the JSON metadata fetched
                # from rubygems REST API
                p_info.directory_extrinsic_metadata.append(
                    RawExtrinsicMetadataCore(
                        format="rubygem-release-yaml",
                        metadata=metadata_bytes,
                    )
                )

                persons = self.extract_authors_from_metadata(metadata_bytes)

        if persons:
            author = persons[0]

        msg = (
            f"Synthetic release for RubyGems source package {p_info.name} "
            f"version {p_info.version}\n"
        )

        if len(persons) > 1:
            msg += "\n"
            for person in persons[1:]:
                msg += f"Co-authored-by: {person.fullname.decode()}\n"

        return Release(
            name=p_info.version.encode(),
            message=msg.encode(),
            date=p_info.built_at,
            author=author,
            target_type=ObjectType.DIRECTORY,
            target=directory,
            synthetic=True,
        )
