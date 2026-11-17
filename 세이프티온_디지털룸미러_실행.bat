@echo off
title SafetyON Electronic Digital Rearview Mirror Simulator
cd /d "C:\Users\LENOVO\Desktop\SafetyOn_Digital_Mirror"
if not exist "safetyon_cms_dsm.py" (
    cd /d "C:\Users\LENOVO\Desktop\2. ?? ? ????? (????? ??)\SafetyOn_Digital_Mirror"
)
py -3 safetyon_cms_dsm.py
if %errorlevel% neq 0 (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" safetyon_cms_dsm.py
)
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] An error occurred while running the simulator.
    pause
)