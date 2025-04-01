@echo off

REM Make sure __version__.py is current
python setup.py

for /F usebackq %%a in (`python -c "import sys;print sys.version[:3]"`) do (
    set python_version=%%a
)

for /F usebackq %%a in (`python -c "from DisplayCAL import meta;print meta.version"`) do (
    set version=%%a
)

if exist dist\py2exe.win32-py%python_version%\DisplayCAL-%version% (
    if exist codesigning\sign.cmd (
        call codesigning\sign.cmd dist\py2exe.win32-py%python_version%\DisplayCAL-%version%\*.exe
    )
)
