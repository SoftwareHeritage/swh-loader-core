#!/usr/bin/env bash

# Script to generate fake crates files.

set -euo pipefail

# files and directories
mkdir -p tmp_dir/crates/
mkdir tmp_dir/crates/hg-core-0.0.1
mkdir tmp_dir/crates/micro-timer-0.1.0
mkdir tmp_dir/crates/micro-timer-0.1.1
mkdir tmp_dir/crates/micro-timer-0.1.2
mkdir tmp_dir/crates/micro-timer-0.2.0
mkdir tmp_dir/crates/micro-timer-0.2.1
mkdir tmp_dir/crates/micro-timer-0.3.0
mkdir tmp_dir/crates/micro-timer-0.3.1
mkdir tmp_dir/crates/micro-timer-0.4.0


cd tmp_dir/crates/

# Creates some <package>-<version>.crate file for test purposes.

# hg-core-0.0.1/Cargo.toml
echo -e '''[package]
name = "hg-core"
version = "0.0.1"
authors = ["Georges Racinet <georges.racinet@octobus.net>"]
description = "Mercurial pure Rust core library, with no assumption on Python bindings (FFI)"
homepage = "https://mercurial-scm.org"
license = "GPL-2.0-or-later"
repository = "https://www.mercurial-scm.org/repo/hg"

[lib]
name = "hg"
[dev-dependencies.rand]
version = "~0.6"

[dev-dependencies.rand_pcg]
version = "~0.1"
''' > hg-core-0.0.1/Cargo.toml

# micro-timer-0.1.0/Cargo.toml
echo -e '''[package]
edition = "2018"
name = "micro-timer"
version = "0.1.0"
# authors = ["Raphaël Gomès <rgomes@octobus.net>"]  # commented for testing empty authors
description = "Dumb tiny logging timer"
homepage = "https://heptapod.octobus.net/Alphare/micro-timer"
readme = "README.md"
license-file = "LICENCE"
repository = "https://heptapod.octobus.net/Alphare/micro-timer"

[lib]
proc-macro = true
[dependencies.quote]
version = "1.0.2"

[dependencies.syn]
version = "1.0.16"
features = ["full", "extra-traits"]
[dev-dependencies.log]
version = "0.4.8"
''' > micro-timer-0.1.0/Cargo.toml

# micro-timer-0.1.1/Cargo.toml
echo -e '''[package]
edition = "2018"
name = "micro-timer"
version = "0.1.1"
authors = ["Raphaël Gomès <rgomes@octobus.net>"]
description = "Dumb tiny logging timer"
homepage = "https://heptapod.octobus.net/Alphare/micro-timer"
readme = "README.md"
license-file = "LICENCE"
repository = "https://heptapod.octobus.net/Alphare/micro-timer"

[lib]
proc-macro = true
[dependencies.quote]
version = "1.0.2"

[dependencies.syn]
version = "1.0.16"
features = ["full", "extra-traits"]
[dev-dependencies.log]
version = "0.4.8"
''' > micro-timer-0.1.1/Cargo.toml

# micro-timer-0.1.2/Cargo.toml
echo -e '''[package]
edition = "2018"
name = "micro-timer"
version = "0.1.2"
authors = ["Raphaël Gomès <rgomes@octobus.net>"]
description = "Dumb tiny logging timer"
homepage = "https://heptapod.octobus.net/Alphare/micro-timer"
readme = "README.md"
license-file = "LICENCE"
repository = "https://heptapod.octobus.net/Alphare/micro-timer"

[lib]
proc-macro = true
[dependencies.proc-macro2]
version = "1.0.9"

[dependencies.quote]
version = "1.0.2"

[dependencies.syn]
version = "1.0.16"
features = ["full", "extra-traits"]
[dev-dependencies.log]
version = "0.4.8"

[dev-dependencies.pretty_assertions]
version = "0.6.1"
''' > micro-timer-0.1.2/Cargo.toml

# micro-timer-0.2.0/Cargo.toml
echo -e '''[package]
edition = "2018"
name = "micro-timer"
version = "0.2.0"
authors = ["Raphaël Gomès <rgomes@octobus.net>"]
description = "Dumb tiny logging timer"
homepage = "https://heptapod.octobus.net/Alphare/micro-timer"
readme = "README.md"
license-file = "LICENCE"
repository = "https://heptapod.octobus.net/Alphare/micro-timer"
[dependencies.micro-timer-macros]
version = "0.2.0"

[dependencies.scopeguard]
version = "1.1.0"
[dev-dependencies.log]
version = "0.4.8"
''' > micro-timer-0.2.0/Cargo.toml

# micro-timer-0.2.1/Cargo.toml
echo -e '''[package]
edition = "2018"
name = "micro-timer"
version = "0.2.1"
authors = ["Raphaël Gomès <rgomes@octobus.net>"]
description = "Dumb tiny logging timer"
homepage = "https://heptapod.octobus.net/Alphare/micro-timer"
readme = "README.md"
license-file = "LICENCE"
repository = "https://heptapod.octobus.net/Alphare/micro-timer"
[dependencies.micro-timer-macros]
version = "0.2.0"

[dependencies.scopeguard]
version = "1.1.0"
[dev-dependencies.log]
version = "0.4.8"
''' > micro-timer-0.2.1/Cargo.toml

# micro-timer-0.3.0/Cargo.toml
echo -e '''[package]
edition = "2018"
name = "micro-timer"
version = "0.3.0"
authors = ["Raphaël Gomès <rgomes@octobus.net>"]
description = "Dumb tiny logging timer"
homepage = "https://heptapod.octobus.net/Alphare/micro-timer"
readme = "README.md"
license-file = "LICENCE"
repository = "https://heptapod.octobus.net/Alphare/micro-timer"
[dependencies.micro-timer-macros]
version = "0.3.0"

[dependencies.scopeguard]
version = "1.1.0"
[dev-dependencies.log]
version = "0.4.8"
''' > micro-timer-0.3.0/Cargo.toml

# micro-timer-0.3.1/Cargo.toml
echo -e '''[package]
edition = "2018"
name = "micro-timer"
version = "0.3.1"
authors = ["Raphaël Gomès <rgomes@octobus.net>"]
description = "Dumb tiny logging timer"
homepage = "https://foss.heptapod.net/octobus/rust/micro-timer"
readme = "README.md"
license-file = "LICENCE"
repository = "https://foss.heptapod.net/octobus/rust/micro-timer"
[dependencies.micro-timer-macros]
version = "0.3.1"

[dependencies.scopeguard]
version = "1.1.0"
[dev-dependencies.log]
version = "0.4.8"
''' > micro-timer-0.3.1/Cargo.toml

# micro-timer-0.4.0/Cargo.toml
echo -e '''[package]
edition = "2018"
name = "micro-timer"
version = "0.4.0"
authors = ["Raphaël Gomès <rgomes@octobus.net>"]
description = "Dumb tiny logging timer"
homepage = "https://foss.heptapod.net/octobus/rust/micro-timer"
readme = "README.md"
license-file = "LICENCE"
repository = "https://foss.heptapod.net/octobus/rust/micro-timer"
[dependencies.micro-timer-macros]
version = "0.4.0"

[dependencies.scopeguard]
version = "1.1.0"
[dev-dependencies.log]
version = "0.4.8"
''' > micro-timer-0.4.0/Cargo.toml

# .crate file are tar.gz archive
tar -czf hg-core-0.0.1.crate hg-core-0.0.1/
tar -czf micro-timer-0.1.0.crate micro-timer-0.1.0/
tar -czf micro-timer-0.1.1.crate micro-timer-0.1.1/
tar -czf micro-timer-0.1.2.crate micro-timer-0.1.2/
tar -czf micro-timer-0.2.0.crate micro-timer-0.2.0/
tar -czf micro-timer-0.2.1.crate micro-timer-0.2.1/
tar -czf micro-timer-0.3.0.crate micro-timer-0.3.0/
tar -czf micro-timer-0.3.1.crate micro-timer-0.3.1/
tar -czf micro-timer-0.4.0.crate micro-timer-0.4.0/

# Copy and rename .crate file for usage with 'requests_mock_datadir'
# See : https://docs.softwareheritage.org/devel/apidoc/swh.core.pytest_plugin.html#swh.core.pytest_plugin.requests_mock_datadir
mkdir ../../https_static.crates.io

cp hg-core-0.0.1.crate ../../https_static.crates.io/crates_hg-core_hg-core-0.0.1.crate
cp micro-timer-0.1.0.crate ../../https_static.crates.io/crates_micro-timer_micro-timer-0.1.0.crate
cp micro-timer-0.1.1.crate ../../https_static.crates.io/crates_micro-timer_micro-timer-0.1.1.crate
cp micro-timer-0.1.2.crate ../../https_static.crates.io/crates_micro-timer_micro-timer-0.1.2.crate
cp micro-timer-0.2.0.crate ../../https_static.crates.io/crates_micro-timer_micro-timer-0.2.0.crate
cp micro-timer-0.2.1.crate ../../https_static.crates.io/crates_micro-timer_micro-timer-0.2.1.crate
cp micro-timer-0.3.0.crate ../../https_static.crates.io/crates_micro-timer_micro-timer-0.3.0.crate
cp micro-timer-0.3.1.crate ../../https_static.crates.io/crates_micro-timer_micro-timer-0.3.1.crate
cp micro-timer-0.4.0.crate ../../https_static.crates.io/crates_micro-timer_micro-timer-0.4.0.crate

# Clean up removing tmp_dir
cd ../../
rm -r tmp_dir/
