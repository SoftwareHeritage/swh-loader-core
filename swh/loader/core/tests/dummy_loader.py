import datetime

from swh.loader.core.loader import BaseLoader
from swh.model.model import (
    MetadataAuthority,
    MetadataAuthorityType,
    MetadataFetcher,
    Origin,
    RawExtrinsicMetadata,
)

ORIGIN = Origin(url="some-url")
PARENT_ORIGIN = Origin(url="base-origin-url")

METADATA_AUTHORITY = MetadataAuthority(
    type=MetadataAuthorityType.FORGE, url="http://example.org/"
)
REMD = RawExtrinsicMetadata(
    target=ORIGIN.swhid(),
    discovery_date=datetime.datetime.now(tz=datetime.timezone.utc),
    authority=METADATA_AUTHORITY,
    fetcher=MetadataFetcher(
        name="test fetcher",
        version="0.0.1",
    ),
    format="test-format",
    metadata=b'{"foo": "bar"}',
)


class DummyLoader:
    """Base Loader to overload and simplify the base class (technical: to avoid repetition
    in other *Loader classes)"""

    visit_type = "git"

    def __init__(self, storage, *args, **kwargs):
        super().__init__(storage, ORIGIN.url, *args, **kwargs)

    def cleanup(self):
        pass

    def prepare(self, *args, **kwargs):
        pass

    def fetch_data(self):
        pass

    def get_snapshot_id(self):
        return None


class DummyBaseLoader(DummyLoader, BaseLoader):
    """Buffered loader will send new data when threshold is reached"""

    def store_data(self) -> None:
        pass


class DummyMetadataFetcher:
    SUPPORTED_LISTERS = {"fake-forge"}
    FETCHER_NAME = "fake-forge"

    def __init__(self, origin, credentials, lister_name, lister_instance_name):
        pass

    def get_origin_metadata(self):
        return [REMD]

    def get_parent_origins(self):
        return []


class DummyMetadataFetcherWithFork:
    SUPPORTED_LISTERS = {"fake-forge"}
    FETCHER_NAME = "fake-forge"

    def __init__(self, origin, credentials, lister_name, lister_instance_name):
        pass

    def get_origin_metadata(self):
        return [REMD]

    def get_parent_origins(self):
        return [PARENT_ORIGIN]


class FooLoader(BaseLoader):
    visit_type = "foo"

    def __init__(self, *args, foo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.foo = foo


class BarLoader(BaseLoader):
    visit_type = "bar"
