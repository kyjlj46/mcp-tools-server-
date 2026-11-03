"""MCP 서버 - LLM이 tool calling으로 쓰는 기본 도구 모음.

새 도구를 추가하려면 아래처럼 함수를 하나 만들고 @server.tool() 을 붙이면 된다.
docstring과 타입 힌트가 그대로 LLM에게 보이는 도구 설명·입력 스키마가 된다.
"""

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from . import basic, web

server = MCPServer(
    name="tools",
    title="기본 도구 MCP 서버",
    version="0.1.0",
    instructions=(
        "웹 검색, 뉴스 검색, 웹 페이지 읽기, 위키백과 요약, 현재 시각, 계산기 도구를 제공합니다. "
        "사실 확인이 필요하면 web_search로 찾은 뒤 fetch_url로 원문을 읽고, 답변에 출처 URL을 붙이세요."
    ),
)

READ_ONLY_WEB = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
READ_ONLY_LOCAL = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

Region = Annotated[str, Field(description="검색 지역·언어. 한국어 결과는 kr-kr, 영어는 us-en, 전 세계는 wt-wt")]
TimeLimit = Annotated[Literal["d", "w", "m", "y"] | None,
                      Field(description="기간 제한: d=하루, w=일주일, m=한 달, y=1년, null=제한 없음")]


@server.tool(annotations=READ_ONLY_WEB, structured_output=False)
def web_search(
    query: Annotated[str, Field(description="검색어")],
    max_results: Annotated[int, Field(ge=1, le=20, description="결과 개수")] = 5,
    region: Region = "kr-kr",
    timelimit: TimeLimit = None,
) -> str:
    """웹을 검색해 제목, URL, 요약 목록을 돌려줍니다. 자세한 내용은 fetch_url로 해당 URL을 읽으세요."""
    return web.web_search(query, max_results, region, timelimit)


@server.tool(annotations=READ_ONLY_WEB, structured_output=False)
def news_search(
    query: Annotated[str, Field(description="검색어")],
    max_results: Annotated[int, Field(ge=1, le=20, description="결과 개수")] = 5,
    region: Region = "kr-kr",
    timelimit: TimeLimit = "m",
) -> str:
    """최신 뉴스 기사를 검색해 제목, 언론사, 날짜, URL, 요약을 돌려줍니다. 기본은 최근 한 달."""
    return web.news_search(query, max_results, region, timelimit)


@server.tool(annotations=READ_ONLY_WEB, structured_output=False)
def fetch_url(
    url: Annotated[str, Field(description="읽을 웹 페이지 주소 (http/https)")],
    max_chars: Annotated[int, Field(ge=500, le=40000, description="돌려받을 최대 글자 수")] = 8000,
    start: Annotated[int, Field(ge=0, description="긴 페이지를 이어 읽을 때 시작 위치(글자)")] = 0,
) -> str:
    """웹 페이지를 열어 광고·메뉴를 뺀 본문 텍스트를 돌려줍니다. 내부망/로컬 주소는 열 수 없습니다."""
    return web.fetch_url(url, max_chars, start)


@server.tool(annotations=READ_ONLY_WEB, structured_output=False)
def wikipedia(
    query: Annotated[str, Field(description="찾을 항목 (인물, 장소, 개념 등)")],
    lang: Annotated[str, Field(description="위키백과 언어 코드: ko, en, ja 등")] = "ko",
) -> str:
    """위키백과에서 가장 관련 있는 문서를 찾아 요약과 URL을 돌려줍니다."""
    return web.wikipedia(query, lang)


@server.tool(annotations=READ_ONLY_LOCAL, structured_output=False)
def current_time(
    timezone: Annotated[str, Field(description="IANA 시간대 이름. 예: Asia/Seoul, UTC, America/New_York")] = "Asia/Seoul",
) -> str:
    """지정한 시간대의 현재 날짜·시각·요일을 돌려줍니다. '오늘', '최근' 같은 표현을 해석할 때 쓰세요."""
    return basic.current_time(timezone)


@server.tool(annotations=READ_ONLY_LOCAL, structured_output=False)
def calculate(
    expression: Annotated[str, Field(description="수식. 예: (1200*1.1)^2, sqrt(2)*pi, 15% 대신 0.15")],
) -> str:
    """사칙연산, 거듭제곱(^ 또는 **), 나머지(%), sqrt·log·sin 등 math 함수, pi·e 상수로 수식을 정확히 계산합니다."""
    return basic.calculate(expression)
