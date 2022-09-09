#!/usr/bin/env bash

# Script to generate fake Aur packages files and servable directories.

set -euo pipefail

# Create directories
readonly TMP=tmp_dir/aur
readonly BASE_URL=https_aur.archlinux.org
readonly SNAPSHOT_PREFIX=cgit_aur.git_snapshot

mkdir -p $TMP
mkdir -p $BASE_URL

cd $TMP

mkdir 'hg-evolve'
echo -e '''pkgbase = hg-evolve
	pkgdesc = Flexible evolution of Mercurial history
	pkgver = 10.5.2
	pkgrel = 1
	url = https://www.mercurial-scm.org/doc/evolution/
	arch = any
	license = GPL2
	makedepends = python-build
	makedepends = python-installer
	makedepends = python-wheel
	depends = mercurial
	source = https://files.pythonhosted.org/packages/source/h/hg-evolve/hg-evolve-10.5.2.tar.gz
	sha512sums = 81a1cc1202ffaf364fde70c6a36e32330e93aa69c9b9f7e11fbc11f988f7fb302d8b79414c644d274fedb7f0a67e10c4344c0206a1424f2bb97ae2cb11a51315

pkgname = hg-evolve
''' > hg-evolve/.SRCINFO

mkdir 'ibus-git'
echo -e '''pkgbase = ibus-git
	pkgdesc = Next Generation Input Bus for Linux
	pkgver = 1.5.23+12+gef4c5c7e
	pkgrel = 1
	url = https://github.com/ibus/ibus/wiki
	arch = x86_64
	license = LGPL
	makedepends = gobject-introspection
	makedepends = vala
	makedepends = intltool
	makedepends = gnome-common
	makedepends = gtk-doc
	makedepends = gtk2
	makedepends = qt5-base
	makedepends = unicode-cldr
	makedepends = unicode-character-database
	makedepends = unicode-emoji
	makedepends = git
	depends = dconf
	depends = gtk3
	depends = hicolor-icon-theme
	depends = libnotify
	depends = python-dbus
	depends = python-gobject
	depends = iso-codes
	depends = librsvg
	options = !emptydirs
	source = ibus::git+https://github.com/ibus/ibus
	sha512sums = SKIP

pkgname = ibus-git
	depends = dconf
	depends = gtk3
	depends = hicolor-icon-theme
	depends = libnotify
	depends = python-dbus
	depends = python-gobject
	depends = iso-codes
	depends = librsvg
	depends = libibus-git=1.5.23+12+gef4c5c7e
	provides = ibus
	conflicts = ibus

pkgname = libibus-git
	pkgdesc = IBus support library
	depends = libglib-2.0.so
	depends = libgobject-2.0.so
	depends = libgio-2.0.so
	provides = libibus
	provides = libibus-1.0.so
	conflicts = libibus
''' > ibus-git/.SRCINFO

mkdir 'libervia-web-hg'
echo -e '''pkgbase = libervia-web-hg
	pkgdesc = Salut à Toi, multi-frontends multi-purposes XMPP client (Web interface)
	pkgver = 0.9.0.r1492.3a34d78f2717
	pkgrel = 1
	url = http://salut-a-toi.org/
	install = libervia-web-hg.install
	arch = any
	license = AGPL3
	makedepends = python-setuptools
	makedepends = mercurial
	depends = python
	depends = python-jinja
	depends = python-shortuuid-git
	depends = libervia-media-hg
	depends = libervia-backend-hg
	depends = libervia-templates-hg
	depends = python-zope-interface
	depends = python-pyopenssl
	depends = python-autobahn
	depends = dbus
	depends = python-brython
	provides = libervia-web
	options = !strip
	source = hg+https://repos.goffi.org/libervia
	md5sums = SKIP

pkgname = libervia-web-hg
''' > libervia-web-hg/.SRCINFO

mkdir 'tealdeer-git'
echo -e '''# Generated by mksrcinfo v8
# Fri Sep  4 20:36:25 UTC 2020
pkgbase = tealdeer-git
	pkgdesc = A fast tldr client in Rust.
	pkgver = r255.30b7c5f
	pkgrel = 1
	url = https://github.com/dbrgn/tealdeer
	arch = x86_64
	arch = armv6h
	arch = armv7h
	arch = aarch64
	license = MIT
	license = Apache
	makedepends = git
	makedepends = rust
	makedepends = cargo
	depends = openssl
	provides = tldr
	conflicts = tldr
	options = !emptydirs
	source = git+https://github.com/dbrgn/tealdeer
	sha256sums = SKIP

pkgname = tealdeer-git
''' > tealdeer-git/.SRCINFO

mkdir 'a-fake-one'
echo -e '''# This one does not exists
# For test purpose, in particular for multi keys, multi lines edge case
pkgbase = a-fake-one
	pkgdesc = A first line of description.
	pkgdesc = A second line for more information.
	pkgver = 0.0.1
	pkgrel = 1
	url = https://nowhere/a-fake-one
	url = https://mirror/a-fake-one
	arch = x86_64
	arch = armv6h
	arch = armv7h
	arch = aarch64
	license = MIT
	license = Apache
	makedepends = git
	makedepends = rust
	makedepends = cargo
	depends = openssl
	provides = a-fake-one
	conflicts = a-fake-one
	options = !emptydirs
	source = git+https://nowhere/a-fake-one
	sha256sums = SKIP

pkgname = a-fake-one
''' > a-fake-one/.SRCINFO

# Compress packages folders to .tar.gz archives
tar -czf ${SNAPSHOT_PREFIX}_hg-evolve.tar.gz hg-evolve
tar -czf ${SNAPSHOT_PREFIX}_ibus-git.tar.gz ibus-git
tar -czf ${SNAPSHOT_PREFIX}_libervia-web-hg.tar.gz libervia-web-hg
tar -czf ${SNAPSHOT_PREFIX}_tealdeer-git.tar.gz tealdeer-git
tar -czf ${SNAPSHOT_PREFIX}_a-fake-one.tar.gz a-fake-one

# Move .tar.gz archives to a servable directory
mv *.tar.gz ../../$BASE_URL

# Clean up removing tmp_dir
cd ../../
rm -r tmp_dir/
