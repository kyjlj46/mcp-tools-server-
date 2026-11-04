# mcp-tools-server

LLM이 **tool calling**으로 직접 쓰는 기본 도구 모음 [MCP](https://modelcontextprotocol.io) 서버입니다.
API 키 없이 동작하며, Claude Code·Claude Desktop 등 MCP를 지원하는 어떤 클라이언트에도 붙일 수 있습니다.

## 제공 도구

| 도구 | 설명 | 주요 인자 |
|------|------|-----------|
| `web_search` | 웹 검색 (DuckDuckGo) → 제목·URL·요약 | `query`, `max_results`(5), `region`(kr-kr), `timelimit`(d/w/m/y) |
| `news_search` | 최신 뉴스 검색 → 제목·언론사·날짜·URL | `query`, `max_results`, `region`, `timelimit`(기본 m) |
| `fetch_url` | 웹 페이지 본문 텍스트 추출 (메뉴·스크립트 제거) | `url`, `max_chars`(8000), `start`(이어 읽기) |
| `wikipedia` | 위키백과 문서 요약 + URL | `query`, `lang`(ko) |
| `current_time` | 현재 날짜·시각·요일 | `timezone`(Asia/Seoul) |
| `calculate` | 안전한 수식 계산 (`^`, `sqrt`, `log`, `pi` 등) | `expression` |

안전장치:
- `fetch_url`은 http(s)만 열 수 있습니다. localhost·사설망·클라우드 메타데이터 같은 내부 주소는 리다이렉트까지 검사해서 막습니다(SSRF 방지). 한 번에 최대 3MB까지 받습니다.
- `calculate`는 `eval`을 쓰지 않고 수식의 AST를 직접 계산하므로, 수식 대신 임의 코드를 넣어도 실행되지 않습니다.
- 모든 도구는 읽기 전용입니다(`readOnlyHint`).

## 설치

[uv](https://docs.astral.sh/uv/)가 필요합니다.

```bash
git clone https://github.com/kyjlj46/mcp-tools-server-.git mcp-tools-server   # 폴더 이름은 mcp-tools-server 로
cd mcp-tools-server
uv sync
```

## 기동 방법

| 방식 | 기동 | 언제 쓰나 |
|---|---|---|
| **stdio** (기본) | 직접 켜지 않습니다. 클라이언트(Claude Code 등)가 필요할 때 하위 프로세스로 띄우고, 끝나면 함께 종료합니다. | Claude Code 등록, image-analyzer "자동 실행" |
| **HTTP** | `start_http.bat` 더블클릭 (포트를 바꾸려면 `start_http.bat 9000`), 또는 VS Code F5 → "MCP 서버 실행 (HTTP)", 또는 `uv run mcp-tools-server --transport streamable-http --port 8765` | 서버를 계속 켜 두고 여러 클라이언트가 같이 쓸 때. 주소: `http://127.0.0.1:8765/mcp` |

image-analyzer에 연결하려면 그 화면 왼쪽 **웹 도구 (MCP 서버) → 설정**에서 방식을 고릅니다.
- 자동 실행: 폴더 경로만 맞으면 됩니다.
- HTTP: 위 방법으로 서버를 켠 뒤 주소를 입력하고 "저장 · 연결 테스트"를 누릅니다.

## 사용

### Claude Code에 등록

```bash
# 모든 프로젝트에서 쓰기 (Windows 예시: 경로는 실제 위치로)
claude mcp add tools --scope user -- C:\Users\<사용자>\mcp-tools-server\.venv\Scripts\python.exe -m mcp_tools_server

# 또는 uv로 실행
claude mcp add tools --scope user -- uv run --directory C:\Users\<사용자>\mcp-tools-server mcp-tools-server
```

등록한 뒤 Claude Code에서 `/mcp`를 입력하면 `tools` 서버와 도구 6개가 보입니다.

### 한 번만 쓰기 (`claude -p`)

```bash
claude -p "N서울타워 운영시간을 웹에서 확인해줘" \
  --mcp-config '{"mcpServers":{"tools":{"command":"<python 경로>","args":["-m","mcp_tools_server"]}}}' \
  --strict-mcp-config --allowedTools "mcp__tools__web_search,mcp__tools__fetch_url"
```

Claude Code 안에서 도구 이름은 `mcp__tools__<도구명>` 형식입니다.

### Claude Desktop 등 다른 클라이언트

`claude_desktop_config.json`에 다음을 추가합니다.

```json
{
  "mcpServers": {
    "tools": {
      "command": "C:\\Users\\<사용자>\\mcp-tools-server\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_tools_server"]
    }
  }
}
```

### HTTP 서버로 실행

```bash
uv run mcp-tools-server --transport streamable-http --port 8765   # → http://127.0.0.1:8765/mcp
```

VS Code에서 F5를 누르면 MCP 서버가 HTTP 모드로 실행됩니다(포트 8765). 테스트는 왼쪽 테스트 패널(플라스크 아이콘)이나 `uv run pytest`로 실행합니다.

## 이 서버를 쓰는 프로젝트

- [image-analyzer](https://github.com/kyjlj46/image-analyzer)
  - 웹 검증·웹서칭·추가 질문 단계에서 이 서버의 도구를 씁니다.
  - 두 프로젝트를 같은 폴더 아래에 나란히 두면 자동으로 연결됩니다.

## 도구 추가하기

[src/mcp_tools_server/server.py](src/mcp_tools_server/server.py)에 함수를 하나 만들고 `@server.tool()`을 붙이면 됩니다.

```python
@server.tool(structured_output=False)
def exchange_rate(base: Annotated[str, Field(description="기준 통화, 예: USD")] = "USD") -> str:
    """환율을 조회합니다."""
    ...
```

- docstring은 LLM이 보는 도구 설명이 되고, 타입 힌트와 `Field` 설명은 입력 스키마가 됩니다.
- 메시지를 LLM에게 그대로 보여 줘야 하는 오류는 `ToolInputError`로 던지세요. 다른 예외는 "Error executing tool"로만 전달됩니다.

## 테스트

```bash
uv run pytest                    # 전체 (인터넷 필요)
uv run pytest -m "not network"   # 오프라인 테스트만
```

## 파일 구성

| 파일 | 역할 |
|------|------|
| `src/mcp_tools_server/server.py` | MCP 서버, 도구 등록(설명·입력 스키마) |
| `src/mcp_tools_server/web.py` | 검색·페이지 읽기·위키백과 구현 |
| `src/mcp_tools_server/basic.py` | 현재 시각·계산기 구현 |
| `src/mcp_tools_server/__init__.py` | 실행 진입점 (`--transport`, `--port`) |
| `start_http.bat` | HTTP 모드로 서버 실행 (Windows, 기본 포트 8765) |
| `tests/test_tools.py` | 도구 단위 테스트 + stdio 하위 프로세스 연결 테스트 |
