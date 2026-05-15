@echo off
setlocal enabledelayedexpansion

REM Build single-file Windows EXEs for the IREPS scraper and GUI.
REM Run this file from the repository root in a prepared Python environment.

set "PROJECT_ROOT=%~dp0"
set "SCRAPING_DIR=%PROJECT_ROOT%Scraping"
set "PROGRAM_FILES_DIR=%SCRAPING_DIR%\Program_Files"
set "DIST_DIR=%SCRAPING_DIR%"
set "EXTRA_DATA=--add-data ""%PROGRAM_FILES_DIR%;Program_Files"""

if exist "%SCRAPING_DIR%\OCR" set "EXTRA_DATA=!EXTRA_DATA! --add-data ""%SCRAPING_DIR%\OCR;Program_Files\OCR"""

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

echo [1/5] Upgrading build tooling...
python -m pip install --upgrade pip pyinstaller
if errorlevel 1 goto :fail

echo [2/5] Installing Python requirements...
python -m pip install -r "%PROJECT_ROOT%requirements.txt"
if errorlevel 1 goto :fail

echo [3/5] Cleaning old build artifacts...
if exist "%PROJECT_ROOT%build" rmdir /s /q "%PROJECT_ROOT%build"
if exist "%PROJECT_ROOT%dist" rmdir /s /q "%PROJECT_ROOT%dist"
if exist "%SCRAPING_DIR%\build" rmdir /s /q "%SCRAPING_DIR%\build"
if exist "%SCRAPING_DIR%\dist" rmdir /s /q "%SCRAPING_DIR%\dist"
if exist "%SCRAPING_DIR%\__pycache__" rmdir /s /q "%SCRAPING_DIR%\__pycache__"
if exist "%SCRAPING_DIR%\IREPS_Tenders.spec" del /q "%SCRAPING_DIR%\IREPS_Tenders.spec"
if exist "%SCRAPING_DIR%\IREPS_scraping_gui.spec" del /q "%SCRAPING_DIR%\IREPS_scraping_gui.spec"
if exist "%SCRAPING_DIR%\IREPS_Tenders.exe" del /q "%SCRAPING_DIR%\IREPS_Tenders.exe"
if exist "%SCRAPING_DIR%\IREPS_scraping_gui.exe" del /q "%SCRAPING_DIR%\IREPS_scraping_gui.exe"

echo [4/5] Building one-file EXE from IREPS_Tenders.py...
pushd "%SCRAPING_DIR%"
pyinstaller --noconfirm --clean --onefile --name IREPS_Tenders ^
    !EXTRA_DATA! ^
    --add-data "app_logo.ico;." ^
    --collect-all selenium ^
    --collect-all chromedriver_autoinstaller ^
    --icon app_logo.ico ^
    --distpath "%DIST_DIR%" ^
    IREPS_Tenders.py
if errorlevel 1 (
    popd
    goto :fail
)

echo [5/5] Building one-file EXE from IREPS_scraping_gui.py...
pyinstaller --noconfirm --clean --onefile --windowed --name IREPS_scraping_gui ^
    !EXTRA_DATA! ^
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

echo.
echo Build complete.
echo Engine EXE (single file): %SCRAPING_DIR%\IREPS_Tenders.exe
echo GUI EXE (single file):    %SCRAPING_DIR%\IREPS_scraping_gui.exe
echo.
echo Both EXEs are built next to Scraping\Program_Files so existing relative runtime paths continue to work.
exit /b 0

:fail
echo.
echo Build failed with errorlevel %errorlevel%.
exit /b %errorlevel%
