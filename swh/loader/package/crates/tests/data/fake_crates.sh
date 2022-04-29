#!/usr/bin/env bash

# Script to generate fake crates files and fake http api response.

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

# Creates some http file response for test purposes.
mkdir ../../https_crates.io

# hg-core, https://crates.io/api/v1/crates/hg-core
echo -e '''{"categories":[],"crate":{"badges":[],"categories":[],"created_at":"2019-04-16T18:48:11.404457+00:00","description":"Mercurial pure Rust core library, with no assumption on Python bindings (FFI)","documentation":null,"downloads":442,"exact_match":false,"homepage":"https://mercurial-scm.org","id":"hg-core","keywords":[],"links":{"owner_team":"/api/v1/crates/hg-core/owner_team","owner_user":"/api/v1/crates/hg-core/owner_user","owners":"/api/v1/crates/hg-core/owners","reverse_dependencies":"/api/v1/crates/hg-core/reverse_dependencies","version_downloads":"/api/v1/crates/hg-core/downloads","versions":null},"max_stable_version":"0.0.1","max_version":"0.0.1","name":"hg-core","newest_version":"0.0.1","recent_downloads":40,"repository":"https://www.mercurial-scm.org/repo/hg","updated_at":"2019-04-16T18:48:11.404457+00:00","versions":[145309]},"keywords":[],"versions":[{"audit_actions":[],"crate":"hg-core","crate_size":21344,"created_at":"2019-04-16T18:48:11.404457+00:00","dl_path":"/api/v1/crates/hg-core/0.0.1/download","downloads":442,"features":{},"id":145309,"license":"GPL-2.0-or-later","links":{"authors":"/api/v1/crates/hg-core/0.0.1/authors","dependencies":"/api/v1/crates/hg-core/0.0.1/dependencies","version_downloads":"/api/v1/crates/hg-core/0.0.1/downloads"},"num":"0.0.1","published_by":{"avatar":"https://avatars0.githubusercontent.com/u/474220?v=4","id":45544,"login":"gracinet","name":"Georges Racinet","url":"https://github.com/gracinet"},"readme_path":"/api/v1/crates/hg-core/0.0.1/readme","updated_at":"2019-04-16T18:48:11.404457+00:00","yanked":false}]}
''' > ../../https_crates.io/api_v1_crates_hg-core

# micro-timer, https://crates.io/api/v1/crates/micro-timer
echo -e '''{"categories":[],"crate":{"badges":[],"categories":[],"created_at":"2020-02-27T14:31:49.131258+00:00","description":"Dumb tiny logging timer","documentation":null,"downloads":44245,"exact_match":false,"homepage":"https://foss.heptapod.net/octobus/rust/micro-timer","id":"micro-timer","keywords":[],"links":{"owner_team":"/api/v1/crates/micro-timer/owner_team","owner_user":"/api/v1/crates/micro-timer/owner_user","owners":"/api/v1/crates/micro-timer/owners","reverse_dependencies":"/api/v1/crates/micro-timer/reverse_dependencies","version_downloads":"/api/v1/crates/micro-timer/downloads","versions":null},"max_stable_version":"0.4.0","max_version":"0.4.0","name":"micro-timer","newest_version":"0.4.0","recent_downloads":3910,"repository":"https://foss.heptapod.net/octobus/rust/micro-timer","updated_at":"2020-09-28T13:40:49.593030+00:00","versions":[288167,254896,248120,223660,223652,216405,216156,216139]},"keywords":[],"versions":[{"audit_actions":[{"action":"publish","time":"2020-09-28T13:40:49.593030+00:00","user":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"}}],"crate":"micro-timer","crate_size":3513,"created_at":"2020-09-28T13:40:49.593030+00:00","dl_path":"/api/v1/crates/micro-timer/0.4.0/download","downloads":337,"features":{},"id":288167,"license":"non-standard","links":{"authors":"/api/v1/crates/micro-timer/0.4.0/authors","dependencies":"/api/v1/crates/micro-timer/0.4.0/dependencies","version_downloads":"/api/v1/crates/micro-timer/0.4.0/downloads"},"num":"0.4.0","published_by":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"},"readme_path":"/api/v1/crates/micro-timer/0.4.0/readme","updated_at":"2020-09-28T13:40:49.593030+00:00","yanked":false},{"audit_actions":[{"action":"publish","time":"2020-06-22T16:40:06.754009+00:00","user":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"}}],"crate":"micro-timer","crate_size":3357,"created_at":"2020-06-22T16:40:06.754009+00:00","dl_path":"/api/v1/crates/micro-timer/0.3.1/download","downloads":37853,"features":{},"id":254896,"license":"non-standard","links":{"authors":"/api/v1/crates/micro-timer/0.3.1/authors","dependencies":"/api/v1/crates/micro-timer/0.3.1/dependencies","version_downloads":"/api/v1/crates/micro-timer/0.3.1/downloads"},"num":"0.3.1","published_by":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"},"readme_path":"/api/v1/crates/micro-timer/0.3.1/readme","updated_at":"2020-06-22T16:40:06.754009+00:00","yanked":false},{"audit_actions":[{"action":"publish","time":"2020-06-02T11:38:33.047581+00:00","user":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"}}],"crate":"micro-timer","crate_size":3306,"created_at":"2020-06-02T11:38:33.047581+00:00","dl_path":"/api/v1/crates/micro-timer/0.3.0/download","downloads":4163,"features":{},"id":248120,"license":"non-standard","links":{"authors":"/api/v1/crates/micro-timer/0.3.0/authors","dependencies":"/api/v1/crates/micro-timer/0.3.0/dependencies","version_downloads":"/api/v1/crates/micro-timer/0.3.0/downloads"},"num":"0.3.0","published_by":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"},"readme_path":"/api/v1/crates/micro-timer/0.3.0/readme","updated_at":"2020-06-02T11:38:33.047581+00:00","yanked":false},{"audit_actions":[{"action":"publish","time":"2020-03-23T11:22:26.288804+00:00","user":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"}}],"crate":"micro-timer","crate_size":2937,"created_at":"2020-03-23T11:22:26.288804+00:00","dl_path":"/api/v1/crates/micro-timer/0.2.1/download","downloads":1301,"features":{},"id":223660,"license":"non-standard","links":{"authors":"/api/v1/crates/micro-timer/0.2.1/authors","dependencies":"/api/v1/crates/micro-timer/0.2.1/dependencies","version_downloads":"/api/v1/crates/micro-timer/0.2.1/downloads"},"num":"0.2.1","published_by":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"},"readme_path":"/api/v1/crates/micro-timer/0.2.1/readme","updated_at":"2020-03-23T11:22:26.288804+00:00","yanked":false},{"audit_actions":[{"action":"publish","time":"2020-03-23T10:57:04.418462+00:00","user":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"}}],"crate":"micro-timer","crate_size":2941,"created_at":"2020-03-23T10:57:04.418462+00:00","dl_path":"/api/v1/crates/micro-timer/0.2.0/download","downloads":104,"features":{},"id":223652,"license":"non-standard","links":{"authors":"/api/v1/crates/micro-timer/0.2.0/authors","dependencies":"/api/v1/crates/micro-timer/0.2.0/dependencies","version_downloads":"/api/v1/crates/micro-timer/0.2.0/downloads"},"num":"0.2.0","published_by":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"},"readme_path":"/api/v1/crates/micro-timer/0.2.0/readme","updated_at":"2020-03-23T10:57:04.418462+00:00","yanked":false},{"audit_actions":[{"action":"publish","time":"2020-02-27T23:35:41.872176+00:00","user":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"}}],"crate":"micro-timer","crate_size":4927,"created_at":"2020-02-27T23:35:41.872176+00:00","dl_path":"/api/v1/crates/micro-timer/0.1.2/download","downloads":258,"features":{},"id":216405,"license":"non-standard","links":{"authors":"/api/v1/crates/micro-timer/0.1.2/authors","dependencies":"/api/v1/crates/micro-timer/0.1.2/dependencies","version_downloads":"/api/v1/crates/micro-timer/0.1.2/downloads"},"num":"0.1.2","published_by":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"},"readme_path":"/api/v1/crates/micro-timer/0.1.2/readme","updated_at":"2020-02-27T23:35:41.872176+00:00","yanked":false},{"audit_actions":[{"action":"publish","time":"2020-02-27T15:17:53.486346+00:00","user":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"}}],"crate":"micro-timer","crate_size":2916,"created_at":"2020-02-27T15:17:53.486346+00:00","dl_path":"/api/v1/crates/micro-timer/0.1.1/download","downloads":111,"features":{},"id":216156,"license":"non-standard","links":{"authors":"/api/v1/crates/micro-timer/0.1.1/authors","dependencies":"/api/v1/crates/micro-timer/0.1.1/dependencies","version_downloads":"/api/v1/crates/micro-timer/0.1.1/downloads"},"num":"0.1.1","published_by":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"},"readme_path":"/api/v1/crates/micro-timer/0.1.1/readme","updated_at":"2020-02-27T15:17:53.486346+00:00","yanked":false},{"audit_actions":[{"action":"publish","time":"2020-02-27T14:31:49.131258+00:00","user":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"}}],"crate":"micro-timer","crate_size":2902,"created_at":"2020-02-27T14:31:49.131258+00:00","dl_path":"/api/v1/crates/micro-timer/0.1.0/download","downloads":118,"features":{},"id":216139,"license":"non-standard","links":{"authors":"/api/v1/crates/micro-timer/0.1.0/authors","dependencies":"/api/v1/crates/micro-timer/0.1.0/dependencies","version_downloads":"/api/v1/crates/micro-timer/0.1.0/downloads"},"num":"0.1.0","published_by":{"avatar":"https://avatars.githubusercontent.com/u/9445758?v=4","id":79957,"login":"Alphare","name":"Raphaël Gomès","url":"https://github.com/Alphare"},"readme_path":"/api/v1/crates/micro-timer/0.1.0/readme","updated_at":"2020-02-27T14:31:49.131258+00:00","yanked":false}]}
''' > ../../https_crates.io/api_v1_crates_micro-timer

# Clean up removing tmp_dir
cd ../../
rm -r tmp_dir/
