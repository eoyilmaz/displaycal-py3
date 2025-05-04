@echo off

if "%~1"=="" goto :usage

:loop
REM Convert TI1 through DCI-P3 D65 with Hybrid Log-Gamma (HLG) TRC
REM Obtain TI3 with DCI-P3 XYZ
fakeread "%~dp0..\DisplayCAL\ref\SMPTE431_P3_D65_HLG1000_cLUT.icm" "%~dpn1"

REM Reverse convert TI3 through Rec. 2020 with Hybrid Log-Gamma (HLG) TRC
REM Obtain TI3 with DCI-P3 RGB encoded in Rec. 2020 Hybrid Log-Gamma (HLG)
fakeread -U "%~dp0..\DisplayCAL\ref\Rec2020_HLG1000_cLUT.icm" "%~dpn1"

shift /1
if "%~1"=="" goto :end
goto :loop

:usage
echo Usage: %~nx0 testchart.ti1 [testchart.ti1...]
echo testchart         Base name for input[ti1]/output[ti3] file

:end
pause
