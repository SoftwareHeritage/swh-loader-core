# Copyright (C) 2019  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from swh.core.config import SWHConfig
from swh.model.from_disk import Directory
from swh.model.identifiers import (
    revision_identifier, snapshot_identifier,
    identifier_to_bytes, normalize_timestamp
)
from swh.storage import get_storage


class PackageLoader:
    visit = None
    """origin visit attribute (dict) set at the beginning of the load method

    """

    def __init__(self, url, visit_type, visit_date=None):
        """Loader's constructor. This raises exception if the minimal required
           configuration is missing (cf. fn:`check` method).

        Args:
            url (str): Origin url to load data from
            visit_type (str): Loader's visit type (git, svn, tar, pypi, npm,
                              etc...)
            visit_date (Optional[str]): visit date to set, default to now

        """
        self.config = SWHConfig.parse_config_file()
        self.storage = get_storage(**self.config['storage'])
        # FIXME: No more configuration documentation
        # Implicitely, this uses the SWH_CONFIG_FILENAME environment variable
        # loading mechanism
        # FIXME: Prepare temp folder to uncompress archives

        # Once and for all, the following are mandatory
        self.origin = {'url': url, 'type': visit_type}
        self.visit_type = visit_type
        if not visit_date:  # now as default visit_date if not provided
            visit_date = datetime.datetime.now(tz=datetime.timezone.utc)
        if isinstance(visit_date, str):
            visit_date = None  # FIXME: parse the visit_date
        self.visit_date = visit_date

        self.check()

    def check(self):
        """Checks the minimal configuration required is set for the loader.

        If some required configuration is missing, exception detailing the
        issue is raised.

        """
        if not 'storage' in self.config:
            raise ValueError(
                'Misconfiguration, at least the storage key should be set')
        if not hasattr(self, 'visit_type'):
            raise ValueError('Loader must have a visit_type set')
        if not hasattr(self, 'origin'):
            raise ValueError('Loader must have an origin dict set')

    def get_versions(self):
        """Return the list of all published package versions.

        """
        return []

    def retrieve_artifacts(self, version):
        """Given a release version of a package, retrieve the associated
           artifact for such version.

        Args:
            version (str): Package version

        Returns:
            xxx

        """
        pass

    def uncompress_artifact_archive(self, artifact_archive_path):
        """Uncompress artifact archive to a temporary folder and returns its
           path.

        Args:
            artifact_archive_path (str): Path to artifact archive to uncompress

        Returns:
            the uncompressed artifact path (str)

        """
        pass

    def get_project_metadata(self, artifact):
        """Given an artifact dict, extract the relevant project metadata.
           Those will be set within the revision's metadata built

        Args:
            artifact (dict): A dict of metadata about a release artifact.

        Returns:
            dict of relevant project metadata (e.g, in pypi loader:
            {'project_info': {...}})

        """
        return {}

    def get_revision_metadata(self, artifact):
        """Given an artifact dict, extract the relevant revision metadata.
           Those will be set within the 'name' (bytes) and 'message' (bytes)
           built revision fields.

        Args:
            artifact (dict): A dict of metadata about a release artifact.

        Returns:
            dict of relevant revision metadata (name, message keys with values
            as bytes)

        """
        pass

    def get_revision_parents(self, version, artifact):
        """Build the revision parents history if any

        Args:
            version (str): A version string as string (e.g. "0.0.1")
            artifact (dict): A dict of metadata about a release artifact.

        Returns:
            List of revision ids representing the new revision's parents.

        """
        return []

    def load(self):
        """Load for a specific origin the associated contents.

        for each package version of the origin

        1. Fetch the files for one package version By default, this can be
           implemented as a simple HTTP request. Loaders with more specific
           requirements can override this, e.g.: the PyPI loader checks the
           integrity of the downloaded files; the Debian loader has to download
           and check several files for one package version.

        2. Extract the downloaded files By default, this would be a universal
           archive/tarball extraction.

           Loaders for specific formats can override this method (for instance,
           the Debian loader uses dpkg-source -x).

        3. Convert the extracted directory to a set of Software Heritage
           objects Using swh.model.from_disk.

        4. Extract the metadata from the unpacked directories This would only
           be applicable for "smart" loaders like npm (parsing the
           package.json), PyPI (parsing the PKG-INFO file) or Debian (parsing
           debian/changelog and debian/control).

           On "minimal-metadata" sources such as the GNU archive, the lister
           should provide the minimal set of metadata needed to populate the
           revision/release objects (authors, dates) as an argument to the
           task.

        5. Generate the revision/release objects for the given version. From
           the data generated at steps 3 and 4.

        end for each

        6. Generate and load the snapshot for the visit

        Using the revisions/releases collected at step 5., and the branch
        information from step 0., generate a snapshot and load it into the
        Software Heritage archive

        """
        status_load = 'uneventful'  # either: eventful, uneventful, failed
        status_visit = 'partial'    # either: partial, full
        tmp_revisions = {}

        # Prepare origin and origin_visit (method?)
        origin = self.storage.origin_add([self.origin])[0]
        visit = self.storage.origin_visit_add(
            origin=origin, date=self.visit_date, type=self.visit_type)['visit']

        # Retrieve the default release (the "latest" one)
        default_release = self.get_default_release()
        for version in self.get_versions():  # for each
            tmp_revisions[version] = []
            for artifact in self.retrieve_artifacts(version):  # 1.
                artifact_path = self.uncompress_artifact_archive(
                    artifact['name'])  # 2.

                # 3. Collect directory information
                directory = Directory.from_disk(path=artifact_path, data=True)
                # FIXME: Try not to load the full raw content in memory
                objects = directory.collect()

                contents = objects['content'].values()
                self.storage.content_add(contents)

                status_load = 'eventful'
                directories = objects['directory'].values()
                self.storage.directory_add(directories)

                # 4. Parse metadata (project, artifact metadata)
                metadata = self.get_revision_metadata(artifact)

                # 5. Build revision
                name = metadata['name']
                message = metadata['message']
                if message:
                    # FIXME: IMSMW, that does not work on python3.5
                    message = b'%s: %s' % (name, message)
                else:
                    message = name

                revision = {
                    'synthetic': True,
                    'metadata': {
                        'original_artifact': artifact,
                        **self.get_metadata(artifact),
                    },
                    'author': metadata['author'],
                    'date': metadata['date'],
                    'committer': metadata['author'],
                    'committer_date': metadata['date'],
                    'message': message,
                    'directory': directory.hash,
                    'parents': self.get_revision_parents(version, artifact),
                    'type': 'tar',
                }

                revision['id'] = identifier_to_bytes(
                    revision_identifier(revision))
                self.storage.revision_add(revision)

                tmp_revisions[version].append[{
                    'filename': artifact['name'],
                    'target': revision['id'],
                }]

        # 6. Build and load the snapshot
        branches = {}
        for version, v_branches in tmp_revisions.items():
            if len(v_branches) == 1:
                branch_name = 'releases/%s' % version
                if version == default_release['version']:
                    branches[b'HEAD'] = {
                        'target_type': 'alias',
                        'target': branch_name.encode('utf-8'),
                    }

                branches[branch_name] = {
                    'target_type': 'revision',
                    'target': v_branches[0]['target'],
                }
            else:
                for x in v_branches:
                    branch_name = 'releases/%s/%s' % (
                        version, v_branches['filename'])
                    branches[branch_name] = {
                        'target_type': 'revision',
                        'target': x['target'],
                    }
        snapshot = {
            'branches': branches
        }
        snapshot['id'] = identifier_to_bytes(
            snapshot_identifier(snapshot))
        self.storage.snapshot_add([snapshot])

        # come so far, we actually reached a full visit
        status_visit = 'full'

        # Update the visit's state
        self.origin_visit_update(
            origin=self.origin,
            visit_id=self.visit['visit'],
            status=status_visit,
            snapshot=snapshot)

        return {'status': status_load}
