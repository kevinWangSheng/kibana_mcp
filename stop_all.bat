@echo off
REM Stop all MCP DevOps Tools servers

echo Stopping MCP servers...

REM Kill processes on ports 8000, 8001, 8002
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTENING"') do (
    echo Killing Kibana MCP ^(PID: %%a^)
    taskkill /F /PID %%a 2>nul
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001.*LISTENING"') do (
    echo Killing Archery MCP ^(PID: %%a^)
    taskkill /F /PID %%a 2>nul
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8002.*LISTENING"') do (
    echo Killing Doris MCP ^(PID: %%a^)
    taskkill /F /PID %%a 2>nul
)

echo.
echo All servers stopped.
