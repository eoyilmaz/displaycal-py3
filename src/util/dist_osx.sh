#!/bin/sh

# Make sure __version__.py is current
./setup.py

version=`python2 -c "from DisplayCAL import meta;print meta.version"`

# Source tarball
# COPYFILE_DISABLE=1   Prevent extended file attributes (metadata) being added
#                      as "dotunderscore" (._<filename>) files to the tarball.
#                      If those files are present in the archive, a digest
#                      calculated under Mac OS X will not match one calculated
#                      under other systems because the digest will be calculated
#                      from extracted archive contents and Mac OS X tar will add
#                      dotunderscore files back as file attributes while other
#                      systems will see the additional dotunderscore files.
COPYFILE_DISABLE=1 ./setup.py sdist --use-distutils 2>&1 | tee DisplayCAL-$version.sdist.log
tar tf dist/DisplayCAL-$version.tar.gz | grep "\._" && { echo "WARNING: DOTUNDERSCORE FILES FOUND IN ARCHIVE"; exit 1; }
#./setup.py 0install --stability=stable 2>&1 | tee DisplayCAL-$version.sdist.log

# App bundle
./setup.py bdist_standalone 2>&1 | tee DisplayCAL-$version.bdist_standalone_osx.log

# DMG
#./setup.py bdist_appdmg 2>&1 | tee -a DisplayCAL-$version.bdist_standalone_osx.log

# PKG
./setup.py bdist_pkg 2>&1 | tee -a DisplayCAL-$version.bdist_standalone_osx.log

# Cleanup
util/tidy_dist.py
