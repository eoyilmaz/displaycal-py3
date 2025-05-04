#!/bin/bash

echo -e "\033[37;40m*** Checking $HOME/.config\033[0m"

ls -l -G -h --color=always --group-directories-first -R $HOME/.config/autostart/*DisplayCAL* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.config/DisplayCAL 2>/dev/null && echo

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking $HOME/.local\033[0m"

ls -l -G -h --color=always $HOME/.local/bin/displaycal* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.local/lib*/python*/*-packages/DisplayCAL* 2>/dev/null && echo

ls -l -G -h --color=always $HOME/.local/share/applications/DisplayCAL*.desktop 2>/dev/null && echo

ls -l -G -h --color=always $HOME/.local/share/applications/zeroinstall-displaycal.desktop 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.local/share/man/man1/displaycal* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.local/share/pyshared/DisplayCAL 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.local/share/pyshared-data/displaycal 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first $HOME/.local/share/DisplayCAL/* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.local/share/doc/displaycal 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.local/share/doc/DisplayCAL* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.local/share/doc/packages/DisplayCAL* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R $HOME/.local/share/doc-base/displaycal* 2>/dev/null && echo

ls -l -G -h --color=always $HOME/.local/share/icons/hicolor/*/apps/DisplayCAL* 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /etc/hotplug/usb\033[0m"

ls -l -G -h --color=always --group-directories-first -R /etc/hotplug/usb/Argyll* 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /etc/udev\033[0m"

ls -l -G -h --color=always --group-directories-first -R /etc/udev/*/*-Argyll.* 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /etc/xdg/autostart\033[0m"

ls -l -G -h --color=always --group-directories-first -R /etc/xdg/autostart/*DisplayCAL* 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /usr/local\033[0m"

ls -l -G -h --color=always /usr/local/bin/displaycal* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/lib*/python*/*-packages/DisplayCAL* 2>/dev/null && echo

ls -l -G -h --color=always /usr/local/share/applications/DisplayCAL*.desktop 2>/dev/null && echo

ls -l -G -h --color=always /usr/local/share/applications/zeroinstall-displaycal.desktop 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/share/man/man1/displaycal* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/share/pyshared/DisplayCAL 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/share/pyshared-data/displaycal 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/share/DisplayCAL 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/share/doc/displaycal 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/share/doc/DisplayCAL* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/share/doc/packages/DisplayCAL* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/local/share/doc-base/displaycal* 2>/dev/null && echo

ls -l -G -h --color=always /usr/local/share/icons/hicolor/*/apps/DisplayCAL* 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /usr\033[0m"

ls -l -G -h --color=always /usr/bin/displaycal* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/lib*/python*/*-packages/DisplayCAL* 2>/dev/null && echo

ls -l -G -h --color=always /usr/share/applications/DisplayCAL*.desktop 2>/dev/null && echo

ls -l -G -h --color=always /usr/share/applications/zeroinstall-displaycal 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/share/man/man1/displaycal* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/share/pyshared/DisplayCAL 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/share/pyshared-data/displaycal 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/share/DisplayCAL 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/share/doc/displaycal 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/share/doc/DisplayCAL* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/share/doc/packages/DisplayCAL* 2>/dev/null && echo

ls -l -G -h --color=always --group-directories-first -R /usr/share/doc-base/displaycal* 2>/dev/null && echo

ls -l -G -h --color=always /usr/share/icons/hicolor/*/apps/DisplayCAL* 2>/dev/null

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** Checking /var/lib/doc-base\033[0m"

ls -l -G -h --color=always --group-directories-first -R /var/lib/doc-base/documents/displaycal* 2>/dev/null && echo

echo "--------------------------------------------------------------------------------"

echo -e "\033[37;40m*** All done\033[0m"
