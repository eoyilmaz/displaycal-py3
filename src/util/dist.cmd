@echo off

REM Make sure __version__.py is current
python setup.py

for /F usebackq %%a in (`python -c "import sys;print sys.version[:3]"`) do (
    set python_version=%%a
)

for /F usebackq %%a in (`python -c "from DisplayCAL import meta;print meta.version"`) do (
    set version=%%a
)

for /F usebackq %%a in (`python -c "from meta import version_tuple;print '.'.join(str(n) for n in version_tuple[:2] + (str(version_tuple[2]) + str(version_tuple[3]), ))"`) do (
    set msi_version=%%a
)

REM Source tarball
if not exist dist\DisplayCAL-%version%.tar.gz if not exist dist\%version%\DisplayCAL-%version%.tar.gz (
    python setup.py sdist --format=gztar --use-distutils 2>&1 | tee DisplayCAL-%version%.sdist.log
)

REM Create openSUSE build service control files and update 0install feeds
REM python setup.py buildservice 0install --stability=stable
python setup.py buildservice --stability=stable

REM Standalone executable
if not exist dist\py2exe.win32-py%python_version%\DisplayCAL-%version% (
    python setup.py bdist_standalone inno 2>&1 | tee DisplayCAL-%version%.bdist_standalone-py%python_version%.log
    if exist codesigning\sign.cmd (
        call codesigning\sign.cmd dist\py2exe.win32-py%python_version%\DisplayCAL-%version%\*.exe
        call codesigning\sign.cmd dist\py2exe.win32-py%python_version%\DisplayCAL-%version%\lib\DisplayCAL.lib*.python*.RealDisplaySizeMM.pyd
    )
)

REM Standalone executable - Setup
if not exist dist\DisplayCAL-%version%-Setup.exe if not exist dist\%version%\DisplayCAL-%version%-Setup.exe (
    "C:\Program Files (x86)\Inno Setup 5\Compil32.exe" /cc dist/DisplayCAL-Setup-py2exe.win32-py%python_version%.iss
)

REM Standalone executable - ZIP
if not exist dist\DisplayCAL-%version%-win32.zip if not exist dist\%version%\DisplayCAL-%version%-win32.zip (
    pushd dist\py2exe.win32-py%python_version%
    zip -9 -r ..\DisplayCAL-%version%-win32.zip DisplayCAL-%version%
    popd
)

if "%~1"=="bdist_msi" (
    REM Python 2.6 MSI
    if not exist dist\DisplayCAL-%msi_version%.win32-py2.6.msi if not exist dist\%version%\DisplayCAL-%msi_version%.win32-py2.6.msi (
        C:\Python26\python.exe setup.py bdist_msi --use-distutils 2>&1 | tee DisplayCAL-%msi_version%.msi-py2.6.log
        C:\Python26\python.exe setup.py finalize_msi 2>&1 | tee -a DisplayCAL-%msi_version%.msi-py2.6.log
    )

    REM Python 2.7 MSI
    if not exist dist\DisplayCAL-%msi_version%.win32-py2.7.msi if not exist dist\%version%\DisplayCAL-%msi_version%.win32-py2.7.msi (
        C:\Python27\python.exe setup.py bdist_msi --use-distutils 2>&1 | tee DisplayCAL-%msi_version%.msi-py2.7.log
        C:\Python27\python.exe setup.py finalize_msi 2>&1 | tee -a DisplayCAL-%msi_version%.msi-py2.7.log
    )
)

if "%~1"=="bdist_wininst" (
    REM Python 2.6 Installer
    if not exist dist\DisplayCAL-%version%.win32-py2.6.exe if not exist dist\%version%\DisplayCAL-%version%.win32-py2.6.exe (
        C:\Python26\python.exe setup.py bdist_wininst --user-access-control=auto --use-distutils 2>&1 | tee DisplayCAL-%version%.wininst-py2.6.log
    )

    REM Python 2.7 Installer
    if not exist dist\DisplayCAL-%version%.win32-py2.7.exe if not exist dist\%version%\DisplayCAL-%version%.win32-py2.7.exe (
        C:\Python27\python.exe setup.py bdist_wininst --user-access-control=auto --use-distutils 2>&1 | tee DisplayCAL-%version%.wininst-py2.7.log
    )
)

REM Cleanup
python util\tidy_dist.py
