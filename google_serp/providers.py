"""Explicit providers: one local Chrome query OR one API request; no fallback."""

import os
from urllib.parse import urlencode, urlsplit

import httpx

from .parser import base_result, clean_url, parse_html


class ProviderError(Exception):
    """Safe error message that never includes request URLs or credentials."""


def validate_cdp(endpoint):
    try:
        parts = urlsplit(endpoint)
        if (parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parts.username or parts.password or parts.path not in {"", "/"}
                or parts.query or parts.fragment or parts.port is None):
            raise ValueError
        # Keep shared workshop browsers isolated from this example.
        if parts.port in {9333, 9345}:
            raise ValueError
    except ValueError:
        raise ProviderError("Use a local CDP endpoint such as http://127.0.0.1:9222 on a dedicated Chrome profile.") from None
    return endpoint


class ChromeProvider:
    def __init__(self, cdp_url=None):
        self.cdp_url = validate_cdp(cdp_url) if cdp_url else None

    def search(self, query, country, language):
        from playwright.sync_api import Error, sync_playwright

        browser, page = None, None
        try:
            with sync_playwright() as playwright:
                if self.cdp_url:
                    browser = playwright.chromium.connect_over_cdp(self.cdp_url, timeout=15000)
                else:
                    # Installed Google Chrome, headful, with a temporary profile.
                    # Playwright removes this profile when our browser closes.
                    browser = playwright.chromium.launch(channel="chrome", headless=False)
                try:
                    if self.cdp_url:
                        if not browser.contexts:
                            raise ProviderError("Chrome has no browser context. Open a normal window in your dedicated profile.")
                        page = browser.contexts[0].new_page()
                    else:
                        page = browser.new_page()
                    response = page.goto("https://www.google.com/search?" + urlencode({
                        "q": query, "gl": country, "hl": language,
                    }), wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3000)
                    result = parse_html(page.content(), query=query, country=country,
                                        language=language, url=page.url)
                    if response and response.status in {403, 429} and result["status"] != "blocked":
                        result.update(status="blocked", error="Google refused this request. Stop and try later.")
                    return result
                finally:
                    if page:
                        page.close()
                    if browser and not self.cdp_url:
                        browser.close()
                    # Exiting sync_playwright disconnects CDP without closing
                    # the user's browser or touching any of their other tabs.
        except Error:
            raise ProviderError("Chrome failed to launch, connect, or load Google. Install Google Chrome, use a desktop session, or set SERP_CDP_URL for a dedicated Chrome.") from None


def block_text(blocks):
    """Flatten documented API text blocks without returning response metadata."""
    pieces = []
    for block in blocks or []:
        if block.get("snippet"):
            pieces.append(block["snippet"])
        pieces.extend(filter(None, [block_text(block.get("text_blocks")), block_text(block.get("list"))]))
    return "\n".join(pieces)


def parse_serpapi(data, query, country, language):
    result = base_result(query, "serpapi", country, language)
    # Never echo raw errors: upstream metadata can contain the authenticated URL.
    if data.get("error"):
        result.update(status="provider_error", error="SerpApi could not complete this search. Check your account and quota.")
        return result
    seen = set()
    for ordinal, row in enumerate(data.get("organic_results") or [], 1):
        target = clean_url(row.get("link"))
        if not target or target in seen:
            continue
        seen.add(target)
        result["organic"].append({"position": row.get("position", ordinal),
                                  "title": row.get("title", ""), "url": target,
                                  "snippet": row.get("snippet", "")})
    for row in data.get("related_questions") or []:
        if row.get("question"):
            result["people_also_ask"].append({"question": row["question"],
                                            "answer": row.get("snippet", ""),
                                            "url": clean_url(row.get("link"))})
    aio = data.get("ai_overview") or {}
    answer = block_text(aio.get("text_blocks"))
    if answer:
        result["ai_overview"] = {"text": answer, "citations": [
            {"title": row.get("title", ""), "url": clean_url(row.get("link"))}
            for row in aio.get("references") or [] if clean_url(row.get("link"))]}
    elif aio.get("page_token"):
        result["warnings"].append("AI Overview requires another API request; it was not fetched to keep this run to one request.")
    if not result["organic"]:
        if (data.get("search_information") or {}).get("organic_results_state") == "Fully empty":
            result["status"] = "no_results"
        else:
            result.update(status="unparsed", error="API returned no recognizable organic results; this is not proof of no matches.")
    return result


class SerpApiProvider:
    def search(self, query, country, language):
        api_key = os.environ.get("SERPAPI_API_KEY", "").strip()
        if not api_key:
            raise ProviderError("Set SERPAPI_API_KEY in your shell before using --provider serpapi.")
        try:
            # Fixed HTTPS origin. No redirects, retries, pagination, or extra AIO call.
            with httpx.Client(timeout=60, follow_redirects=False, trust_env=False) as client:
                response = client.get("https://serpapi.com/search.json", params={
                    "engine": "google", "q": query, "gl": country, "hl": language,
                    "api_key": api_key,
                })
                response.raise_for_status()
                data = response.json()
            if not isinstance(data, dict):
                raise ValueError
            return parse_serpapi(data, query, country, language)
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            raise ProviderError("SerpApi request failed. Check connectivity, account and quota. No fallback was attempted.") from None
