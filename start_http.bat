@echo off
rem Start mcp-tools-server in HTTP mode: http://127.0.0.1:8765/mcp
rem Usage: start_http.bat [port]
cd /d "%~dp0"
set PORT=%1
if "%PORT%"=="" set PORT=8765
if not exist ".venv\Scripts\python.exe" (
  where uv >/dev/null 2>/dev/null && (uv sync) || ("%USERPROFILE%\.local\bin\uv.exe" sync)
)
echo MCP server: http://127.0.0.1:%PORT%/mcp   (Ctrl+C to stop)
".venv\Scripts\python.exe" -m mcp_tools_server --transport streamable-http --port %PORT%
pause
