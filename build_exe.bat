@echo off
setlocal enabledelayedexpansion

REM Build a copy-paste portable Windows release for the IREPS scraper and GUI.
REM Run this file from the repository root in a prepared Python environment.

set "PROJECT_ROOT=%~dp0"
set "SCRAPING_DIR=%PROJECT_ROOT%Scraping"
set "PROGRAM_FILES_DIR=%SCRAPING_DIR%\Program_Files"
set "PORTABLE_DIR=%PROJECT_ROOT%IREPS_Tenders_Portable"
set "DIST_DIR=%PORTABLE_DIR%"
set "ZIP_PATH=%PROJECT_ROOT%IREPS_Tenders_Portable.zip"

if not exist "%SCRAPING_DIR%\IREPS_Tenders.py" (
    echo Could not find %SCRAPING_DIR%\IREPS_Tenders.py.
    exit /b 1
)

if not exist "%SCRAPING_DIR%\IREPS_scraping_gui.py" (
    echo Could not find %SCRAPING_DIR%\IREPS_scraping_gui.py.
    exit /b 1
)

if not exist "%PROGRAM_FILES_DIR%" (
    echo Could not find %PROGRAM_FILES_DIR%.
    exit /b 1
)

echo [1/8] Checking Python version...
python -c "import sys; v=sys.version_info; print(f'Python {v.major}.{v.minor}.{v.micro}'); sys.exit(0 if (v.major, v.minor) in ((3, 10), (3, 11), (3, 12), (3, 13)) else 1)"
if errorlevel 1 (
    echo.
    echo Unsupported Python version. This project currently builds with Python 3.10, 3.11, 3.12, or 3.13.
    echo Python 3.14+ is not supported by the current pinned build toolchain.
    echo Create a fresh virtual environment with a supported Python version, then run build_exe.bat again.
    exit /b 1
)

echo [2/8] Upgrading build tooling...
python -m pip install --upgrade pip setuptools wheel pyinstaller
if errorlevel 1 goto :fail

echo [3/8] Installing Python requirements...
python -m pip install -r "%PROJECT_ROOT%requirements.txt"
if errorlevel 1 goto :fail

echo [4/8] Cleaning old build artifacts...
if exist "%PROJECT_ROOT%build" rmdir /s /q "%PROJECT_ROOT%build"
if exist "%PROJECT_ROOT%dist" rmdir /s /q "%PROJECT_ROOT%dist"
if exist "%SCRAPING_DIR%\build" rmdir /s /q "%SCRAPING_DIR%\build"
if exist "%SCRAPING_DIR%\dist" rmdir /s /q "%SCRAPING_DIR%\dist"
if exist "%PORTABLE_DIR%" rmdir /s /q "%PORTABLE_DIR%"
if exist "%ZIP_PATH%" del /q "%ZIP_PATH%"
if exist "%SCRAPING_DIR%\__pycache__" rmdir /s /q "%SCRAPING_DIR%\__pycache__"
if exist "%SCRAPING_DIR%\IREPS_Tenders.spec" del /q "%SCRAPING_DIR%\IREPS_Tenders.spec"
if exist "%SCRAPING_DIR%\IREPS_scraping_gui.spec" del /q "%SCRAPING_DIR%\IREPS_scraping_gui.spec"
if exist "%SCRAPING_DIR%\IREPS_Tenders.exe" del /q "%SCRAPING_DIR%\IREPS_Tenders.exe"
if exist "%SCRAPING_DIR%\IREPS_scraping_gui.exe" del /q "%SCRAPING_DIR%\IREPS_scraping_gui.exe"

echo [5/8] Building portable engine EXE from IREPS_Tenders.py...
pushd "%SCRAPING_DIR%"
pyinstaller --noconfirm --clean --onefile --name IREPS_Tenders ^
    --add-data "app_logo.ico;." ^
    --collect-all selenium ^
    --collect-all chromedriver_autoinstaller ^
    --collect-all torch ^
    --collect-all torchvision ^
    --icon app_logo.ico ^
    --distpath "%DIST_DIR%" ^
    IREPS_Tenders.py
if errorlevel 1 (
    popd
    goto :fail
)

echo [6/8] Building portable GUI EXE from IREPS_scraping_gui.py...
pyinstaller --noconfirm --clean --onefile --windowed --name IREPS_scraping_gui ^
    --add-data "app_logo.ico;." ^
    --collect-all customtkinter ^
    --collect-all selenium ^
    --collect-all chromedriver_autoinstaller ^
    --icon app_logo.ico ^
    --distpath "%DIST_DIR%" ^
    IREPS_scraping_gui.py
if errorlevel 1 (
    popd
    goto :fail
)
popd

echo [7/8] Copying runtime files into portable folder...
robocopy "%PROGRAM_FILES_DIR%" "%PORTABLE_DIR%\Program_Files" /E /XD "ireps_temp" "consolelog" /XF "*.log"
set "ROBOCOPY_EXIT=%ERRORLEVEL%"
if %ROBOCOPY_EXIT% GEQ 8 goto :fail
copy /Y "%SCRAPING_DIR%\app_logo.ico" "%PORTABLE_DIR%\app_logo.ico" >nul
> "%PORTABLE_DIR%\Start_IREPS_Tenders.bat" echo @echo off
>> "%PORTABLE_DIR%\Start_IREPS_Tenders.bat" echo cd /d "%%~dp0"
>> "%PORTABLE_DIR%\Start_IREPS_Tenders.bat" echo start "" "IREPS_scraping_gui.exe"
> "%PORTABLE_DIR%\README_FIRST.txt" echo IREPS Tenders portable Windows build
>> "%PORTABLE_DIR%\README_FIRST.txt" echo.
>> "%PORTABLE_DIR%\README_FIRST.txt" echo Copy this whole folder to another Windows computer and run Start_IREPS_Tenders.bat or IREPS_scraping_gui.exe.
>> "%PORTABLE_DIR%\README_FIRST.txt" echo Keep Program_Files next to the EXE files because it contains Configration.json, Organization_list.txt, and captcha_model.pth.
>> "%PORTABLE_DIR%\README_FIRST.txt" echo Google Chrome is still required for Selenium browser automation.

echo [8/8] Creating portable zip...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%PORTABLE_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force"
if errorlevel 1 goto :fail

echo.
echo Build complete.
echo Portable folder: %PORTABLE_DIR%
echo Portable zip:    %ZIP_PATH%
echo GUI EXE:         %PORTABLE_DIR%\IREPS_scraping_gui.exe
echo Engine EXE:      %PORTABLE_DIR%\IREPS_Tenders.exe
echo.
echo Copy the portable folder or zip to another Windows computer, keep Program_Files beside the EXEs, and run Start_IREPS_Tenders.bat.
exit /b 0

:fail
echo.
echo Build failed with errorlevel %errorlevel%.
exit /b %errorlevel%
