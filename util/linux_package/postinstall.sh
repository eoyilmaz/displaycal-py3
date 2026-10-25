#!/bin/sh
# DEB/RPM post-install script.
#
# Sets up DisplayCAL's venv purely from what the package itself ships
# (/opt/displaycal/wheels, see vendor_wheels.sh) plus the distro packages it
# depends on (wxPython and dbus-python, reached through
# --system-site-packages). It never touches the network and never compiles
# anything, `--no-index` makes pip fail instead of falling back to PyPI.
set -e

INSTALL_DIR=/opt/displaycal
WHEELS_DIR="${INSTALL_DIR}/wheels"
VENV_DIR="${INSTALL_DIR}/venv"

PYTHON_VERSION="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
REQUIREMENTS="${WHEELS_DIR}/requirements-${PYTHON_VERSION}.txt"
if [ ! -f "${REQUIREMENTS}" ]; then
  echo "DisplayCAL: this package has no bundled dependencies for Python ${PYTHON_VERSION}, supported versions are:" >&2
  ls "${WHEELS_DIR}" | sed -n 's/^requirements-\(.*\)\.txt$/  \1/p' >&2
  echo "DisplayCAL: please use the AppImage or Flatpak instead." >&2
  exit 1
fi

echo "DisplayCAL: setting up virtual environment in ${VENV_DIR} ..."
python3 -m venv --clear --system-site-packages "${VENV_DIR}"
PIP="${VENV_DIR}/bin/pip"

echo "DisplayCAL: installing the bundled dependencies ..."
"${PIP}" install \
  --disable-pip-version-check \
  --no-index \
  --find-links "${WHEELS_DIR}" \
  --requirement "${REQUIREMENTS}"

# --no-deps, wxPython and dbus-python come from the distro and their versions
# don't necessarily match the pins in DisplayCAL's own metadata.
"${PIP}" install \
  --disable-pip-version-check \
  --no-index \
  --no-deps \
  "${INSTALL_DIR}"/displaycal-*.whl

echo "DisplayCAL: install complete."
if [ -d /etc/udev/rules.d ]; then
  udevadm control --reload-rules 2>/dev/null || true
fi
