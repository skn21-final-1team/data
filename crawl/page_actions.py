from playwright.async_api import Page

_ACCORDION_SELECTORS = [
    "button[class*='HoverButton-module__button']",
    "[aria-expanded='false']",
    "details:not([open]) > summary",
]


async def expand_collapsed(page: Page) -> str:
    for selector in _ACCORDION_SELECTORS:
        buttons = await page.query_selector_all(selector)
        if not buttons:
            continue

        baseline_lines: set[str] = set((await page.inner_text("body")).splitlines())
        extras: list[str] = []
        seen_new: set[str] = set()

        for button in buttons:
            try:
                await button.click(timeout=3000)
                await page.wait_for_load_state("networkidle")
                current_lines = (await page.inner_text("body")).splitlines()
                new_lines = [
                    line
                    for line in current_lines
                    if line.strip()
                    and line not in baseline_lines
                    and line not in seen_new
                ]
                seen_new.update(new_lines)
                if new_lines:
                    extras.append("\n".join(new_lines))
            except Exception:
                pass

        return "\n\n".join(extras)

    return ""
