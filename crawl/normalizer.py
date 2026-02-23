from urllib.parse import parse_qs, urlencode, urlparse


def normalize(url: str) -> str:
    return _to_duckduckgo(url)


def _to_duckduckgo(url: str) -> str:
    parsed = urlparse(url)
    if "google" not in parsed.netloc:
        return url
    query = parse_qs(parsed.query).get("q", [""])[0]
    if not query:
        return url
    return f"https://html.duckduckgo.com/html/?{urlencode({'q': query})}"
