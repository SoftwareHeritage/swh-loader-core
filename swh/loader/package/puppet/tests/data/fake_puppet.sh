#!/usr/bin/env bash

# Script to generate fake Puppet module archives as .tar.gz.

set -euo pipefail

# Create directories
readonly TMP=tmp_dir/puppet
readonly BASE_PATH=https_forgeapi.puppet.com

mkdir -p $TMP

# tar.gz package archives
# Puppet module tar.gz archive needs at least one directory with a metadata.json file
mkdir -p ${TMP}/saz-memcached-1.0.0
mkdir -p ${TMP}/saz-memcached-8.1.0
mkdir -p $BASE_PATH

echo -e '''{
  "summary": "UNKNOWN",
  "author": "saz",
  "source": "UNKNOWN",
  "dependencies": [

  ],
  "types": [

  ],
  "license": "Apache License, Version 2.0",
  "project_page": "https://github.com/saz/puppet-memcached",
  "version": "1.0.0",
  "name": "saz-memcached",
  "checksums": {
    "spec/spec_helper.rb": "ca19ec4f451ebc7fdb035b52eae6e909",
    "manifests/params.pp": "0b8904086e7fa6f0d1f667d547a17d96",
    "README.md": "fa0b9f6d97f2763e565d8a330fb3930b",
    "manifests/config.pp": "706f7c5001fb6014575909a335a52def",
    "templates/memcached.conf.erb": "8151e00d922bb9ebb1a24a05ac0969d7",
    "manifests/service.pp": "a528751401189c299a38cab12d52431f",
    "tests/init.pp": "e798f4999ba392f3c0fce0d5290c263f",
    "manifests/install.pp": "11a9e9a99a7bc1c7b2511ce7e79c9fb4",
    "spec/spec.opts": "a600ded995d948e393fbe2320ba8e51c",
    "metadata.json": "d34d0b70aba36510fbc2df4e667479ef",
    "manifests/init.pp": "c5166a8a88b544ded705efac21494bc1",
    "Modulefile": "7f512991a7d2ad99ffb28ac6e7419f9e"
  },
  "description": "Manage memcached via Puppet"
}
''' > ${TMP}/saz-memcached-1.0.0/metadata.json

echo -e '''{
  "name": "saz-memcached",
  "version": "8.1.0",
  "author": "saz",
  "summary": "Manage memcached via Puppet",
  "license": "Apache-2.0",
  "source": "git://github.com/saz/puppet-memcached.git",
  "project_page": "https://github.com/saz/puppet-memcached",
  "issues_url": "https://github.com/saz/puppet-memcached/issues",
  "description": "Manage memcached via Puppet",
  "requirements": [
    {"name":"puppet","version_requirement":">= 6.1.0 < 8.0.0" }
  ],
  "dependencies": [
    {"name":"puppetlabs/stdlib","version_requirement":">= 4.13.1 < 9.0.0"},
    {"name":"puppetlabs/firewall","version_requirement":">= 0.1.0 < 4.0.0"},
    {"name":"puppet/systemd","version_requirement":">= 2.10.0 < 4.0.0"},
    {"name":"puppet/selinux","version_requirement":">= 3.2.0 < 4.0.0"}
  ],
  "operatingsystem_support": [
    {
      "operatingsystem": "RedHat",
      "operatingsystemrelease": [
        "7",
        "8",
        "9"
      ]
    },
    {
      "operatingsystem": "CentOS",
      "operatingsystemrelease": [
        "7",
        "8",
        "9"
      ]
    },
    {
      "operatingsystem": "OracleLinux",
      "operatingsystemrelease": [
        "7"
      ]
    },
    {
      "operatingsystem": "Scientific",
      "operatingsystemrelease": [
        "7"
      ]
    },
    {
      "operatingsystem": "Debian",
      "operatingsystemrelease": [
        "9",
        "10",
        "11"
      ]
    },
    {
      "operatingsystem": "Ubuntu",
      "operatingsystemrelease": [
        "18.04",
        "20.04",
        "22.04"
      ]
    },
    {
      "operatingsystem": "Windows"
    },
    {
      "operatingsystem": "FreeBSD"
    }
  ]
}
''' > ${TMP}/saz-memcached-8.1.0/metadata.json

cd $TMP

# Tar compress
tar -czf v3_files_saz-memcached-1.0.0.tar.gz saz-memcached-1.0.0
tar -czf v3_files_saz-memcached-8.1.0.tar.gz saz-memcached-8.1.0

# Move .tar.gz archives to a servable directory
mv *.tar.gz ../../$BASE_PATH

# Clean up removing tmp_dir
cd ../../
rm -r tmp_dir/
