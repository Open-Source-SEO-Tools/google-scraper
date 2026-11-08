import contextlib
import io
import json
import os
import unittest
import uuid
from unittest.mock import MagicMock, patch

import httpx

import serp
from google_serp.providers import ChromeProvider, ProviderError, SerpApiProvider, parse_serpapi, validate_cdp


class ProviderTests(unittest.TestCase):
    def test_cdp_rejects_protected_ports_and_remote_hosts(self):
        for endpoint in ["http://127.0.0.1:9333", "http://127.0.0.1:9345",
                         "http://example.com:9222", "https://localhost:9222",
                         "http://localhost:9222/path", "http://localhost:invalid"]:
            with self.subTest(endpoint=endpoint), self.assertRaises(ProviderError):
                validate_cdp(endpoint)
        self.assertEqual(validate_cdp("http://127.0.0.1:9222"), "http://127.0.0.1:9222")

    def test_missing_api_key_does_not_make_request(self):
        with patch.dict(os.environ, {}, clear=True), patch("httpx.Client") as client:
            with self.assertRaises(ProviderError):
                SerpApiProvider().search("coffee", "us", "en")
            client.assert_not_called()

    def test_api_mapping_preserves_positions_and_nested_ai_text(self):
        result = parse_serpapi({
            "organic_results": [{"position": 3, "title": "Grinders", "link": "https://example.com"}],
            "related_questions": [{"question": "How fine should I grind?"}],
            "ai_overview": {"text_blocks": [{"snippet": "Choose burrs."},
                                             {"list": [{"snippet": "Adjust the grind."}]}],
                            "references": [{"link": "https://example.com/guide", "title": "Guide"}]},
        }, "coffee", "us", "en")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["organic"][0]["position"], 3)
        self.assertEqual(result["ai_overview"]["text"], "Choose burrs.\nAdjust the grind.")
        self.assertEqual(result["people_also_ask"][0]["answer"], "")

    def test_api_does_not_return_continuation_or_metadata(self):
        result = parse_serpapi({"ai_overview": {"page_token": uuid.uuid4().hex},
                               "search_metadata": {"raw_html_file": "https://example.com/private"}},
                              "coffee", "us", "en")
        self.assertIsNone(result["ai_overview"])
        self.assertTrue(result["warnings"])
        self.assertNotIn("search_metadata", result)
        self.assertNotIn("page_token", json.dumps(result))

    def test_api_errors_do_not_echo_credentials(self):
        credential = uuid.uuid4().hex
        result = parse_serpapi({"error": credential}, "coffee", "us", "en")
        self.assertNotIn(credential, json.dumps(result))
        self.assertEqual(result["status"], "provider_error")

    def test_http_error_is_redacted_and_one_request_only(self):
        credential = uuid.uuid4().hex
        with patch.dict(os.environ, {"SERPAPI_API_KEY": credential}), patch("httpx.Client") as client:
            get = client.return_value.__enter__.return_value.get
            get.side_effect = httpx.ConnectError(credential)
            with self.assertRaises(ProviderError) as raised:
                SerpApiProvider().search("coffee", "us", "en")
            self.assertNotIn(credential, str(raised.exception))
            self.assertEqual(get.call_count, 1)

    def test_api_success_uses_fixed_origin_and_does_not_follow_up(self):
        with patch.dict(os.environ, {"SERPAPI_API_KEY": uuid.uuid4().hex}), patch("httpx.Client") as client:
            get = client.return_value.__enter__.return_value.get
            get.return_value.json.return_value = {
                "organic_results": [{"title": "Coffee", "link": "https://example.com"}],
                "ai_overview": {"page_token": uuid.uuid4().hex},
            }
            result = SerpApiProvider().search("coffee", "us", "en")
            self.assertEqual(result["status"], "ok")
            self.assertEqual(get.call_count, 1)
            self.assertEqual(get.call_args.args[0], "https://serpapi.com/search.json")
            self.assertFalse(client.call_args.kwargs["follow_redirects"])

    def test_default_cli_uses_chrome_and_never_api_after_block(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch("serp.ChromeProvider") as chrome, \
                patch("serp.SerpApiProvider") as api, contextlib.redirect_stdout(output):
            chrome.return_value.search.return_value = {"status": "blocked"}
            self.assertEqual(serp.main(["best coffee grinder"]), 1)
            api.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"], "blocked")

    def test_demo_has_no_network_and_returns_real_parser_output(self):
        with patch("serp.ChromeProvider") as chrome, patch("serp.SerpApiProvider") as api, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(serp.main(["best coffee grinder", "--demo"]), 0)
            chrome.assert_not_called()
            api.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["provider"], "demo")

    def test_cdp_closes_only_new_tab_and_local_mode_closes_owned_browser(self):
        for endpoint in [None, "http://127.0.0.1:9222"]:
            with self.subTest(endpoint=endpoint), patch("playwright.sync_api.sync_playwright") as manager:
                playwright = manager.return_value.__enter__.return_value
                browser = MagicMock()
                playwright.chromium.launch.return_value = browser
                playwright.chromium.connect_over_cdp.return_value = browser
                page = MagicMock()
                browser.new_page.return_value = page
                browser.contexts = [MagicMock()]
                browser.contexts[0].new_page.return_value = page
                page.content.return_value = '<form id="captcha-form"></form>'
                page.url = "https://www.google.com/sorry/index"
                result = ChromeProvider(endpoint).search("coffee", "us", "en")
                self.assertEqual(result["status"], "blocked")
                page.goto.assert_called_once()
                page.close.assert_called_once()
                if endpoint:
                    browser.close.assert_not_called()
                    playwright.chromium.launch.assert_not_called()
                else:
                    browser.close.assert_called_once()
                    self.assertFalse(playwright.chromium.launch.call_args.kwargs["headless"])

    def test_owned_chrome_is_closed_if_new_tab_fails(self):
        from playwright.sync_api import Error

        with patch("playwright.sync_api.sync_playwright") as manager:
            browser = manager.return_value.__enter__.return_value.chromium.launch.return_value
            browser.new_page.side_effect = Error("Cannot create tab")
            with self.assertRaises(ProviderError):
                ChromeProvider().search("coffee", "us", "en")
            browser.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
