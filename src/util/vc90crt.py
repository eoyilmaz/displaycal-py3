# -*- coding: UTF-8 -*-

import os
import platform
import shutil

import winmanifest

name = "Microsoft.VC90.CRT"


def vc90crt_find_files():
    if platform.architecture()[0] == "64bit":
        arch = "amd64"
    else:
        arch = "x86"
    return winmanifest.Manifest(
        processorArchitecture=arch,
        name=name,
        publicKeyToken="1fc8b3b9a1e18e3b",
        version=[9, 0, 30729, 9625],
    ).find_files()


def vc90crt_copy_files(dest_dir):
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    for filename in vc90crt_find_files():
        dest = os.path.join(
            dest_dir,
            name + ".manifest"
            if filename.endswith(".manifest")
            else os.path.basename(filename),
        )
        if not os.path.exists(dest):
            shutil.copy2(filename, dest)
