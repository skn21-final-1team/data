from bs4 import BeautifulSoup
from trafilatura import extract, extract_metadata


def _strip_nested_tables(html: str) -> str:
    """table 안에 table이 중첩된 레이아웃 테이블을 제거한다.
    평탄한 데이터 테이블은 유지."""
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        if table.find("table"):
            table.decompose()
    return str(soup)


def parse_html(html: str) -> tuple[str | None, str]:
    meta = extract_metadata(html)
    title = meta.title if meta else None
    cleaned = _strip_nested_tables(html)
    content = extract(cleaned, include_comments=False, include_tables=True, output_format="markdown") or ""
    return title, content


def parse_duckduckgo_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for result in soup.select(".result"):
        title_el = result.select_one(".result__title a")
        snippet_el = result.select_one(".result__snippet")
        url_el = result.select_one(".result__url")
        if not title_el or not snippet_el:
            continue
        title = title_el.get_text(strip=True)
        snippet = snippet_el.get_text(strip=True)
        url = url_el.get_text(strip=True) if url_el else ""
        results.append(f"## {title}\n{url}\n{snippet}")
    return "\n\n".join(results)
