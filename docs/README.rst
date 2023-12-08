Software Heritage - Loader foundations
======================================

The Software Heritage Loader Core is a low-level loading utilities and
helpers used by `loaders <https://docs.softwareheritage.org/devel/glossary.html#term-loader>`_.

The main entry points are classes:

- `swh.loader.core.loader.BaseLoader <https://docs.softwareheritage.org/devel/apidoc/swh.loader.core.loader.html#swh.loader.core.loader.BaseLoader>`_
  for VCS loaders (e.g. git, svn, ...)

- `swh.loader.core.loader.ContentLoader <https://docs.softwareheritage.org/devel/apidoc/swh.loader.core.loader.html#swh.loader.core.loader.ContentLoader>`_
  for Content loader

- `swh.loader.core.loader.BaseDirectoryLoader <https://docs.softwareheritage.org/devel/apidoc/swh.loader.core.loader.html#swh.loader.core.loader.BaseDirectoryLoader>`_
  for Directory loaders

- `swh.loader.package.loader.PackageLoader <https://docs.softwareheritage.org/devel/apidoc/swh.loader.package.loader.html#swh.loader.package.loader.PackageLoader>`_
  for Package loaders (e.g. PyPI, Npm, ...)

Package loaders
---------------

This package also implements many package loaders directly, out of convenience,
as they usually are quite similar and each fits in a single file.

They all roughly follow these steps, explained in the
`swh.loader.package.loader.PackageLoader.load <https://docs.softwareheritage.org/devel/apidoc/swh.loader.package.loader.html#swh.loader.package.loader.PackageLoader.load>`_
documentation.
See the `Package Loader tutorial <https://docs.softwareheritage.org/devel/swh-loader-core/package-loader-tutorial.html#package-loader-tutorial>`_
for details.

VCS loaders
-----------

Unlike package loaders, VCS loaders remain in separate packages,
as they often need more advanced conversions and very VCS-specific operations.

This usually involves getting the branches of a repository and recursively loading
revisions in the history (and directory trees in these revisions),
until a known revision is found
