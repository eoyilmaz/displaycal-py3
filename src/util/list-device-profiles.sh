#!/bin/sh

echo -e "\033[37;40m*** Checking $HOME/.color/icc/devices\033[0m"
ls -l -G -h --color=always --group-directories-first -R $HOME/.color/icc/devices

echo -e "\033[37;40m*** Checking $HOME/.local/share/color/icc/devices\033[0m"
ls -l -G -h --color=always --group-directories-first -R $HOME/.local/share/color/icc/devices

echo -e "\033[37;40m*** Checking /usr/local/share/color/icc/devices\033[0m"
ls -l -G -h --color=always --group-directories-first -R /usr/local/share/color/icc/devices

echo -e "\033[37;40m*** Checking /usr/share/color/icc/devices\033[0m"
ls -l -G -h --color=always --group-directories-first -R /usr/share/color/icc/devices

echo -e "\033[37;40m*** Checking /var/lib/color/icc/devices\033[0m"
ls -l -G -h --color=always --group-directories-first -R /var/lib/color/icc/devices
