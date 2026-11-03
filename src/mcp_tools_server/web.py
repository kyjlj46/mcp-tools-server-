"""웹 도구 구현 - API 키 없이 동작한다.

- 검색: DuckDuckGo (ddgs 패키지)
- 페이지 읽기: httpx + BeautifulSoup 로 본문 텍스트 추출 (내부망 주소 차단)
- 위키백과: 공개 REST API
"""

import ipaddress
import re
import socket
from urllib.parse import quote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from ddgs.exceptions import DDGSException
from mcp.server.mcpserver.exceptions import ToolError

# 위키미디어는 프로그램 이름과 연락처가 들어간 User-Agent를 요구한다
USER_AGENT = "mcp-tools-server/0.1 (https://github.com/kyjlj46/mcp-tools-server-) httpx"
# 일반 웹 페이지는 브라우저가 아닌 User-Agent를 막는 곳이 많다
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
TIMEOUT = httpx.Timeout(15.0)
MAX_DOWNLOAD = 3 * 1024 * 1024  # 페이지 하나당 최대 3MB만 받는다
MAX_REDIRECTS = 5


class ToolInputError(ToolError):
    """도구 사용자(LLM)에게 메시지가 그대로 전달되는 오류. (다른 예외는 'Error executing tool'로 가려진다)"""


# ── 검색 ───────────────────────────────────────────────────────────────

def _format_results(results: list[dict], url_key: str, extra: tuple[str, ...] = ()) -> str:
    if not results:
        return "검색 결과가 없습니다. 검색어를 바꿔 보세요."
    lines = []
    for n, r in enumerate(results, start=1):
        meta = " · ".join(str(r[k]) for k in extra if r.get(k))
        lines.append(f"{n}. {r.get('title', '').strip()}\n   URL: {r.get(url_key, '')}"
                     + (f"\n   {meta}" if meta else "")
                     + f"\n   {(r.get('body') or '').strip()}")
    return "\n\n".join(lines)


def _search(kind: str, query: str, max_results: int, region: str, timelimit: str | None) -> tuple[list[dict], str]:
    """ddgs 검색. 기간 제한으로 결과가 없으면 제한 없이 한 번 더 찾는다. (결과, 안내 문구) 반환."""
    query = query.strip()
    if not query:
        raise ToolInputError("검색어가 비어 있습니다.")
    max_results = max(1, min(max_results, 20))
    search = getattr(DDGS(), kind)
    try:
        return search(query, region=region, safesearch="moderate", timelimit=timelimit, max_results=max_results), ""
    except DDGSException as e:
        if not timelimit:
            raise ToolInputError(f"검색 실패: {e}") from None
    try:
        results = search(query, region=region, safesearch="moderate", timelimit=None, max_results=max_results)
        return results, f"(기간 제한 '{timelimit}' 안에 결과가 없어 전체 기간에서 찾았습니다)\n\n"
    except DDGSException as e:
        raise ToolInputError(f"검색 실패: {e}") from None


def web_search(query: str, max_results: int = 5, region: str = "kr-kr", timelimit: str | None = None) -> str:
    results, note = _search("text", query, max_results, region, timelimit)
    return note + _format_results(results, "href")


def news_search(query: str, max_results: int = 5, region: str = "kr-kr", timelimit: str | None = "m") -> str:
    results, note = _search("news", query, max_results, region, timelimit)
    return note + _format_results(results, "url", extra=("source", "date"))


# ── 페이지 읽기 ─────────────────────────────────────────────────────────

def _check_public_url(url: str) -> None:
    """http(s)만 허용하고, 내부망·로컬 주소로 가는 요청(SSRF)은 막는다."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ToolInputError(f"http(s) 주소만 열 수 있습니다: {url}")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        raise ToolInputError(f"주소를 찾을 수 없습니다: {parsed.hostname}") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ToolInputError(f"내부망/로컬 주소는 열 수 없습니다: {parsed.hostname}")


def _download(url: str) -> tuple[str, str, bytes]:
    """리다이렉트를 한 단계씩 따라가며 매번 주소를 검사한다. (최종 URL, content-type, 본문) 반환."""
    with httpx.Client(headers={"User-Agent": BROWSER_UA, "Accept-Language": "ko,en;q=0.8"},
                      timeout=TIMEOUT, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _check_public_url(url)
            with client.stream("GET", url) as resp:
                if resp.is_redirect and resp.headers.get("location"):
                    url = urljoin(url, resp.headers["location"])
                    continue
                if resp.status_code >= 400:
                    raise ToolInputError(f"페이지를 열 수 없습니다 (HTTP {resp.status_code}): {url}")
                body = bytearray()
                for chunk in resp.iter_bytes():
                    body += chunk
                    if len(body) > MAX_DOWNLOAD:
                        break
                return url, resp.headers.get("content-type", ""), bytes(body)
    raise ToolInputError("리다이렉트가 너무 많습니다.")


def _html_to_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form", "iframe"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text


def fetch_url(url: str, max_chars: int = 8000, start: int = 0) -> str:
    final_url, ctype, body = _download(url.strip())
    charset = re.search(r"charset=([\w-]+)", ctype)
    raw = body.decode(charset.group(1) if charset else "utf-8", errors="replace")
    if "html" in ctype or raw.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        title, text = _html_to_text(raw)
    elif ctype.startswith(("text/", "application/json", "application/xml")):
        title, text = "", raw
    else:
        raise ToolInputError(f"텍스트가 아닌 콘텐츠입니다 ({ctype or '알 수 없음'}): {final_url}")

    max_chars = max(500, min(max_chars, 40000))
    start = max(0, start)
    part = text[start:start + max_chars]
    head = f"URL: {final_url}\n" + (f"제목: {title}\n" if title else "")
    if start + max_chars < len(text):
        head += f"(전체 {len(text)}자 중 {start}~{start + len(part)}자. 이어서 보려면 start={start + max_chars})\n"
    return head + "\n" + part


# ── 위키백과 ───────────────────────────────────────────────────────────

def wikipedia(query: str, lang: str = "ko", sentences_only: bool = False) -> str:
    query = query.strip()
    if not query:
        raise ToolInputError("검색어가 비어 있습니다.")
    if not re.fullmatch(r"[a-z]{2,3}(-[a-z]+)?", lang):
        raise ToolInputError(f"언어 코드가 올바르지 않습니다: {lang}")
    base = f"https://{lang}.wikipedia.org"
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as client:
        found = client.get(f"{base}/w/api.php", params={
            "action": "query", "list": "search", "srsearch": query, "srlimit": 3, "format": "json"}).json()
        hits = found.get("query", {}).get("search", [])
        if not hits:
            return f"{lang}.wikipedia.org 에서 '{query}' 문서를 찾지 못했습니다."
        title = hits[0]["title"]
        summary = client.get(f"{base}/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}").json()
    text = summary.get("extract") or ""
    others = ", ".join(h["title"] for h in hits[1:])
    page = summary.get("content_urls", {}).get("desktop", {}).get("page", f"{base}/wiki/{quote(title)}")
    out = f"제목: {summary.get('title', title)}\n"
    if summary.get("description"):
        out += f"설명: {summary['description']}\n"
    out += f"URL: {page}\n\n{text}"
    if others and not sentences_only:
        out += f"\n\n다른 후보 문서: {others}"
    return out
