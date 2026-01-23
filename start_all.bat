@echo off
REM Start all MCP DevOps Tools servers
REM Kibana: 8000, Archery: 8001, Doris: 8002

echo Starting MCP DevOps Tools...
echo.

cd /d %~dp0

REM Use virtual environment Python
set PYTHON=%~dp0.venv\Scripts\python.exe

REM Check if venv exists
if not exist "%PYTHON%" (
    echo ERROR: Virtual environment not found at .venv\Scripts\python.exe
    echo Please create it first: python -m venv .venv
    pause
    exit /b 1
)

REM Start Kibana MCP (port 8000)
start "Kibana MCP - 8000" cmd /k "cd /d %~dp0 && "%PYTHON%" -m servers.kibana.server --port=8000"

REM Start Archery MCP (port 8001)
start "Archery MCP - 8001" cmd /k "cd /d %~dp0 && "%PYTHON%" -m servers.archery.server --port=8001"

REM Start Doris MCP (port 8002)
start "Doris MCP - 8002" cmd /k "cd /d %~dp0 && "%PYTHON%" -m servers.doris.server --port=8002"

echo.
echo All servers started:
echo   - Kibana:  http://localhost:8000/mcp  (3 days logs)
echo   - Archery: http://localhost:8001/mcp  (SQL queries)
echo   - Doris:   http://localhost:8002/mcp  (3+ days logs)
echo.
pause
