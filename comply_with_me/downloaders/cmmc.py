"""CMMC resources downloader (requires Playwright — DoD portal blocks headless requests)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from .base import (
    RATE_LIMIT_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENT,
    DownloadResult,
    download_file,
    require_playwright,
    sanitize_filename,
)

SOURCE_URL = "https://dodcio.defense.gov/cmmc/Resources-Documentation/"
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}

# DNN CMS module IDs for the two sections on the CMMC resources page
SECTION_MODULES = {
    "internal": "dnn_ctr136430_ModuleContent",
    "external": "dnn_ctr136428_ModuleContent",
}

# These three PDFs are reliably blocked by the DoD portal in headless mode.
# They are tracked here so they can be surfaced as manual-download instructions.
KNOWN_BLOCKED = {
    "CMMC-FAQsv3.pdf",
    "CMMC-101-Nov2025.pdf",
    "FulcrumAdvStrat.pdf",
}


def _fetch_html() -> str:
    require_playwright()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(SOURCE_URL, wait_until="networkidle")
        html = page.content()
        browser.close()
    return html


def _parse_links(html: str) -> list[tuple[str, str, str]]:
    """Return list of (section, filename, url) for all downloadable links."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    for section, module_id in SECTION_MODULES.items():
        container = soup.find(id=module_id)
        if not container:
            continue
        for anchor in container.find_all("a", href=True):
            raw_href = anchor["href"].strip()
            if not raw_href:
                continue
            url = urljoin(SOURCE_URL, raw_href)
            if url in seen:
                continue
            ext = Path(urlparse(url).path).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            seen.add(url)
            filename = sanitize_filename(Path(urlparse(url).path).name)
            links.append((section, filename, url))

    return links


def _playwright_download(
    links: list[tuple[str, str, str]], dest: Path, force: bool
) -> DownloadResult:
    """Download files using Playwright browser context (handles DoD auth/redirect)."""
    require_playwright()
    from playwright.sync_api import sync_playwright

    result = DownloadResult(framework="cmmc")
    import time

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        page.goto(SOURCE_URL, wait_until="networkidle")

        for _section, filename, url in links:
            target = dest / filename
            if target.exists() and target.stat().st_size > 0 and not force:
                result.skipped.append(filename)
                continue

            locator = page.locator(f"a[href='{url}']")
            if locator.count() == 0:
                # Link not clickable via Playwright — try direct HTTP download
                session = requests.Session()
                ok, msg = download_file(session, url, target, force=force, referer=SOURCE_URL)
                if msg == "skipped":
                    result.skipped.append(filename)
                elif ok:
                    result.downloaded.append(filename)
                else:
                    if filename in KNOWN_BLOCKED:
                        result.manual_required.append((filename, url))
                    else:
                        result.errors.append((filename, msg))
                continue

            try:
                time.sleep(RATE_LIMIT_DELAY)
                target.parent.mkdir(parents=True, exist_ok=True)
                with page.expect_download(timeout=REQUEST_TIMEOUT * 1000) as dl_info:
                    locator.first.click()
                dl_info.value.save_as(str(target))
                if target.stat().st_size == 0:
                    target.unlink(missing_ok=True)
                    raise OSError("Empty file")
                result.downloaded.append(filename)
            except Exception as exc:  # noqa: BLE001
                if filename in KNOWN_BLOCKED:
                    result.manual_required.append((filename, url))
                else:
                    result.errors.append((filename, str(exc)))

        browser.close()

    return result


def run(output_dir: Path, dry_run: bool = False, force: bool = False) -> DownloadResult:
    dest = output_dir / "cmmc"

    html = _fetch_html()
    links = _parse_links(html)

    if not links:
        result = DownloadResult(framework="cmmc")
        result.errors.append(("", "No downloadable links found on CMMC page"))
        return result

    if dry_run:
        result = DownloadResult(framework="cmmc")
        for _section, filename, _url in links:
            target = dest / filename
            if target.exists() and target.stat().st_size > 0 and not force:
                result.skipped.append(filename)
            else:
                result.downloaded.append(filename)
        return result

    dest.mkdir(parents=True, exist_ok=True)
    return _playwright_download(links, dest, force)
