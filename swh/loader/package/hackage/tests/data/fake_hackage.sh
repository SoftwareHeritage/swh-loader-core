#!/usr/bin/env bash

# Script to generate fake Hackage http api response and fake Haskell package archives as .tar.gz.

set -euo pipefail

# Create directories
readonly TMP=tmp_dir/hackage
readonly BASE_API=https_hackage.haskell.org

mkdir -p $TMP
mkdir -p $BASE_API

# http api response that returns versions per package
echo -e '''{"2.1.0.0":"normal"}
''' > ${BASE_API}/package_aeson

echo -e '''{"0.1":"normal","0.3.0.2":"normal"}
''' > ${BASE_API}/package_colors

echo -e '''{"0.6.3":"normal"}
''' > ${BASE_API}/package_Hs2lib

echo -e '''{"0.1.0":"normal"}
''' > ${BASE_API}/package_numeric-qq

echo -e '''{"1.0.0.0":"normal"}
''' > ${BASE_API}/package_haskell2010

# http api response that returns revisions per version
echo -e '''[
    {
        "number": 0,
        "time": "2022-06-15T14:07:42Z",
        "user": "phadej"
    },
    {
        "number": 1,
        "time": "2022-06-20T10:58:49Z",
        "user": "phadej"
    },
    {
        "number": 2,
        "time": "2022-08-11T09:04:30Z",
        "user": "phadej"
    }
]
''' > ${BASE_API}/package_aeson-2.1.0.0_revisions

echo -e '''[
    {
        "number": 0,
        "time": "2013-06-01T13:59:19Z",
        "user": "FumiakiKinoshita"
    }
]
''' > ${BASE_API}/package_colors-0.1_revisions

echo -e '''[
    {
        "number": 0,
        "time": "2015-02-23T03:50:39Z",
        "user": "FumiakiKinoshita"
    },
    {
        "number": 1,
        "time": "2015-06-06T14:20:04Z",
        "user": "FumiakiKinoshita"
    },
    {
        "number": 2,
        "time": "2022-08-27T11:55:04Z",
        "user": "FumiakiKinoshita"
    }
]
''' > ${BASE_API}/package_colors-0.3.0.2_revisions

echo -e '''[
    {
        "number": 0,
        "time": "2015-01-27T11:58:10Z",
        "user": "TamarChristina"
    }
]
''' > ${BASE_API}/package_Hs2lib-0.6.3_revisions

echo -e '''[
    {
        "number": 0,
        "time": "2014-05-18T01:44:58Z",
        "user": "NikitaVolkov"
    }
]
''' > ${BASE_API}/package_numeric-qq-0.1.0_revisions

echo -e '''[
    {
        "number": 0,
        "time": "2014-03-22T12:41:36Z",
        "user": "HerbertValerioRiedel"
    }
]
''' > ${BASE_API}/package_haskell2010-1.0.0.0_revisions

# tar.gz package archives
# Haskell package tar.gz archive needs at least one directory with a {pkname}.cabal file
mkdir -p ${TMP}/aeson-2.1.0.0
mkdir -p ${TMP}/colors-0.1
mkdir -p ${TMP}/colors-0.3.0.2
mkdir -p ${TMP}/Hs2lib-0.6.3
mkdir -p ${TMP}/numeric-qq-0.1.0
mkdir -p ${TMP}/haskell2010-1.0.0.0

echo -e """name:               aeson
version:            2.1.0.0
license:            BSD3
license-file:       LICENSE
category:           Text, Web, JSON
copyright:
  (c) 2011-2016 Bryan O'Sullivan
  (c) 2011 MailRank, Inc.

author:             Bryan O'Sullivan <bos@serpentine.com>
maintainer:         Adam Bergmark <adam@bergmark.nl>
stability:          experimental
tested-with:
  GHC ==8.0.2
   || ==8.2.2
   || ==8.4.4
   || ==8.6.5
   || ==8.8.4
   || ==8.10.7
   || ==9.0.2
   || ==9.2.3
   || ==9.4.1

synopsis:           Fast JSON parsing and encoding
cabal-version:      >=1.10
homepage:           https://github.com/haskell/aeson
bug-reports:        https://github.com/haskell/aeson/issues
build-type:         Simple
description:
  A JSON parsing and encoding library optimized for ease of use
  and high performance.
  .
  To get started, see the documentation for the @Data.Aeson@ module
  below.
  .
  (A note on naming: in Greek mythology, Aeson was the father of Jason.)

extra-source-files:
  *.yaml
  benchmarks/json-data/*.json
  cbits/*.c
  changelog.md
  README.markdown
  src-ffi/Data/Aeson/Parser/*.hs
  src-pure/Data/Aeson/Parser/*.hs
  tests/golden/*.expected
  tests/JSONTestSuite/test_parsing/*.json
  tests/JSONTestSuite/test_transform/*.json

flag cffi
  description:
    Controls whether to include c-ffi bits or pure haskell. Default to False for security.

  default:     False
  manual:      True

flag ordered-keymap
  description: Use ordered @Data.Map.Strict@ for KeyMap implementation.
  default:     True
  manual:      True

library
  default-language: Haskell2010
  hs-source-dirs:   src attoparsec-iso8601/src
  exposed-modules:
    Data.Aeson
    Data.Aeson.Encoding
    Data.Aeson.Encoding.Internal
    Data.Aeson.Internal
    Data.Aeson.Internal.Time
    Data.Aeson.Key
    Data.Aeson.KeyMap
    Data.Aeson.Parser
    Data.Aeson.Parser.Internal
    Data.Aeson.QQ.Simple
    Data.Aeson.Text
    Data.Aeson.TH
    Data.Aeson.Types

  other-modules:
    Data.Aeson.Encoding.Builder
    Data.Aeson.Internal.ByteString
    Data.Aeson.Internal.Functions
    Data.Aeson.Internal.Text
    Data.Aeson.Internal.TH
    Data.Aeson.Parser.Time
    Data.Aeson.Parser.Unescape
    Data.Aeson.Types.Class
    Data.Aeson.Types.FromJSON
    Data.Aeson.Types.Generic
    Data.Aeson.Types.Internal
    Data.Aeson.Types.ToJSON
    Data.Attoparsec.Time
    Data.Attoparsec.Time.Internal

  -- GHC bundled libs
  build-depends:
      base              >=4.9.0.0  && <5
    , bytestring        >=0.10.8.1 && <0.12
    , containers        >=0.5.7.1  && <0.7
    , deepseq           >=1.4.2.0  && <1.5
    , ghc-prim          >=0.5.0.0  && <0.9
    , template-haskell  >=2.11.0.0 && <2.19
    , text              >=1.2.3.0  && <1.3 || >=2.0 && <2.1
    , time              >=1.6.0.1  && <1.13

  -- Compat
  build-depends:
      base-compat-batteries  >=0.10.0 && <0.13
    , generically            >=0.1    && <0.2
    , time-compat            >=1.9.6  && <1.10

  if !impl(ghc >=8.6)
    build-depends: contravariant >=1.4.1 && <1.6

  -- Other dependencies
  build-depends:
      attoparsec            >=0.14.2   && <0.15
    , data-fix              >=0.3.2    && <0.4
    , dlist                 >=0.8.0.4  && <1.1
    , hashable              >=1.3.5.0  && <1.5
    , indexed-traversable   >=0.1.2    && <0.2
    , OneTuple              >=0.3.1    && <0.4
    , primitive             >=0.7.3.0  && <0.8
    , QuickCheck            >=2.14.2   && <2.15
    , scientific            >=0.3.7.0  && <0.4
    , semialign             >=1.2      && <1.3
    , strict                >=0.4      && <0.5
    , tagged                >=0.8.6    && <0.9
    , text-short            >=0.1.5    && <0.2
    , th-abstraction        >=0.3.0.0  && <0.5
    , these                 >=1.1.1.1  && <1.2
    , unordered-containers  >=0.2.10.0 && <0.3
    , uuid-types            >=1.0.5    && <1.1
    , vector                >=0.12.0.1 && <0.13
    , witherable            >=0.4.2    && <0.5

  ghc-options:      -Wall

  if (impl(ghcjs) || !flag(cffi))
    hs-source-dirs: src-pure
    other-modules:  Data.Aeson.Parser.UnescapePure

  else
    c-sources:      cbits/unescape_string.c
    cpp-options:    -DCFFI
    hs-source-dirs: src-ffi
    other-modules:  Data.Aeson.Parser.UnescapeFFI
    build-depends:  text <2.0

  if flag(ordered-keymap)
    cpp-options: -DUSE_ORDEREDMAP=1

test-suite aeson-tests
  default-language: Haskell2010
  type:             exitcode-stdio-1.0
  hs-source-dirs:   tests
  main-is:          Tests.hs
  ghc-options:      -Wall -threaded -rtsopts
  other-modules:
    DataFamilies.Encoders
    DataFamilies.Instances
    DataFamilies.Properties
    DataFamilies.Types
    Encoders
    ErrorMessages
    Functions
    Instances
    Options
    Properties
    PropertyGeneric
    PropertyKeys
    PropertyQC
    PropertyRoundTrip
    PropertyRTFunctors
    PropertyTH
    PropUtils
    SerializationFormatSpec
    Types
    UnitTests
    UnitTests.NullaryConstructors

  build-depends:
      aeson
    , attoparsec
    , base
    , base-compat
    , base-orphans          >=0.5.3    && <0.9
    , base16-bytestring
    , bytestring
    , containers
    , data-fix
    , Diff                  >=0.4      && <0.5
    , directory
    , dlist
    , filepath
    , generic-deriving      >=1.10     && <1.15
    , generically
    , ghc-prim              >=0.2
    , hashable
    , indexed-traversable
    , integer-logarithms    >=1        && <1.1
    , OneTuple
    , primitive
    , QuickCheck            >=2.14.2   && <2.15
    , quickcheck-instances  >=0.3.26.1 && <0.4
    , scientific
    , strict
    , tagged
    , tasty
    , tasty-golden
    , tasty-hunit
    , tasty-quickcheck
    , template-haskell
    , text
    , text-short
    , these
    , time
    , time-compat
    , unordered-containers
    , uuid-types
    , vector

source-repository head
  type:     git
  location: git://github.com/haskell/aeson.git
""" > ${TMP}/aeson-2.1.0.0/aeson.cabal

echo -e """-- Initial colors.cabal generated by cabal init.  For further
-- documentation, see http://haskell.org/cabal/users-guide/

name:                colors
version:             0.1
synopsis:            A type for colors
-- description:
homepage:            https://github.com/fumieval/colors
license:             BSD3
license-file:        LICENSE
author:              Fumiaki Kinoshita
maintainer:          Fumiaki Kinoshita <fumiexcel@gmail.com>
-- copyright:
category:            Data
build-type:          Simple
cabal-version:       >=1.8

source-repository head
  type: git
  location: https://github.com/fumieval/colors.git

library
  exposed-modules:     Data.Color, Data.Color.Names, Data.Color.Class
  -- other-modules:
  build-depends:       base ==4.*, profunctors ==3.*
""" > ${TMP}/colors-0.1/colors.cabal

echo -e """name:                colors
version:             0.3.0.2
synopsis:            A type for colors
-- description:
homepage:            https://github.com/fumieval/colors
license:             BSD3
license-file:        LICENSE
author:              Fumiaki Kinoshita
maintainer:          Fumiaki Kinoshita <fumiexcel@gmail.com>
copyright:           Copyright (C) 2013 Fumiaki Kinoshita
category:            Data
build-type:          Simple
cabal-version:       >=1.8

source-repository head
  type: git
  location: https://github.com/fumieval/colors.git

library
  exposed-modules:     Data.Color, Data.Color.Names, Data.Color.Class
  -- other-modules:
  build-depends:       base ==4.*, profunctors >= 3 && < 5, linear, lens >= 4.0 && <5
""" > ${TMP}/colors-0.3.0.2/colors.cabal

echo -e """Name:           Hs2lib
Version:        0.6.3
Cabal-Version:  >= 1.10
Build-Type:     Custom
License:        BSD3
License-File:   LICENSE.txt
Author:         Tamar Christina <tamar (at) zhox.com>
Maintainer:     Tamar Christina <tamar (at) zhox.com>
Homepage:       http://blog.zhox.com/category/hs2lib/
Category:       Development
Stability:      experimental
Synopsis:       A Library and Preprocessor that makes it easier to create shared libs from Haskell programs.
Description:    The supplied PreProcessor can be run over any existing source and would generate FFI code for every function marked to be exported by the special notation documented inside the package. It then proceeds to compile this generated code into a lib.
                .
                The Library contains some helper code that's commonly needed to convert between types, and contains the code for the typeclasses the PreProcessor uses in the generated code to keep things clean.
                .
                It will always generated the required C types for use when calling the dll, but it will also generate the C# unsafe code if requested.
                .
				Read http://www.scribd.com/doc/63918055/Hs2lib-Tutorial#scribd
                .
                A replacement for this library is in development and will eventually replace this
				.
                Current Restrictions:
                .
                    - Does NOT support x64 bit versions of GHC. This will be added in future versions if enough demand exist.
                .
                    - You cannot export functions which have the same name (even if they're in different modules because 1 big hsc file is generated at the moment, no conflict resolutions)
                .
                    - You cannot export datatypes with the same name, same restriction as above.
                .
                    - Does not support automatic instance generation for infix constructors yet
                .
                    - List of Lists are not supported (concat them first).
                .
                NOTE: Package is now working again, but I have fixed the version of haskell-src-exts to prevent it from breaking again.
                .
Data-Files: Templates/main.template-unix.c,
            Templates/main.template-win.c,
            Templates/nomain.template-unix.c,
            Templates/nomain.template-win.c,
            Includes/Tuples.h,
            Includes/Instances.h,
            Includes/FFI.dll
            Includes/FFI/Properties/AssemblyInfo.cs
            Includes/FFI/FFI.sln
            Includes/FFI/FFI.csproj
            Includes/FFI/LockedValue.cs
            Includes/FFI/SafeString.cs
            Includes/FFI/FFI.suo
            Includes/FFI/WinLib.cs
            Includes/WinDllSupport.dll
            Includes/WinDllSupport.lib
            Includes/WinDllSupport.exp
            Includes/WinDllSupport.h


Tested-With:   GHC  >= 7.8.3
Build-Depends: base >= 4,
               syb  >= 0.1.0.2

Extra-Source-Files: WinDll/*.hs,
                    WinDll/CodeGen/*.hs,
                    WinDll/CodeGen/CSharp/*.hs,
                    WinDll/COFF/*.hs,
                    -- WinDll/Lib/*.hsc,
                    WinDll/Lib/*.cpphs,
                    WinDll/Lib/*.xpphs,
                    WinDll/Lib/*.hs,
                    WinDll/Shared/*.hs,
                    WinDll/Debug/*.hs,
                    WinDll/Debug/*.xhs,
                    WinDll/Debug/*.hs-boot,
                    WinDll/Structs/*.hs,
                    WinDll/Structs/Folds/*.hs,
                    WinDll/Structs/MShow/*.hs,
                    WinDll/Utils/*.hs,
                    Tests/*.hs,
                    Tests/Exec/*.hs,
                    Tests/Src/*.hs,
                    Tests/Src/*.txt,
                    *.hs,
                    Includes/*.h,
                    Includes/*.dll,
                    Includes/*.exp,
                    Includes/*.lib,
                    LIMITS.TXT

Library
    Exposed:    True
    Exposed-Modules:    WinDll.Lib.Converter,
                        WinDll.Lib.NativeMapping,
                        WinDll.Lib.InstancesTypes,
                        WinDll.Debug.Alloc,
                        WinDll.Debug.Records,
                        WinDll.Debug.Stack,
                        WinDll.Debug.Exports,
                        WinDll.Lib.NativeMapping_Debug,
                        WinDll.Lib.Native,
                        WinDll.Lib.Tuples,
                        WinDll.Lib.Tuples_Debug,
                        WinDll.Structs.Types

    Build-Depends:   haskell-src-exts >= 1.13.5 && <= 1.15.0.1,
                     ghc              >= 7.8.3,
                     base             >= 4    && < 5,
                     filepath         >= 1.1.0.2,
                     old-locale       >= 1.0.0.2,
                     time             >= 1.2.0.3,
                     directory        >= 1.0.0.3,
                     syb              >= 0.1.0.2,
                     random           >= 1.0.0.1

    Other-Modules:    Paths_Hs2lib
    Default-Language: Haskell98

    if !os(windows)
        GHC-Options: -fPIC

    Build-Tools: hsc2hs, cpphs
    Include-Dirs: Includes


Executable Hs2lib
    Main-is:         Hs2lib.hs

    Build-Depends:   QuickCheck       >= 2.1.0.1,
                     directory        >= 1.0.0.3,
                     ghc-paths        >= 0.1.0.5,
                     filepath         >= 1.1.0.2,
                     random           >= 1.0.0.1,
                     process          >= 1.0.1.1,
                     ghc              >= 7.8.3,
                     mtl              >= 1.1.0.2,
                     containers       >= 0.2.0.0,
                     array            >= 0.2.0.0,
                     haskell-src-exts >= 1.13.5 && <= 1.15.0.1,
                     haddock          >= 2.7.2,
                     base             >= 4   && < 5,
                     syb              >= 0.1.0.2,
                     time             >= 1.2.0.3,
                     old-locale       >= 1.0.0.2,
                     cereal           >= 0.3.0.0

    ghc-options:    -threaded -fspec-constr-count=16
    cpp-options:    -UDEBUG

    Other-Modules:    Paths_Hs2lib,
                      WinDll.Lib.NativeMapping,
                      WinDll.Lib.NativeMapping_Debug

    Default-Language: Haskell98

Executable Hs2lib-debug
    Main-is:         Hs2lib-debug.hs

    Build-Depends:   QuickCheck       >= 2.1.0.1,
                     directory        >= 1.0.0.3,
                     ghc-paths        >= 0.1.0.5,
                     filepath         >= 1.1.0.2,
                     random           >= 1.0.0.1,
                     process          >= 1.0.1.1,
                     ghc              >= 7.8.3,
                     mtl              >= 1.1.0.2,
                     containers       >= 0.2.0.0,
                     array            >= 0.2.0.0,
                     haskell-src-exts >= 1.13.5 && <= 1.15.0.1,
                     haddock          >= 2.7.2,
                     base             >= 4   && < 5,
                     syb              >= 0.1.0.2,
                     time             >= 1.2.0.3,
                     old-locale       >= 1.0.0.2,
                     cereal           >= 0.3.0.0

    ghc-options:    -threaded -fspec-constr-count=16 -rtsopts
    cpp-options:    -DDEBUG

    Other-Modules:    Paths_Hs2lib,
                      WinDll.Lib.NativeMapping,
                      WinDll.Lib.NativeMapping_Debug,
                      WinDll.Debug.Records,
                      WinDll.Debug.Stack

    Default-Language: Haskell98

Executable Hs2lib-testgen
    Main-is:         Tests/Exec/Hs2lib-testgen.hs

    Build-Depends:   QuickCheck       >= 2.1.0.1,
                     directory        >= 1.0.0.3,
                     ghc-paths        >= 0.1.0.5,
                     filepath         >= 1.1.0.2,
                     random           >= 1.0.0.1,
                     process          >= 1.0.1.1,
                     ghc              >= 7.8.3,
                     mtl              >= 1.1.0.2,
                     containers       >= 0.2.0.0,
                     array            >= 0.2.0.0,
                     haskell-src-exts >= 1.13.5 && <= 1.15.0.1,
                     haddock          >= 2.7.2,
                     base             >= 4   && < 5,
                     syb              >= 0.1.0.2,
                     time             >= 1.2.0.3,
                     old-locale       >= 1.0.0.2,
                     cereal           >= 0.3.0.0

    ghc-options:    -threaded -fspec-constr-count=16 -rtsopts
    cpp-options:    -UDEBUG

    Other-Modules:    Paths_Hs2lib,
                      WinDll.Lib.NativeMapping,
                      WinDll.Lib.NativeMapping_Debug,
                      WinDll.Debug.Records,
                      WinDll.Debug.Stack

    Default-Language: Haskell98

Test-Suite test-regression
    type:             exitcode-stdio-1.0
    main-is:          Tests/Test-Regression.hs
    Default-Language: Haskell98
    build-depends: base             >= 4   && < 5,
                   filepath         >= 1.1.0.2,
                   process          >= 1.0.1.1,
                   directory        >= 1.0.0.3

Test-Suite test-regression-debug
    type:             exitcode-stdio-1.0
    main-is:          Tests/Test-Regression-Debug.hs
    Default-Language: Haskell98
    build-depends: base             >= 4   && < 5,
                   filepath         >= 1.1.0.2,
                   process          >= 1.0.1.1,
                   directory        >= 1.0.0.3
""" > ${TMP}/Hs2lib-0.6.3/Hs2lib.cabal

echo -e """name:
  numeric-qq
version:
  0.1.0
synopsis:
  Quasi-quoters for numbers of different bases
description:
  Quasi-quoters for numbers of different bases
category:
  QuasiQoutes, Numeric
homepage:
  https://github.com/nikita-volkov/numeric-qq
bug-reports:
  https://github.com/nikita-volkov/numeric-qq/issues
author:
  Nikita Volkov <nikita.y.volkov@mail.ru>
maintainer:
  Nikita Volkov <nikita.y.volkov@mail.ru>
copyright:
  (c) 2014, Nikita Volkov
license:
  MIT
license-file:
  LICENSE
build-type:
  Simple
cabal-version:
  >=1.10


source-repository head
  type:
    git
  location:
    git://github.com/nikita-volkov/numeric-qq.git


library
  hs-source-dirs:
    library
  other-modules:
    NumericQQ.Prelude
  exposed-modules:
    NumericQQ
  build-depends:
    -- template-haskell:
    template-haskell == 2.*,
    -- debugging:
    loch-th == 0.2.*,
    placeholders == 0.1.*,
    -- general:
    base >= 4.5 && < 5
  default-extensions:
    Arrows, BangPatterns, ConstraintKinds, DataKinds, DefaultSignatures, DeriveDataTypeable, DeriveFunctor, DeriveGeneric, EmptyDataDecls, FlexibleContexts, FlexibleInstances, FunctionalDependencies, GADTs, GeneralizedNewtypeDeriving, ImpredicativeTypes, LambdaCase, LiberalTypeSynonyms, MultiParamTypeClasses, MultiWayIf, NoImplicitPrelude, NoMonomorphismRestriction, OverloadedStrings, PatternGuards, ParallelListComp, QuasiQuotes, RankNTypes, RecordWildCards, ScopedTypeVariables, StandaloneDeriving, TemplateHaskell, TupleSections, TypeFamilies, TypeOperators
  default-language:
    Haskell2010


test-suite internal-tests
  type:
    exitcode-stdio-1.0
  hs-source-dirs:
    executables
    library
  main-is:
    InternalTests.hs
  ghc-options:
    -threaded
  build-depends:
    HTF == 0.11.*,
    -- template-haskell:
    template-haskell == 2.*,
    -- debugging:
    loch-th == 0.2.*,
    placeholders == 0.1.*,
    -- general:
    base >= 4.5 && < 5
  default-extensions:
    Arrows, BangPatterns, ConstraintKinds, DataKinds, DefaultSignatures, DeriveDataTypeable, DeriveFunctor, DeriveGeneric, EmptyDataDecls, FlexibleContexts, FlexibleInstances, FunctionalDependencies, GADTs, GeneralizedNewtypeDeriving, ImpredicativeTypes, LambdaCase, LiberalTypeSynonyms, MultiParamTypeClasses, MultiWayIf, NoImplicitPrelude, NoMonomorphismRestriction, OverloadedStrings, PatternGuards, ParallelListComp, QuasiQuotes, RankNTypes, RecordWildCards, ScopedTypeVariables, StandaloneDeriving, TemplateHaskell, TupleSections, TypeFamilies, TypeOperators
  default-language:
    Haskell2010
""" > ${TMP}/numeric-qq-0.1.0/numeric-qq.cabal

echo -e """name:		haskell2010
version:	1.0.0.0
x-revision: 1
license:	BSD3
license-file:	LICENSE
maintainer:	libraries@haskell.org
bug-reports: http://hackage.haskell.org/trac/ghc/newticket?component=libraries/haskell2010
synopsis:	Compatibility with Haskell 2010
category:   Haskell2010
description:
        This package provides exactly the library modules defined by
        the Haskell 2010 standard.
homepage:	http://www.haskell.org/definition/
build-type:     Simple
Cabal-Version: >= 1.6

Library
    build-depends:	base >= 4.3 && < 4.6, array

    -- this hack adds a dependency on ghc-prim for Haddock.  The GHC
    -- build system doesn't seem to track transitive dependencies when
    -- running Haddock, and if we don't do this then Haddock can't
    -- find the docs for things defined in ghc-prim.
    if impl(ghc) {
       build-depends: ghc-prim
    }

    exposed-modules:
        Data.Array,
        Data.Char,
        Data.Complex,
        System.IO,
        System.IO.Error,
        Data.Ix,
        Data.List,
        Data.Maybe,
        Control.Monad,
        Data.Ratio,
        System.Environment,
        System.Exit,
        Numeric,
        Prelude,

        -- FFI modules
        Data.Int,
        Data.Word,
        Data.Bits,

        Foreign,
        Foreign.Ptr,
        Foreign.ForeignPtr,
        Foreign.StablePtr,
        Foreign.Storable,
        Foreign.C,
        Foreign.C.Error,
        Foreign.C.String,
        Foreign.C.Types,
        Foreign.Marshal,
        Foreign.Marshal.Alloc,
        Foreign.Marshal.Array,
        Foreign.Marshal.Error,
        Foreign.Marshal.Utils
    exposed: False
    extensions: PackageImports, CPP

source-repository head
    type:     darcs
    location: http://darcs.haskell.org/packages/haskell2010/

""" > ${TMP}/haskell2010-1.0.0.0/haskell2010.cabal

cd $TMP

tar -czf package_aeson-2.1.0.0_aeson-2.1.0.0.tar.gz aeson-2.1.0.0
tar -czf package_colors-0.1_colors-0.1.tar.gz colors-0.1
tar -czf package_colors-0.3.0.2_colors-0.3.0.2.tar.gz colors-0.3.0.2
tar -czf package_Hs2lib-0.6.3_Hs2lib-0.6.3.tar.gz Hs2lib-0.6.3
tar -czf package_numeric-qq-0.1.0_numeric-qq-0.1.0.tar.gz numeric-qq-0.1.0
tar -czf package_haskell2010-1.0.0.0_haskell2010-1.0.0.0.tar.gz haskell2010-1.0.0.0

# Move .tar.gz archives to a servable directory
mv *.tar.gz ../../$BASE_API

# Clean up removing tmp_dir
cd ../../
rm -r tmp_dir/
