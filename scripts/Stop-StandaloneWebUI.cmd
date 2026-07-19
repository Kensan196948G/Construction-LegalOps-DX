@echo off
setlocal
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0Stop-StandaloneWebUI.ps1" %*
