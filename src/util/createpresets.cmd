@echo off
setlocal

if not "%~1"=="" (
    if not "%~2"=="" goto single
)

call :createpreset "Default"      "default"
call :createpreset "eeColor"      "video_eeColor"
call :createpreset "Laptop"       "laptop"
call :createpreset "madVR"        "video_madVR"
call :createpreset "madVR ST.2084" "video_madVR_ST2084"
call :createpreset "Office & Web" "office_web"
call :createpreset "Photo"        "photo"
call :createpreset "Prisma"       "video_Prisma"
call :createpreset "ReShade"      "video_ReShade"
call :createpreset "Resolve"      "video_resolve"
call :createpreset "Resolve ST.2084" "video_resolve_ST2084_clip"
call :createpreset "Softproof"    "softproof"
call :createpreset "sRGB"         "sRGB"
call :createpreset "Video"        "video"
goto :EOF

:single
:createpreset
echo %1
colprof  -ql -aG -C "Created with DisplayCAL and ArgyllCMS" -D "DisplayCAL calibration preset: %~1" "%~dp0..\misc\ti3\%~2"
move /-Y "%~dp0..\misc\ti3\%~2.ic?" "%~dp0..\DisplayCAL\presets\%~2.icc" && if not exist "%~dp0..\misc\ti3\%~2.ic?" python "%~dp0update_presets.py" "%~2"
echo.
goto :EOF
