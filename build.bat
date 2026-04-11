@echo off
echo ============================================
echo  Midi Controller - Build Script
echo ============================================
echo.

echo [1/2] Installing / updating dependencies...
pip install --quiet pygame customtkinter pyinstaller
echo Done.
echo.

echo [2/2] Building executable...
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "MidiController" ^
  --collect-data customtkinter ^
  --hidden-import pygame.midi ^
  main.py

echo.
if exist "dist\MidiController.exe" (
    echo SUCCESS - dist\MidiController.exe is ready.
) else (
    echo BUILD FAILED - check output above for errors.
)
echo.
pause
