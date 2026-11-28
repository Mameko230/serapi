@echo off
setlocal
cd /d "%~dp0"
set "ELECTRON_RUN_AS_NODE="
rem This machine needs --no-sandbox for Electron to start.
set "SERAPI_DISABLE_SINGLE_INSTANCE=1"
start "" "Serapi.exe" --no-sandbox
endlocal
