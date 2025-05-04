#!/bin/sh

echo -e "\033[33;40m*** Checking $HOME/.config/autostart\033[0m"
ls -l -G -h --color=always --group-directories-first -R $HOME/.config/autostart

echo -e "\033[33;40m*** Checking /etc/xdg/autostart\033[0m"
ls -l -G -h --color=always --group-directories-first -R /etc/xdg/autostart
