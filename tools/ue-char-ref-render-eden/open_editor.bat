@echo off
REM ============================================================
REM  Open the eden (Etheria UE4) editor INTERACTIVELY.
REM  -unattended skips the "modules out of date / rebuild?" gate
REM  (that gate is the only reason the GUI "wouldn't open" before:
REM   the prompt appeared and clicking No quit the editor).
REM
REM  Why interactive (not run_ue.bat headless): on this custom engine,
REM  spawning render actors (SkeletalMeshActor / SceneCapture2D / camera)
REM  crashes without an active Level Editor viewport. So the render
REM  scripts (01/02/03) must run inside this interactive editor with the
REM  3D viewport active.
REM
REM  Workflow:
REM    1) Run this .bat. Wait for the editor to fully open.
REM    2) CLICK inside the 3D viewport (top-left big black panel) and
REM       move the mouse over it, so the viewport becomes the active one.
REM    3) Window -> Developer Tools -> Output Log. In the command box type:
REM         py "D:\code\ue_scripts_eth_ue4\01_setup.py"
REM       then 02_test.py, then 03_batch.py the same way.
REM ============================================================
setlocal
set "UE=D:\eden_Deval_ArtSrc_Johnx\Engine\Binaries\Win64\UE4Editor.exe"
set "PROJ=D:\eden_Deval_ArtSrc_Johnx\GameProject\GameUE_cpp.uproject"
echo Opening eden editor (interactive, -unattended). First open is slow.
"%UE%" "%PROJ%" -unattended
endlocal
