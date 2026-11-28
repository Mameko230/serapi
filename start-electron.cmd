@echo off
setlocal
set "TARGET=%~dp0electron\dist\win-unpacked\run-serapi.cmd"
if not exist "%TARGET%" (
  echo Electron build not found:
  echo   %TARGET%
  echo Run: cd electron ^&^& npm run dist:dir
  pause
  exit /b 1
)
call "%TARGET%"
endlocal
