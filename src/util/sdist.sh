#!/bin/sh

version=`python3 -c "from DisplayCAL import meta;print meta.version"`

# Source tarball
./setup.py sdist 0install $* --use-distutils 2>&1 | tee DisplayCAL-$version.sdist.log
