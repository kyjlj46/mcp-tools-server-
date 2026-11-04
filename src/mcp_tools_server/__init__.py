"""기본 도구 MCP 서버. `mcp-tools-server` 또는 `python -m mcp_tools_server` 로 실행한다."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="기본 도구 MCP 서버 (웹 검색, 페이지 읽기, 위키백과, 시각, 계산기)")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio",
                        help="stdio: Claude Code 등이 하위 프로세스로 실행 (기본) / streamable-http: HTTP 서버로 실행")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP 모드 주소 (기본 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="HTTP 모드 포트 (기본 8765)")
    args = parser.parse_args()

    from .server import server
    if args.transport == "stdio":
        server.run("stdio")
    else:
        print(f"MCP 서버: http://{args.host}:{args.port}/mcp  (끄려면 Ctrl+C / VS Code에서는 Shift+F5)", flush=True)
        server.run("streamable-http", host=args.host, port=args.port)
