@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-OMA.ps1"
if errorlevel 1 pause
