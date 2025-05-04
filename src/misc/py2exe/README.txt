Patches for py2exe 0.6.9
Copy these files into the py2exe directory, overwriting existing files.

boot_common.py
The original stdout and stderr redirection does not implement the 'isatty'
method. The patched file adds it.

build_exe.py
The add_icon method is faulty. When adding icons to an exe, it begins counting
at index 0, which is wrong (it should start at 1). Also, it does not reset the
index for additional targets, so if the first target got 7 icons (index 0..6)
then the next target's icon index will begin at 7. The patched file works around
those problems by not using the faulty implementation, but a tried-and-tested
one from PyInstaller (icon.py) instead.
