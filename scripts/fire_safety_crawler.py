"""Playwright ????????????????????????????

???????
1. ?????? Playwright API??? rows.count()/inner_text() ? await ? bug??
2. ???????????????? enqueue_links ?? <a> ?????????
3. ????????????????????? next_btn.count() ? await ???????????
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from dataclasses import dataclass
from typing import Optional

from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from playwright.async_api import Page
from tqdm.asyncio import tqdm


LOGIN_URL = "http://117.73.254.171:10010/#/login"
TASK_URL = (
    "http://117.73.254.171:10010/#/jdjcrw?runId=1984595857552314368&name=??????"
)
START_DATE = "2021-01-01"
END_DATE = "2025-11-01"
AGENCY_NAME = "?????????????"


@dataclass(slots=True)
class RowData:
    company: str
    date: str
    number: str
    detail_number: Optional[str] = None


async def fill_date_range(page: Page) -> None:
    date_inputs = page.locator('input.el-range-input')
    if await date_inputs.count() >= 2:
        await date_inputs.nth(0).fill(START_DATE)
        await date_inputs.nth(1).fill(END_DATE)
    else:
        await page.fill('input[placeholder="????"]', START_DATE)
        await page.fill('input[placeholder="????"]', END_DATE)


async def choose_agency(page: Page) -> None:
    await page.click('input[placeholder="???????"]')
    option = page.locator(f'//li[contains(., "{AGENCY_NAME}")]')
    await option.wait_for()
    await option.click()


async def scrape_list_page(context: PlaywrightCrawlingContext, pbar: tqdm) -> None:
    page = context.page
    await page.wait_for_selector('table.el-table__body tbody tr', timeout=30_000)

    rows = page.locator('table.el-table__body tbody tr')
    row_count = await rows.count()

    for row_index in range(row_count):
        row = rows.nth(row_index)
        number = (await row.locator('td:nth-child(4)').inner_text()).strip()
        if not number:
            continue

        company = (await row.locator('td:nth-child(2)').inner_text()).strip()
        date = (await row.locator('td:nth-child(8)').inner_text()).strip()

        detail_number = await open_detail_and_get_number(page, row_index)

        await context.push_data(
            RowData(
                company=company,
                date=date,
                number=number,
                detail_number=detail_number,
            ).__dict__
        )

    next_btn = page.locator('button.btn-next:not(.disabled)')
    if await next_btn.count() > 0:
        await next_btn.click()
        await page.wait_for_load_state('networkidle')
        pbar.update(1)
        await scrape_list_page(context, pbar)


async def open_detail_and_get_number(page: Page, row_index: int) -> Optional[str]:
    detail_cell = page.locator('table.el-table__body tbody tr').nth(row_index).locator('span.url')
    if await detail_cell.count() == 0:
        return None

    popup_ctx = page.expect_popup()
    await detail_cell.click()
    detail_page = await popup_ctx
    async with contextlib.AsyncExitStack() as stack:
        stack.push_async_callback(detail_page.close)

        await detail_page.wait_for_load_state('networkidle')
        await detail_page.wait_for_selector('span:has-text("????")', timeout=30_000)

        details_text = await detail_page.locator('span:has-text("????")').inner_text()
        match = re.search(r"??????(\S+)", details_text)
        return match.group(1) if match else None


async def run_crawler() -> None:
    pbar = tqdm(total=100, desc="???", unit="?")

    crawler = PlaywrightCrawler(
        browser_launch_options={"timeout": 60_000},
        max_requests_per_crawl=1_000,
    )

    @crawler.router.default_handler
    async def handler(context: PlaywrightCrawlingContext) -> None:
        page = context.page
        url = context.request.url

        if "login" in url:
            await page.wait_for_selector('input[placeholder="???"]', timeout=30_000)
            await page.fill('input[placeholder="???"]', "????")
            await page.fill('input[placeholder="??"]', "????")
            await page.click('button:has-text("??")')
            await page.wait_for_url("**/jdjcrw?*", timeout=30_000)

            await page.goto(TASK_URL)
            await page.wait_for_load_state("networkidle")

            await fill_date_range(page)
            await choose_agency(page)
            await page.click('button:has-text("??")')
            await page.wait_for_load_state("networkidle")

            await scrape_list_page(context, pbar)

    await crawler.run([LOGIN_URL])

    pbar.close()
    await crawler.export_data("????_2021-2025.json")


def main() -> None:
    asyncio.run(run_crawler())


if __name__ == "__main__":
    main()
