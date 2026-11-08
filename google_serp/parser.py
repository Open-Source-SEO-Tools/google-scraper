"""Parse rendered Google HTML. Keep feature cards out of organic positions."""

from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

AIO = "[data-attrid='AIOverview'], [data-aim], [data-ai-overview]"
PAA = ".related-question-pair, [jsname='N760b'], .dnXCYb, [data-q]"
ADS = "#tads, #tadsb, [data-text-ad], [data-ad], [data-pla]"
EXCLUDE = f"{AIO}, {PAA}, {ADS}, .kp-wholepage, [data-local-pack]"


def text(node):
    return node.get_text(" ", strip=True) if node else ""


def clean_url(href):
    """Unwrap Google redirects; accept only absolute web links without credentials."""
    if not isinstance(href, str):
        return ""
    if href.startswith("/url?"):
        params = parse_qs(urlsplit(href).query)
        href = (params.get("q") or params.get("url") or [""])[0]
    try:
        parts = urlsplit(href)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return ""
        if parts.username or parts.password:
            return ""
    except ValueError:
        return ""
    return href


def external_url(href):
    url = clean_url(href)
    host = urlsplit(url).hostname or ""
    # Internal Google navigation is not an organic result. Other Google
    # properties (for example support.google.com) can be real organic results.
    if host in {"google.com", "www.google.com", "maps.google.com", "accounts.google.com"}:
        return ""
    return url


def base_result(query, provider, country, language):
    return {
        "query": query, "provider": provider, "country": country, "language": language,
        "status": "ok", "organic": [], "ai_overview": None, "people_also_ask": [],
        "warnings": [],
    }


def parse_html(html, *, query, provider="chrome", country="us", language="en", url=""):
    result = base_result(query, provider, country, language)
    soup = BeautifulSoup(html, "html.parser")
    visible_text = text(soup).lower()
    if (urlsplit(url).path.startswith("/sorry")
            or soup.select_one("#captcha-form, form[action*='/sorry/']")
            or "our systems have detected unusual traffic" in visible_text):
        result.update(status="blocked", error="Google returned /sorry or a CAPTCHA. Stop and try later.")
        return result
    if (urlsplit(url).hostname == "consent.google.com"
            or soup.select_one("form[action*='consent.google.com']")
            or "before you continue to google" in visible_text):
        result.update(status="consent_required", error="Google requires consent. Open your own Chrome, review it, then use CDP.")
        return result

    # Require an explicit AI marker; generic Google cards are not reliable AIO evidence.
    aio = soup.select_one(AIO)
    if aio:
        body = aio.select_one("[data-aip], .WaaZC, .PvHIRb") or aio
        citations, seen = [], set()
        for anchor in aio.select("a[href]"):
            target = external_url(anchor.get("href"))
            if target and target not in seen:
                seen.add(target)
                citations.append({"title": text(anchor), "url": target})
        answer = text(body)
        if answer:
            result["ai_overview"] = {"text": answer, "citations": citations}

    seen_questions = set()
    for card in soup.select(PAA):
        heading = card.select_one("[role='heading'], .CSkcDe, .iDjcJe, .JlqpRe")
        question = card.get("data-q") or text(heading)
        if not question or question in seen_questions:
            continue
        seen_questions.add(question)
        answer = card.select_one(".hgKElc, .wDYxhc, [data-attrid*='description']")
        source = next((external_url(a.get("href")) for a in card.select("a[href]")
                       if external_url(a.get("href"))), "")
        result["people_also_ask"].append({
            "question": question, "answer": text(answer), "url": source,
        })

    # Remove all features before identifying organic headings. Citation and PAA
    # cards can reuse Google's organic classes, so classes alone are unsafe.
    for node in list(soup.select(EXCLUDE)):
        if node.parent is not None:
            node.decompose()
    root = soup.select_one("#rso") or soup.select_one("#search") or soup
    seen, position = set(), 0
    for heading in root.select("h3"):
        anchor = heading.find_parent("a", href=True)
        if not anchor:
            continue
        target = external_url(anchor.get("href"))
        if not target:
            continue
        position += 1
        if target in seen:
            continue
        seen.add(target)
        card = heading.find_parent(class_=["MjjYud", "tF2Cxc", "g", "kCrYT"])
        snippet = card.select_one(".VwiC3b, .IsZvec, .aCOpRe") if card else None
        result["organic"].append({
            "position": position, "title": text(heading), "url": target, "snippet": text(snippet),
        })
    if not result["organic"]:
        if any(marker in visible_text for marker in (
                "did not match any documents", "no results found for")):
            result["status"] = "no_results"
        else:
            result.update(status="unparsed", error="No organic results recognized. Google may have changed its layout or shown a challenge.")
    result["warnings"].append("Only recognized DOM features are returned; empty features do not prove absence.")
    return result
