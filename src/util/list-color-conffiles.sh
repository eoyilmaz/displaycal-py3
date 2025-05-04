#!/bin/sh

echo -e "\033[33;40m*** Checking $HOME/.config/color.jcnf\033[0m"
ls -l -G -h --color=always $HOME/.config/color.jcnf

echo -e "\033[33;40m*** Checking $HOME/.config/color/device-profiles.conf\033[0m"
ls -l -G -h --color=always $HOME/.config/color/device-profiles.conf

echo -e "\033[33;40m*** Checking $HOME/.config/gnome-color-manager/device-profiles.conf\033[0m"
ls -l -G -h --color=always $HOME/.config/gnome-color-manager/device-profiles.conf

echo -e "\033[33;40m*** Checking /etc/xdg/color.jcnf\033[0m"
ls -l -G -h --color=always /etc/xdg/color.jcnf
