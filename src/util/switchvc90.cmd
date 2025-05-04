@echo off
setlocal
pushd "%SystemRoot%\WinSxS"
for /D %%a in (. Manifests Policies) do (
    pushd "%%~a"
    for /D %%b in (*.VC90.*) do (
        call :bak "%%~b"
    )
    for %%b in (*.VC90.*) do (
        call :bak "%%~b"
    )
    popd
)
popd
pause
goto :EOF

:bak
if /i "%~x1"==".bak" (
    echo %~1
    echo -^> %~n1
    ren "%~1" "%~n1"
) else (
    echo %~1
    echo -^> %~1.bak
    ren "%~1" "%~1.bak"
)
echo.
goto :EOF