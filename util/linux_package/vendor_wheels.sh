#!/bin/bash
# Download every runtime dependency of DisplayCAL as a prebuilt wheel, so the
# DEB/RPM post-install script can set up its venv fully offline, without ever
# reaching PyPI or compiling anything as root.
#
# Usage: util/linux_package/vendor_wheels.sh <dest_dir>
#
# For every supported target Python a pinned requirements-<X.Y>.txt is
# resolved with `uv pip compile` (which, unlike `pip download`, evaluates the
# `python_version` markers in requirements.txt against the target Python
# rather than the one running this script), and the wheels it pins are
# downloaded next to it.
#
# wxPython and dbus-python are left out, PyPI only has source distributions of
# them for Linux, so the packages depend on the distro's own builds instead
# (python3-wxgtk4.0/python3-dbus on Debian, python3-wxpython4/python3-dbus on
# Fedora, python3-wxPython/python3-dbus-python on openSUSE), which the venv
# sees through --system-site-packages.
#
# PySide6 is swapped for PySide6-Essentials, DisplayCAL only uses QtCore,
# QtGui and QtWidgets, so the much bigger PySide6-Addons isn't needed.

set -euo pipefail

DEST_DIR="${1:?usage: $0 <dest_dir>}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# Keep in sync with requires-python in pyproject.toml.
PYTHON_VERSIONS="3.11 3.12 3.13 3.14"

# glibc floor of the bundled wheels. PySide6 >= 6.10 is only published as
# manylinux_2_34, which still covers Debian 12, Ubuntu 22.04+ and Fedora.
GLIBC_MINOR=34
ARCH=x86_64

mkdir -p "${DEST_DIR}"

BASE_REQUIREMENTS="$(mktemp)"
trap 'rm -f "${BASE_REQUIREMENTS}"' EXIT
grep -vE '^[[:space:]]*(#|$)|^(wxPython|dbus-python)[[:space:]=<>!~;]' \
  "${REPO_ROOT}/requirements.txt" \
  | sed -E 's/^PySide6([[:space:]=<>!~;])/PySide6-Essentials\1/' \
  > "${BASE_REQUIREMENTS}"

# `pip download --platform` doesn't expand a manylinux tag to the older ones it
# is compatible with, so list them all.
PLATFORM_ARGS=()
for ((minor = GLIBC_MINOR; minor >= 17; minor--)); do
  PLATFORM_ARGS+=(--platform "manylinux_2_${minor}_${ARCH}")
done
PLATFORM_ARGS+=(--platform "manylinux2014_${ARCH}" --platform "linux_${ARCH}")

for python_version in ${PYTHON_VERSIONS}; do
  lock_file="${DEST_DIR}/requirements-${python_version}.txt"
  echo "Resolving dependencies for Python ${python_version} ..."
  uv pip compile \
    --quiet \
    --no-header \
    --no-annotate \
    --only-binary :all: \
    --python-version "${python_version}" \
    --python-platform "${ARCH}-manylinux_2_${GLIBC_MINOR}" \
    --output-file "${lock_file}" \
    "${BASE_REQUIREMENTS}"

  echo "Downloading wheels for Python ${python_version} ..."
  python -m pip download \
    --disable-pip-version-check \
    --no-deps \
    --only-binary :all: \
    --implementation cp \
    --python-version "${python_version}" \
    "${PLATFORM_ARGS[@]}" \
    --dest "${DEST_DIR}" \
    --requirement "${lock_file}"
done
