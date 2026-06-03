@echo off
REM ============================================================
REM  Headless-run a UE Python script in the eden (Etheria UE4) project.
REM
REM  Uses the FULL EDITOR + -ExecCmds="py <script>" (NOT -run=pythonscript,
REM  and NOT -ExecutePythonScript): spawning actors needs a Level Editor
REM  viewport. A commandlet has none; -ExecutePythonScript runs too early
REM  (before the viewport exists). -ExecCmds runs AFTER full editor init,
REM  when GCurrentLevelEditingViewportClient is valid, so spawn works.
REM  -unattended skips the "modules out of date / rebuild?" gate.
REM  UE_HEADLESS_QUIT=1 makes the script quit the editor when done.
REM
REM  Usage:  run_ue.bat 01_setup.py
REM          run_ue.bat 03_batch.py
REM  Script path must NOT contain spaces (ExecutePythonScript limitation).
REM  NOTE: keep this .bat ASCII-only (cmd.exe reads .bat as system codepage).
REM ============================================================
setlocal
set "UE=D:\eden_Deval_ArtSrc_Johnx\Engine\Binaries\Win64\UE4Editor-Cmd.exe"
set "PROJ=D:\eden_Deval_ArtSrc_Johnx\GameProject\GameUE_cpp.uproject"

if "%~1"=="" (
  echo Usage: %~nx0 ^<script.py^>   e.g. %~nx0 03_batch.py
  exit /b 1
)
set "SCRIPT=%~1"
if not exist "%SCRIPT%" set "SCRIPT=%~dp0%~1"
if not exist "%SCRIPT%" ( echo [run_ue] script not found: %~1 & exit /b 1 )

set "UE_HEADLESS_QUIT=1"
echo [run_ue] script : %SCRIPT%
echo [run_ue] Full editor headless. First run ~10-15 min (compiles ~10k shaders;
echo [run_ue] later runs are much faster once the DDC cache is warm).
echo [run_ue] An editor WINDOW will open (needed for a valid viewport so actor
echo [run_ue] spawning works). DO NOT close it - it quits itself when done.
echo.

"%UE%" "%PROJ%" -ExecCmds="py %SCRIPT%" -unattended -nopause -stdout -FullStdOutLogOutput

echo.
echo [run_ue] exit code=%ERRORLEVEL%  (rely on [setup]/[batch] DONE in the log)
endlocal
