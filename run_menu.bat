@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
set "VENV_DIR=%ROOT_DIR%venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
set "REQUIREMENTS_FILE=%ROOT_DIR%requirements.txt"

title IREPS Tenders Control Menu

:MENU
cls
echo ============================================================
echo              IREPS Tenders Control Menu
echo ============================================================
echo Root folder : %ROOT_DIR%
echo Venv folder : %VENV_DIR%
if exist "%PYTHON_EXE%" (
    echo Venv status : Ready
) else (
    echo Venv status : Missing - choose option 1 before running apps
)
echo ------------------------------------------------------------
echo  1. Create/update venv and install requirements
echo  2. Run configuration editor
echo  3. Run IREPS scraper
echo  4. Run analysis dashboard
echo  5. Run CAPTCHA solver utility
echo  6. Open command prompt with venv activated
echo  7. Exit
echo ------------------------------------------------------------
set "MENU_CHOICE="
set /p "MENU_CHOICE=Select an option [1-7]: "

if "%MENU_CHOICE%"=="1" goto SETUP_VENV
if "%MENU_CHOICE%"=="2" goto CONFIG_EDITOR
if "%MENU_CHOICE%"=="3" goto SCRAPER
if "%MENU_CHOICE%"=="4" goto DASHBOARD
if "%MENU_CHOICE%"=="5" goto CAPTCHA_SOLVER
if "%MENU_CHOICE%"=="6" goto OPEN_SHELL
if "%MENU_CHOICE%"=="7" goto EXIT_MENU

echo.
echo Invalid option. Please choose a number from 1 to 7.
pause
goto MENU

:SETUP_VENV
call :CREATE_OR_UPDATE_VENV
pause
goto MENU

:CONFIG_EDITOR
call :ENSURE_VENV || goto MENU
call :RUN_PYTHON_IN_DIR "Scraping" "IREPS_scraping_gui.py"
goto MENU

:SCRAPER
call :ENSURE_VENV || goto MENU
call :RUN_PYTHON_IN_DIR "Scraping" "IREPS_Tenders.py"
goto MENU

:DASHBOARD
call :ENSURE_VENV || goto MENU
call :RUN_PYTHON_IN_DIR "Analysis" "script.py"
goto MENU

:CAPTCHA_SOLVER
call :ENSURE_VENV || goto MENU
call :RUN_PYTHON_IN_DIR "Scraping\Program_Files" "captcha_solver.py"
goto MENU

:OPEN_SHELL
call :ENSURE_VENV || goto MENU
echo.
echo Opening a new command prompt with venv activated...
start "IREPS venv" cmd /k "call ""%VENV_DIR%\Scripts\activate.bat"" && cd /d ""%ROOT_DIR%"""
goto MENU

:CREATE_OR_UPDATE_VENV
echo.
echo ============================================================
echo Creating/updating virtual environment
echo ============================================================
if not exist "%PYTHON_EXE%" (
    echo Creating venv at "%VENV_DIR%"...
    py -m venv "%VENV_DIR%" 2>nul
    if errorlevel 1 (
        echo Python launcher failed or is unavailable. Trying python...
        python -m venv "%VENV_DIR%"
    )
    if errorlevel 1 (
        echo Failed to create virtual environment.
        exit /b 1
    )
) else (
    echo Reusing existing venv at "%VENV_DIR%".
)

if not exist "%REQUIREMENTS_FILE%" (
    echo Missing requirements file: "%REQUIREMENTS_FILE%"
    exit /b 1
)

echo Upgrading pip...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    exit /b 1
)

echo Installing project requirements...
"%PIP_EXE%" install -r "%REQUIREMENTS_FILE%"
if errorlevel 1 (
    echo Failed to install requirements.
    exit /b 1
)

echo.
echo Virtual environment is ready.
exit /b 0

:ENSURE_VENV
if exist "%PYTHON_EXE%" exit /b 0
echo.
echo Virtual environment was not found at "%VENV_DIR%".
choice /C YN /M "Create venv and install requirements now"
if errorlevel 2 exit /b 1
call :CREATE_OR_UPDATE_VENV
exit /b %ERRORLEVEL%

:RUN_PYTHON_IN_DIR
set "APP_DIR=%~1"
set "SCRIPT_NAME=%~2"
set "TARGET_DIR=%ROOT_DIR%%APP_DIR%"
set "TARGET_SCRIPT=%TARGET_DIR%\%SCRIPT_NAME%"

echo.
echo ============================================================
echo Running %APP_DIR%\%SCRIPT_NAME%
echo ============================================================
if not exist "%TARGET_SCRIPT%" (
    echo Missing script: "%TARGET_SCRIPT%"
    pause
    exit /b 1
)

pushd "%TARGET_DIR%"
"%PYTHON_EXE%" "%SCRIPT_NAME%"
set "RUN_EXIT_CODE=%ERRORLEVEL%"
popd

echo.
echo Process finished with exit code %RUN_EXIT_CODE%.
pause
exit /b %RUN_EXIT_CODE%

:EXIT_MENU
echo.
echo Goodbye.
exit /b 0
