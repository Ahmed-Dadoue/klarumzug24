@echo off
setlocal

echo Starting Klarumzug24 local environment...
echo.

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "DOCS_DIR=%ROOT_DIR%\docs"
set "VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"

if not exist "%BACKEND_DIR%" (
  echo [ERROR] backend folder not found: "%BACKEND_DIR%"
  pause
  exit /b 1
)

if not exist "%DOCS_DIR%" (
  echo [ERROR] docs folder not found: "%DOCS_DIR%"
  pause
  exit /b 1
)

if not exist "%VENV_PYTHON%" (
  echo [ERROR] Missing backend virtualenv: "%VENV_PYTHON%"
  echo Create it with:
  echo   cd backend
  echo   python -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

echo Checking uvicorn...
%VENV_PYTHON% -m pip show uvicorn >nul 2>&1
if errorlevel 1 (
  echo [INFO] Installing uvicorn...
  %VENV_PYTHON% -m pip install uvicorn
)

start "Klarumzug24 Backend" /D "%BACKEND_DIR%" cmd /k ""%VENV_PYTHON%" -m uvicorn main:app --reload --port 8000"
start "Klarumzug24 Frontend" /D "%DOCS_DIR%" cmd /k ""%VENV_PYTHON%" -m http.server 8080"

echo ----------------------------------
echo Frontend: http://localhost:8080
echo Backend : http://localhost:8000
echo ----------------------------------
echo.
echo Press any key to close this launcher window...
pause >nul

endlocal
