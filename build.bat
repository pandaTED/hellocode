@echo off
echo Building HelloCode with Nuitka...
echo.

pip install nuitka ordered-set
if errorlevel 1 (
    echo Failed to install build dependencies
    exit /b 1
)

python build.py
if errorlevel 1 (
    echo Build failed
    exit /b 1
)

echo.
echo Build complete! Check the dist\ folder.
pause
