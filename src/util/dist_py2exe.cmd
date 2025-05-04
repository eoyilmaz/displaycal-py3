@echo off

REM Make sure __version__.py is current
python setup.py

for /F usebackq %%a in (`python -c "import sys;print sys.version[:3]"`) do (
    set python_version=%%a
)

for /F usebackq %%a in (`python -c "from DisplayCAL import meta;print meta.version"`) do (
    set version=%%a
)

REM Standalone executable
if not exist dist\py2exe.win32-py%python_version%\DisplayCAL-%version% (
    python setup.py bdist_standalone inno 2>&1 | tee DisplayCAL-%version%.bdist_standalone-py%python_version%.log
    if exist codesigning\sign.cmd (
    call codesigning\sign.cmd dist\py2exe.win32-py%python_version%\DisplayCAL-%version%\*.exe
    call codesigning\sign.cmd dist\py2exe.win32-py%python_version%\DisplayCAL-%version%\lib\DisplayCAL.lib*.python*.RealDisplaySizeMM.pyd
    )
)

REM Standalone executable - Setup
REM if not exist dist\DisplayCAL-%version%-Setup.exe if not exist dist\%version%\DisplayCAL-%version%-Setup.exe (
REM 	"C:\Program Files (x86)\Inno Setup 5\Compil32.exe" /cc dist/DisplayCAL-Setup-py2exe.win32-py%python_version%.iss
REM )
