#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import os
import re
import shutil
from hashlib import sha256


def sha256sum(filename, blocksize=65536):
    filehash = sha256()
    with open(filename, "rb") as f:
        for block in iter(lambda: f.read(blocksize), ""):
            filehash.update(block)
    return filehash.hexdigest()


def main():
    dist = glob.glob(os.path.join("dist", "DisplayCAL-*"))
    for entry in dist:
        version = re.search(r"\d+(?:\.\d+){3}", entry)
        if version:
            version = version.group()
            version_dir = os.path.join("dist", version)
            if not os.path.isdir(version_dir):
                os.mkdir(version_dir)
            shutil.move(entry, version_dir)
    sha256sums = os.path.join("dist", "sha256sums.txt")
    if os.path.isfile(sha256sums):
        # Update checksum file
        with open(sha256sums, "a") as f:
            for filename in glob.glob(os.path.join(version_dir, "*")):
                # Use standard sha256sum output format (binary mode)
                f.write(sha256sum(filename) + " *" + os.path.basename(filename) + "\n")


if __name__ == "__main__":
    main()
