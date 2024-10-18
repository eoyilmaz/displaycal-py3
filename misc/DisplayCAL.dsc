Standards-Version: 4.3.0
Debtransform-Tar: ${PACKAGE}-${VERSION}.tar.gz
Format: 1.0
Source: ${DEBPACKAGE}
Version: ${VERSION}-1
Binary: ${DEBPACKAGE}
Maintainer: ${MAINTAINER} <obs-packaging@${DOMAIN}>
Architecture: any
Build-Depends: build-essential, dbus, debhelper, dh-python, doc-base, libglib2.0-dev, pkg-config, libgtk-3-dev, libxxf86vm-dev, python3-dev, python3, python3-venv
Files:
 ffffffffffffffffffffffffffffffff 1 ${DEBPACKAGE}_${VERSION}.orig.tar.gz
 ffffffffffffffffffffffffffffffff 1 ${DEBPACKAGE}_${VERSION}-1.diff.tar.gz
