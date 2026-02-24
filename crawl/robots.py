from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from crawl.config import get_crawl_settings


class RobotsChecker:
    def __init__(self) -> None:
        self._cache: dict[str, RobotFileParser] = {}

    async def is_allowed(self, url: str) -> bool:
        parser = await self._get_parser(url)
        settings = get_crawl_settings()
        return parser.can_fetch(settings.user_agent, url)

    def get_crawl_delay(self, url: str) -> float | None:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._cache.get(origin)
        if parser is None:
            return None
        delay = parser.crawl_delay(get_crawl_settings().user_agent)
        return float(delay) if delay is not None else None

    async def _get_parser(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin in self._cache:
            return self._cache[origin]

        parser = RobotFileParser()
        robots_url = f"{origin}/robots.txt"

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                else:
                    parser.allow_all = True
        except httpx.HTTPError:
            parser.allow_all = True

        self._cache[origin] = parser
        return parser
