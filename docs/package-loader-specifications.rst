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
     - "Synthetic release for archive at {p_info.url}\n"
     - true
     - ""
     - passed as arg
     -
   * - cran
     - ``metadata.get(​"Version", passed as arg)``
     - ``release_name(​version)``
     - =version
     - standard message
     - true
     - ``metadata.get(​"Maintainer", "")``
     - ``metadata.get(​"Date")``
     - metadata is intrinsic
   * - debian
     - =``version``
     - ``release_name(​version)``
     - =``i_version``
     - standard message (using ``i_version``)
     - true
     - ``metadata​.changelog​.person``
     - ``metadata​.changelog​.date``
     - metadata is intrinsic. Old revisions have ``dsc`` as type
       ``i_version`` is the intrinsic version (eg. ``0.7.2-3``) while ``version``
       contains the debian suite name (eg. ``stretch/contrib/0.7.2-3``) and is
       passed as arg
   * - deposit
     - HEAD
     - only HEAD
     - HEAD
     - "{client}: Deposit {id} in collection {collection}\n"
     - true
     - original author
     - ``<codemeta: dateCreated>`` from SWORD XML
     - revisions had parents
   * - maven-loader
     - passed as arg
     - HEAD
     - ``release_name(version)``
     - "Synthetic release for archive at {p_info.url}\n"
     - true
     - ""
     - passed as arg
     - Only one artefact per url (jar/zip src)
   * - nixguix
     - URL
     - URL
     - URL
     - None
     - true
     - ""
     - None
     - it's the URL of the artifact referenced by the derivation
   * - npm
     - ``metadata​["version"]``
     - ``release_name(​version)``
     - =version
     - standard message
     - true
     - from int metadata or ""
     - from ext metadata or None
     -
   * - opam
     - as given by opam
     - "{opam_package}​.{version}"
     - =version
     - standard message
     - true
     - from metadata
     - None
     - "{self.opam_package}​.{version}" matches the version names used by opam's backend. metadata is extrinsic
   * - pypi
     - ``metadata​["version"]``
     - ``release_name(​version)`` or ``release_name(​version, filename)``
     - =version
     - ``metadata[​'comment_text']}`` or standard message
     - true
     - from int metadata or ""
     - from ext metadata or None
     - metadata is intrinsic

using this function::

    def release_name(version: str, filename: Optional[str] = None) -> str:
        if filename:
            return "releases/%s/%s" % (version, filename)
        return "releases/%s" % version

and "standard message" being::

    msg = (
        f"Synthetic release for {PACKAGE_MANAGER} source package {name} "
        f"version {version}\n"
    )


The ``target_type`` field is always ``dir``, and the target the id of a directory
loaded by unpacking a tarball/zip file/...
