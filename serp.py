"""Run with: python serp.py 'best coffee grinder'. JSON goes to stdout."""

import argparse
import json
import os
from pathlib import Path

from google_serp.parser import base_result, parse_html
from google_serp.providers import ChromeProvider, ProviderError, SerpApiProvider


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect one Google results page as JSON. Chrome is the default; APIs are explicit.")
    parser.add_argument("query", help="Search text, in quotes")
    parser.add_argument("--provider", choices=("chrome", "serpapi"), default="chrome")
    parser.add_argument("--country", default="us", help="Google country code (default: us); not exact city targeting")
    parser.add_argument("--language", default="en", help="Google language code (default: en)")
    parser.add_argument("--demo", action="store_true", help="Parse the bundled synthetic sample, without network access")
    args = parser.parse_args(argv)
    if not args.query.strip():
        parser.error("query must not be blank")
    if args.demo:
        fixture = Path(__file__).parent / "tests" / "fixtures" / "sample.html"
        result = parse_html(fixture.read_text(encoding="utf-8"), query=args.query,
                            provider="demo", country=args.country, language=args.language)
    else:
        try:
            provider = (ChromeProvider(os.environ.get("SERP_CDP_URL")) if args.provider == "chrome"
                        else SerpApiProvider())
            result = provider.search(args.query, args.country, args.language)
        except ProviderError as exc:
            result = base_result(args.query, args.provider, args.country, args.language)
            result.update(status="provider_error", error=str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"ok", "no_results"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
