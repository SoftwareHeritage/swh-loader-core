#!/usr/bin/env bash

# Script to generate fake Perl package archives as .tar.gz.

set -euo pipefail

# Create directories
readonly TMP=tmp_dir/cpan
readonly BASE_PATH=https_cpan.metacpan.org

mkdir -p $TMP

# tar.gz package archives
# Perl package tar.gz archive needs at least one directory with a META.json or META.yml file
mkdir -p ${TMP}/Internals-CountObjects-0.01
mkdir -p ${TMP}/Internals-CountObjects-0.05
mkdir -p $BASE_PATH

echo -e """---
abstract: 'Report all allocated perl objects'
author:
  - 'Josh Jore <jjore@cpan.org>'
build_requires: {}
configure_requires:
  ExtUtils::MakeMaker: 6.31
dynamic_config: 0
generated_by: 'Dist::Zilla version 4.200000, CPAN::Meta::Converter version 2.102400'
license: perl
meta-spec:
  url: http://module-build.sourceforge.net/META-spec-v1.4.html
  version: 1.4
name: Internals-CountObjects
version: 0.01
""" > ${TMP}/Internals-CountObjects-0.01/META.yml

echo -e '''{
   "abstract" : "Report all allocated perl objects",
   "author" : [
      "Josh Jore <jjore@cpan.org>"
   ],
   "dynamic_config" : 0,
   "generated_by" : "Dist::Zilla version 4.200000, CPAN::Meta::Converter version 2.102400",
   "license" : [
      "perl_5"
   ],
   "meta-spec" : {
      "url" : "http://search.cpan.org/perldoc?CPAN::Meta::Spec",
      "version" : "2"
   },
   "name" : "Internals-CountObjects",
   "prereqs" : {
      "build" : {
         "requires" : {
            "ExtUtils::CBuilder" : 0
         }
      }
   },
   "release_status" : "stable",
   "resources" : {
      "bugtracker" : {
         "mailto" : "bug-Internals-CountObjects@rt.cpan.org",
         "web" : "http://rt.cpan.org/NoAuth/Bugs.html?Dist=Internals-CountObjects"
      },
      "homepage" : "http://search.cpan.org/dist/Internals-CountObjects",
      "repository" : {
         "type" : "git",
         "url" : "git://github.com/jbenjore/Internals-CountObjects.git",
         "web" : "http://github.com/jbenjore/Internals-CountObjects"
      }
   },
   "version" : "0.05"
}
''' > ${TMP}/Internals-CountObjects-0.05/META.json

cd $TMP

# Tar compress
tar -czf authors_id_J_JJ_JJORE_Internals-CountObjects-0.01.tar.gz Internals-CountObjects-0.01
tar -czf authors_id_J_JJ_JJORE_Internals-CountObjects-0.05.tar.gz Internals-CountObjects-0.05

# Move .tar.gz archives to a servable directory
mv *.tar.gz ../../$BASE_PATH

# Clean up removing tmp_dir
cd ../../
rm -r tmp_dir/
