"""도구 테스트. 실행: uv run pytest  (웹 테스트 제외: uv run pytest -m "not network")"""

import sys

import anyio
import pytest
from mcp import Client, StdioServerParameters

from mcp_tools_server import basic, web
from mcp_tools_server.server import server

EXPECTED = {"web_search", "news_search", "fetch_url", "wikipedia", "current_time", "calculate"}


def call(name: str, args: dict) -> tuple[bool, str]:
    async def run():
        async with Client(server) as c:
            r = await c.call_tool(name, args)
            return r.is_error, "".join(getattr(x, "text", "") for x in r.content)
    return anyio.run(run)


def test_tools_listed():
    async def run():
        async with Client(server) as c:
            return {t.name for t in (await c.list_tools()).tools}
    assert anyio.run(run) == EXPECTED


def test_stdio_subprocess():
    """실제로 Claude Code가 하듯 하위 프로세스(stdio)로 띄워 호출한다."""
    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_tools_server"])
        async with Client(params) as c:
            names = {t.name for t in (await c.list_tools()).tools}
            r = await c.call_tool("calculate", {"expression": "2^10"})
            return names, r.content[0].text
    names, text = anyio.run(run)
    assert names == EXPECTED and text.endswith("= 1024")


@pytest.mark.parametrize("expr, expected", [
    ("1+2*3", "7"), ("(1200*1.1)^2", "1742400"), ("sqrt(16)+max(1,2)", "6"), ("1,234+1", "1235"), ("10/4", "2.5"),
])
def test_calculate(expr, expected):
    assert basic.calculate(expr).endswith(f"= {expected}")


@pytest.mark.parametrize("expr", ["__import__('os')", "open('x')", "2**100000", "1/0", "a+1"])
def test_calculate_rejects(expr):
    with pytest.raises(web.ToolInputError):
        basic.calculate(expr)


def test_error_is_tool_error():
    is_error, text = call("calculate", {"expression": "__import__('os')"})
    assert is_error and "지원하지 않는" in text


def test_current_time():
    assert "Asia/Seoul UTC+0900" in basic.current_time()
    with pytest.raises(web.ToolInputError):
        basic.current_time("Mars/Base")


@pytest.mark.parametrize("url", ["http://127.0.0.1:8000/", "http://localhost/", "http://192.168.0.1/",
                                 "http://169.254.169.254/latest/", "file:///C:/Windows/win.ini", "ftp://example.com"])
def test_fetch_blocks_internal(url):
    with pytest.raises(web.ToolInputError):
        web.fetch_url(url)


@pytest.mark.network
def test_web_search():
    out = web.web_search("Python programming language", max_results=3, region="us-en")
    assert "URL: http" in out


@pytest.mark.network
def test_news_search():
    assert "URL: http" in web.news_search("인공지능", max_results=3)


@pytest.mark.network
def test_fetch_url():
    out = web.fetch_url("https://example.com")
    assert "Example Domain" in out


@pytest.mark.network
def test_wikipedia():
    out = web.wikipedia("서울특별시")
    assert "ko.wikipedia.org" in out and "서울" in out
