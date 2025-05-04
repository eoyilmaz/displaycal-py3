@echo off

:loop
if "%~1"=="" goto :end
pushd "%~1"
for %%a in (*.png) do (
    ren "%%~a" "%%~na.old"
    pngcrush -rem alla -rem text -rem iCCP "%%~na.old" "%%~a"
    del "%%~na.old"
)
popd
shift /1
goto :loop

:end
pause
