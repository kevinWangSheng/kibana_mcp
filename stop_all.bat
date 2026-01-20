@echo off
REM Stop all MCP DevOps Tools servers

echo Stopping MCP DevOps Tools...

REM Kill Python processes on ports 8000, 8001, 8002
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTENING"') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001.*LISTENING"') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8002.*LISTENING"') do taskkill /F /PID %%a 2>nul

echo All servers stopped.
pause
