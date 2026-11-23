@echo off
setlocal
set "LONGWAVE_HOME=%~dp0..\..\data"
"%~dp0runtime\python.exe" -m longwave phone %*
