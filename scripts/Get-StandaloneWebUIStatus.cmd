@echo off
setlocal
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0Get-StandaloneWebUIStatus.ps1" %*
