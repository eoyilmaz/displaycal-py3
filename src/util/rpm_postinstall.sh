#!/bin/sh

# Update icon cache and menu
/bin/touch --no-create %{_datadir}/icons/hicolor &> /dev/null || true
which xdg-icon-resource &> /dev/null && xdg-icon-resource forceupdate || true
which xdg-desktop-menu &> /dev/null && xdg-desktop-menu forceupdate || true
