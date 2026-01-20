@echo off
REM Start all MCP DevOps Tools servers
REM Kibana: 8000, Archery: 8001, Doris: 8002

echo Starting MCP DevOps Tools...
echo.

cd /d %~dp0

REM Start Kibana MCP (port 8000)
start "Kibana MCP" cmd /k "python -m servers.kibana.server --port=8000"

REM Start Archery MCP (port 8001)
start "Archery MCP" cmd /k "python -m servers.archery.server --port=8001"

REM Start Doris MCP (port 8002)
start "Doris MCP" cmd /k "python -m servers.doris.server --port=8002"

echo.
echo All servers started:
echo   - Kibana:  http://localhost:8000/mcp  (logs within 3 days)
echo   - Archery: http://localhost:8001/mcp  (SQL database queries)
echo   - Doris:   http://localhost:8002/mcp  (historical logs 3+ days)
echo.
echo Press any key to exit this window...
pause >nul
