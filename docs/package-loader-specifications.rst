.. _package-loader-specifications:

Package loader specifications
=============================

Release fields
--------------

Here is an overview of the fields (+ internal version name + branch name) used by each package loader, after D6616:

.. list-table:: Fields used by each package loader
   :header-rows: 1

   * - Loader
     - internal version
     - branch name
     - name
     - message
     - synthetic
     - author
     - date
     - Notes
   * - archive
     - passed as arg
     - ``release_name(​version)``
     - =version
     - "swh-loader-package:
       synthetic revision message"
     - true
     - SWH robot
     - passed as arg
     -
   * - cran
     - ``metadata.get(​"Version", passed as arg)``
     - ``release_name(​version)``
     - =version
     - =version
     - true
     - ``metadata.get(​"Maintainer", "")``
     - ``metadata.get(​"Date")``
     - metadata is intrinsic
   * - debian
     - passed as arg (eg. ``stretch/contrib/0.7.2-3``)
     - ``release_name(​version)``
     - =version
     - "Synthetic revision for Debian source package %s version %s"
     - true
     - ``metadata​.changelog​.person``
     - ``metadata​.changelog​.date``
     - metadata is intrinsic. Old revisions have ``dsc`` as type
   * - deposit
     - HEAD
     - only HEAD
     - HEAD
     - "{client}: Deposit {id} in collection {collection}"
     - true
     - SWH robot
     - ``<codemeta: dateCreated>`` from SWORD XML
     - revisions had parents
   * - nixguix
     - URL
     - URL
     - URL
     - ""
     - true
     - ""
     - None
     - it's the URL of the artifact referenced by the derivation
   * - npm
     - ``metadata​["version"]``
     - ``release_name(​version)``
     - =version
     - =version
     - true
     - from int metadata or ""
     - from ext metadata or None
     -
   * - opam
     - as given by opam
     - "{opam_package}​.{version}"
     - =version
     - =version
     - true
     - from metadata
     - None
     - "{self.opam_package}​.{version}" matches the version names used by opam's backend. metadata is extrinsic
   * - pypi
     - ``metadata​["version"]``
     - ``release_name(​version)`` or ``release_name(​version, filename)``
     - =version
     - "{version}: {metadata[​'comment_text']}" or just version
     - true
     - from int metadata or ""
     - from ext metadata or None
     - metadata is intrinsic

using this function::

    def release_name(version: str, filename: Optional[str] = None) -> str:
        if filename:
            return "releases/%s/%s" % (version, filename)
        return "releases/%s" % version


The ``target_type`` field is always ``dir``, and the target the id of a directory
loaded by unpacking a tarball/zip file/...
