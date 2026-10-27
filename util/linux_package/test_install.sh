#!/bin/bash
# Smoke-test a built DEB/RPM in a clean container, with the package's own
# install step run without any network access, to make sure the post-install
# script never reaches out to PyPI or tries to compile anything (#983).
#
# Usage: util/linux_package/test_install.sh <image> <package_file>
#   e.g. util/linux_package/test_install.sh debian:trixie dist/displaycal.deb
#        util/linux_package/test_install.sh opensuse/tumbleweed dist/displaycal.rpm
#
# The distro dependencies are installed first (with network, from the
# distro's own repositories), the result is committed to a temporary image
# and the package itself is then installed in a --network none container.
# The distro's own Argyll package is installed alongside the dependencies, so
# a file conflict with it fails the test (#1022).

set -euo pipefail

IMAGE="${1:?usage: $0 <image> <package_file>}"
PACKAGE="$(realpath "${2:?usage: $0 <image> <package_file>}")"
PACKAGE_DIR="$(dirname "${PACKAGE}")"
PACKAGE_NAME="$(basename "${PACKAGE}")"
DEPS_IMAGE="displaycal-test-deps:$(echo "${IMAGE}" | tr ':/' '--')"

case "${PACKAGE_NAME}" in
  *.deb)
    DEPENDS="$(dpkg-deb --field "${PACKAGE}" Depends)"
    INSTALL_DEPS="apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get satisfy -y --no-install-recommends \"${DEPENDS}\" && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends argyll"
    INSTALL_PACKAGE="dpkg -i /pkg/${PACKAGE_NAME}"
    ;;
  *.rpm)
    DEPENDS="$(rpm -qpR "${PACKAGE}" | grep -v '^rpmlib(' | sed "s/.*/'&'/" | tr '\n' ' ')"
    # zypper hangs resolving rich deps like "(a or b)" given on its command
    # line, but resolves them fine from a package's metadata, so install the
    # package itself and drop it again (with everything its post-install
    # script created) before the offline install (#1022).
    INSTALL_DEPS="if command -v zypper >/dev/null; then
        zypper --non-interactive install --no-recommends --allow-unsigned-rpm /pkg/${PACKAGE_NAME} argyllcms
        rpm -e --nodeps --noscripts \$(rpm -qp --qf '%{NAME}' /pkg/${PACKAGE_NAME})
        rm -rf /opt/displaycal
      else
        dnf install -y ${DEPENDS} argyllcms
      fi"
    INSTALL_PACKAGE="rpm -i /pkg/${PACKAGE_NAME}"
    ;;
  *)
    echo "Unsupported package type: ${PACKAGE_NAME}" >&2
    exit 1
    ;;
esac

echo "::group::Installing the distro dependencies in ${IMAGE}"
CONTAINER="$(docker create --volume "${PACKAGE_DIR}:/pkg:ro" "${IMAGE}" sh -c "set -e
  ${INSTALL_DEPS}")"
trap 'docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true; docker rmi -f "${DEPS_IMAGE}" >/dev/null 2>&1 || true' EXIT
docker start --attach "${CONTAINER}"
docker commit "${CONTAINER}" "${DEPS_IMAGE}" >/dev/null
echo "::endgroup::"

echo "Installing ${PACKAGE_NAME} in ${IMAGE} without network access"
docker run --rm --network none \
  --volume "${PACKAGE_DIR}:/pkg:ro" \
  --env QT_QPA_PLATFORM=offscreen \
  "${DEPS_IMAGE}" \
  sh -c "set -e
    ${INSTALL_PACKAGE}
    /opt/displaycal/venv/bin/python -c '
import dbus, wx
import DisplayCAL.ui
import qtpy
from qtpy.QtWidgets import QApplication
app = QApplication([])
print(\"DisplayCAL imports OK, wx\", wx.version(), \"Qt\", qtpy.QT_VERSION)
'"
