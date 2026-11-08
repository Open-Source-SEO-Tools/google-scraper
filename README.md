# Google SERP Scraper — student edition

Collect one Google search results page as JSON: organic results, AI Overview text
and citations when recognized, and People Also Ask questions with any answers
already in the page. Designed for SEO students at LLM Mastery, Chiang Mai,
14–15 November 2026. Python 3.10+ and Google Chrome are required.

There are two explicit providers: your local Chrome (default), or SerpApi using
your own environment variable. The program never switches providers automatically.
It has no database, account system, proxy pool, server or deployment requirement.

## Five-minute quickstart

Open a terminal in this folder. Install [Python](https://www.python.org/downloads/)
and [Google Chrome](https://www.google.com/chrome/) first if needed.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python serp.py "best coffee grinder"
```

On Windows PowerShell, use `.venv\Scripts\Activate.ps1` instead of `source`.
If your machine names Python `python3`, use that for the first command.
You do not need to download Playwright's Chromium: this uses installed Chrome.
Chrome opens with a temporary, separate profile and closes after the query.
Run it from your graphical desktop; Linux needs a working `DISPLAY`.

To learn the output before making a live request:

```bash
python serp.py "best coffee grinder" --demo
```

Actual output from this command (a **synthetic bundled HTML example**, not live rankings):

```json
{
  "query": "best coffee grinder",
  "provider": "demo",
  "country": "us",
  "language": "en",
  "status": "ok",
  "organic": [
    {
      "position": 1,
      "title": "Choosing a coffee grinder",
      "url": "https://example.com/coffee-grinders",
      "snippet": "Compare burr size, grind settings and cleaning."
    }
  ],
  "ai_overview": {
    "text": "Burr grinders give a more consistent grind than blade grinders.",
    "citations": [
      {
        "title": "Grind guide citation",
        "url": "https://example.com/grind-guide"
      }
    ]
  },
  "people_also_ask": [
    {
      "question": "Is a burr grinder better?",
      "answer": "Burr grinders usually produce more even particles.",
      "url": "https://example.com/burr-guide"
    }
  ],
  "warnings": [
    "Only recognized DOM features are returned; empty features do not prove absence."
  ]
}
```

## Your own Chrome through CDP

CDP lets Python open one new tab in a Chrome you started. Use a dedicated profile,
not your daily browser, and bind debugging to localhost. For Linux:

```bash
google-chrome --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 --user-data-dir=/tmp/serp-student-profile
```

Keep that Chrome open. In another terminal with your virtual environment active:

```bash
export SERP_CDP_URL=http://127.0.0.1:9222
python serp.py "best coffee grinder" --country us --language en
```

For macOS, launch `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
with the same flags. Windows users can launch `chrome.exe` with the same flags
and a new profile directory; set `$env:SERP_CDP_URL='http://127.0.0.1:9222'` in
PowerShell. The command closes only the tab it creates and leaves your Chrome open.
Remote CDP endpoints and reserved workshop ports 9333/9345 are rejected.

## Optional API provider

Only choose this if you have a SerpApi account and want to use its quota. Enter
your key into an environment variable, never into Python or committed files.
On Bash, this reads it without displaying it or saving its value in shell history:

```bash
read -rs -p "SerpApi key: " SERPAPI_API_KEY
export SERPAPI_API_KEY
python serp.py "best coffee grinder" --provider serpapi
unset SERPAPI_API_KEY
```

`.env.example` lists the variable names. The script does **not** load `.env` files.
The API adapter makes one request, normalizes organic results and related questions,
and returns AI Overview text only if included in that response. If a second
request is needed for AI Overview, it returns a warning and makes no extra call.
It returns no account metadata or continuation values. Implementation references:
[search response](https://serpapi.com/search-api),
[AI Overview](https://serpapi.com/ai-overview), and
[related questions](https://serpapi.com/related-questions).

## Cost per run

- **Chrome:** $0 in API charges; uses your computer and internet connection.
- **Demo and tests:** $0; no network calls.
- **SerpApi:** one search request per run, charged against your own plan/quota.
  Effective cost per request is your plan price divided by included searches,
  plus any applicable overage. Check [current plans](https://serpapi.com/pricing)
  before selecting this provider. Failed requests may also consume provider quota.
  No API or paid LLM calls were made to verify this student edition.

## Limits and interpreting results

- Google blocked the real local query `best coffee grinder` during verification
  on 8 November 2026. The command returned `status: "blocked"`, empty results and
  exit code 1. This is **not** a successful ranking measurement. No retry,
  challenge bypass or paid fallback was attempted.
- If Google shows `/sorry` or a CAPTCHA, stop. Consent screens return
  `consent_required`; review consent yourself in your own dedicated Chrome.
- Live successful organic/PAA/AI Overview extraction is **not verified** here.
  Offline fixtures verify the parser; the SerpApi adapter uses mocked responses.
- This is a small teaching parser. Google changes its markup. Only explicit AI
  markers are recognized; missing features can mean unsupported markup. Confirm
  important readings in a browser. AI Overview availability varies by query,
  location, language and account.
- One page only, no bulk jobs, automated retries, pagination, proxy rotation,
  CAPTCHA solving, PAA expansion or AI Overview “show more” clicks. Answers can be
  empty when they have not been loaded. Only English block/empty-page phrases
  are recognized in addition to URL and form markers.
- Country/language parameters influence Google but do not set your IP or give
  exact city rankings. Organic positions are observed candidate order, with gaps
  retained for duplicate URLs; this is not a complete rank-tracking service.
- Headings from unsupported feature layouts can be mistaken for organic results.
  Ads, recognized AI/PAA cards and recognized local/knowledge cards are excluded.
- JSON goes to standard output. Exit 0 means `ok` or explicit `no_results`;
  exit 1 means blocked, consent, unrecognized markup or provider failure;
  exit 2 means invalid command arguments.
- No raw HTML, browser profile, cookies or search history is saved by this project.
  Attached Chrome manages its own profile as usual. If you save output yourself,
  review it before sharing. Use neutral practice queries, not private client data.

## Tests and code map

```bash
python -m unittest discover -s tests -v
```

`serp.py` handles the command, `google_serp/providers.py` fetches one page or
response, and `google_serp/parser.py` extracts fields. Tests cover feature
separation, duplicate positions, challenge/consent handling, explicit provider
selection, redacted errors and Chrome tab ownership. To add a provider, implement
`search(query, country, language)` returning the same JSON shape, then register
it in `serp.py`.

This is a small reimplementation of parsing/provider ideas from
[SEOShipper/google-scraper](https://github.com/SEOShipper/google-scraper) and the
serp-master approach. Production infrastructure and source history are not included.

## Licence

MIT — see [LICENSE](LICENSE).
