#!/usr/bin/env bash

# Script to generate fake Dart or FLutter packages archives as .tar.gz.

set -euo pipefail

# Create directories
readonly TMP=tmp_dir/pubdev
readonly BASE_ARCHIVES=https_pub.dartlang.org

mkdir -p $TMP
mkdir -p $BASE_ARCHIVES

# Dart package a pubspec.yaml file at thier root. Generate some of them.

mkdir -p ${TMP}/packages_authentication_versions_0.0.1
echo -e '''name: authentication
description: Persistent user authentication for Flutter with optional backend API integration.
version: 0.0.1
author:
homepage:

environment:
  sdk: ">=2.7.0 <3.0.0"
  flutter: ">=1.17.0 <2.0.0"

dependencies:
  flutter:
    sdk: flutter

dev_dependencies:
  flutter_test:
    sdk: flutter

# For information on the generic Dart part of this file, see the
# following page: https://dart.dev/tools/pub/pubspec

# The following section is specific to Flutter.
flutter:
  # This section identifies this Flutter project as a plugin project.
  # The 'pluginClass' and Android 'package' identifiers should not ordinarily
  # be modified. They are used by the tooling to maintain consistency when
  # adding or updating assets for this project.
  plugin:
    platforms:
    # This plugin project was generated without specifying any
    # platforms with the `--platform` argument. If you see the `fake_platform` map below, remove it and
    # then add platforms following the instruction here:
    # https://flutter.dev/docs/development/packages-and-plugins/developing-packages#plugin-platforms
    # -------------------
      some_platform:
        pluginClass: somePluginClass
    # -------------------

  # To add assets to your plugin package, add an assets section, like this:
  # assets:
  #   - images/a_dot_burr.jpeg
  #   - images/a_dot_ham.jpeg
  #
  # For details regarding assets in packages, see
  # https://flutter.dev/assets-and-images/#from-packages
  #
  # An image asset can refer to one or more resolution-specific "variants", see
  # https://flutter.dev/assets-and-images/#resolution-aware.

  # To add custom fonts to your plugin package, add a fonts section here,
  # in this "flutter" section. Each entry in this list should have a
  # "family" key with the font family name, and a "fonts" key with a
  # list giving the asset and other descriptors for the font. For
  # example:
  # fonts:
  #   - family: Schyler
  #     fonts:
  #       - asset: fonts/Schyler-Regular.ttf
  #       - asset: fonts/Schyler-Italic.ttf
  #         style: italic
  #   - family: Trajan Pro
  #     fonts:
  #       - asset: fonts/TrajanPro.ttf
  #       - asset: fonts/TrajanPro_Bold.ttf
  #         weight: 700
  #
  # For details regarding fonts in packages, see
  # https://flutter.dev/custom-fonts/#from-packages
''' > ${TMP}/packages_authentication_versions_0.0.1/pubspec.yaml


mkdir -p ${TMP}/packages_autolinker_versions_0.1.1
echo -e '''name: Autolinker
version: 0.1.1
author: hackcave <hackers@hackcave.org>
homepage: https://github.com/hackcave
description:
    Port of Autolinker.js to dart
''' > ${TMP}/packages_autolinker_versions_0.1.1/pubspec.yaml

mkdir -p ${TMP}/packages_bezier_versions_1.1.5
echo -e '''name: bezier
version: 1.1.5
authors:
  - Aaron Barrett <aaron@aaronbarrett.com>
  - Isaac Barrett <ikebart9999@gmail.com>
description: >-
  A 2D Bézier curve math library. Based heavily on the work of @TheRealPomax
  <pomax.github.io/bezierjs>.

  Live examples can be found at <www.dartographer.com/bezier>.
homepage: https://github.com/aab29/bezier.dart
environment:
  sdk: ">=2.0.0 <3.0.0"
dependencies:
  vector_math: ^2.0.0
dev_dependencies:
  test: ^1.0.0
''' > ${TMP}/packages_bezier_versions_1.1.5/pubspec.yaml

mkdir -p ${TMP}/packages_pdf_versions_1.0.0
echo -e '''name: pdf
author: David PHAM-VAN <dev.nfet.net@gmail.com>
description: A pdf producer for Dart
homepage: https://github.com/davbfr/dart_pdf
version: 1.0.0

environment:
  sdk: ">=1.8.0 <2.0.0"

dependencies:
  meta: "^1.1.5"
  ttf_parser: "^1.0.0"
  vector_math: "^2.0.7"

dev_dependencies:
  test: any
''' > ${TMP}/packages_pdf_versions_1.0.0/pubspec.yaml

mkdir -p ${TMP}/packages_pdf_versions_3.8.2
echo -e '''name: pdf
description: A pdf producer for Dart. It can create pdf files for both web or flutter.
homepage: https://github.com/DavBfr/dart_pdf/tree/master/pdf
repository: https://github.com/DavBfr/dart_pdf
issue_tracker: https://github.com/DavBfr/dart_pdf/issues
version: 3.8.2

environment:
  sdk: ">=2.12.0 <3.0.0"

dependencies:
  archive: ^3.1.0
  barcode: ">=2.2.0 <3.0.0"
  crypto: ^3.0.0
  image: ">=3.0.1 <4.0.0"
  meta: ">=1.3.0 <2.0.0"
  path_parsing: ">=0.2.0 <2.0.0"
  vector_math: ^2.1.0
  xml: ">=5.1.0 <7.0.0"

dev_dependencies:
  flutter_lints: ^1.0.4
  test: ">=1.16.0 <2.0.0"
''' > ${TMP}/packages_pdf_versions_3.8.2/pubspec.yaml

cd $TMP

tar -czf packages_authentication_versions_0.0.1.tar.gz -C packages_authentication_versions_0.0.1 .
tar -czf packages_Autolinker_versions_0.1.1.tar.gz -C packages_autolinker_versions_0.1.1 .
tar -czf packages_bezier_versions_1.1.5.tar.gz -C packages_bezier_versions_1.1.5 .
tar -czf packages_pdf_versions_1.0.0.tar.gz -C packages_pdf_versions_1.0.0 .
tar -czf packages_pdf_versions_3.8.2.tar.gz -C packages_pdf_versions_3.8.2 .


# Move .tar.gz archives to a servable directory
mv *.tar.gz ../../$BASE_ARCHIVES

# Clean up removing tmp_dir
cd ../../
rm -r tmp_dir/
