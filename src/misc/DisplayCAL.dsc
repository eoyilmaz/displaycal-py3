Standards-Version: 4.3.0
Debtransform-Tar: ${PACKAGE}-${VERSION}.tar.gz
Format: 1.0
Source: ${DEBPACKAGE}
Version: ${VERSION}-1
Binary: ${DEBPACKAGE}
Maintainer: ${MAINTAINER} <obs-packaging@${DOMAIN}>
Architecture: any
Build-Depends: debhelper, dh-python, doc-base, python2.7-dev, python, libxinerama-dev, libxrandr-dev, libxxf86vm-dev
Files: 
 ffffffffffffffffffffffffffffffff 1 ${DEBPACKAGE}_${VERSION}.orig.tar.gz
 ffffffffffffffffffffffffffffffff 1 ${DEBPACKAGE}_${VERSION}-1.diff.tar.gz
