import httpx
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from dataclasses import dataclass

from core.exceptions import CrawlFailedError, RobotsBlockedError, ScrapeFetchError
from crawl.config import get_crawl_settings
from crawl.normalizer import normalize
from crawl.page_actions import expand_collapsed
from crawl.parser import parse_duckduckgo_html, parse_html
from crawl.robots import RobotsChecker
from crawl.validator import validate


@dataclass(frozen=True)
class ScrapeResult:
    url: str
    title: str | None
    content: str


class HybridClient:
    def __init__(self) -> None:
        self._robots = RobotsChecker()

    async def scrape(self, url: str) -> ScrapeResult:
        url = normalize(url)
        if not await self._robots.is_allowed(url):
            raise RobotsBlockedError(f"robots.txt에 의해 차단된 URL: {url}")
        settings = get_crawl_settings()
        try:
            title, static_content = await self._scrape_static(url)
            print(
                f"  [정적] {len(static_content)}자 (임계값: {settings.static_fallback_threshold}자)"
            )
            if len(static_content) < settings.static_fallback_threshold:
                print("  [동적] 임계값 미달 → 동적 크롤링 시작")
                dyn_title, dyn_content = await self._scrape_dynamic(url)
                print(f"  [동적] 완료: {len(dyn_content)}자")
                if len(dyn_content) > len(static_content):
                    title, content = dyn_title, dyn_content
                else:
                    content = static_content
            else:
                content = static_content
        except ScrapeFetchError:
            raise
        except Exception as e:
            raise ScrapeFetchError(str(e)) from e

        validate(content)
        return ScrapeResult(url=url, title=title or None, content=content)

    async def _scrape_static(self, url: str) -> tuple[str | None, str]:
        settings = get_crawl_settings()
        headers = {
            "User-Agent": settings.user_agent,
            "Accept-Language": settings.accept_language,
        }
        async with httpx.AsyncClient(
            headers=headers, timeout=30.0, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
        html = response.text
        if "duckduckgo.com" in url:
            return "DuckDuckGo 검색 결과", parse_duckduckgo_html(html)
        return parse_html(html)

    async def _scrape_dynamic(self, url: str) -> tuple[str | None, str]:
        settings = get_crawl_settings()
        stealth = Stealth(navigator_languages_override=("ko-KR", "ko"))
        async with stealth.use_async(async_playwright()) as p:
            browser = await p.chromium.launch(headless=settings.playwright_headless)
            try:
                context = await browser.new_context(
                    locale="ko-KR",
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()
                await page.goto(
                    url, wait_until="networkidle", timeout=settings.playwright_timeout
                )
                await page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight / 2)"
                )
                await page.wait_for_load_state("networkidle")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_load_state("networkidle")
                html = await page.content()
                title = await page.title()
                accordion_text = await expand_collapsed(page)
            finally:
                await browser.close()

        _, content = parse_html(html)
        if accordion_text:
            content = content + "\n\n" + accordion_text
        return title or None, content


hybrid_client = HybridClient()
