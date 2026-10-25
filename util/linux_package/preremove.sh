#!/bin/sh
# DEB/RPM pre-remove script.
#
# Only drop the venv on an actual removal. On an RPM upgrade the old package's
# %preun runs *after* the new package's %post, so removing it then would wipe
# the venv that was just set up ($1 is the number of versions left installed,
# 0 on erase). A DEB upgrade calls this with "upgrade" and the new postinst
# recreates the venv anyway.
case "$1" in
  0 | remove | purge | "") rm -rf /opt/displaycal/venv ;;
esac
if [ -d /etc/udev/rules.d ]; then
  udevadm control --reload-rules 2>/dev/null || true
fi
