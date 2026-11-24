@echo off
rem Double-click to start the whole demo. Options: start_demo.bat -Camera webcam ^| -Camera video ^| -WebSockets ^| -Hotspot ^| -NoDesktop ^| -NoMobile
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_demo.ps1" %*
