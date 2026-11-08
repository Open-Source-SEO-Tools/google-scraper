import unittest
from pathlib import Path

from google_serp.parser import clean_url, parse_html


class ParserTests(unittest.TestCase):
    def parse(self, html, **kwargs):
        return parse_html(html, query="best coffee grinder", **kwargs)

    def test_sample_separates_organic_aio_paa_and_ads(self):
        html = (Path(__file__).parent / "fixtures" / "sample.html").read_text()
        result = self.parse(html)
        self.assertEqual(result["status"], "ok")
        self.assertEqual([row["url"] for row in result["organic"]],
                         ["https://example.com/coffee-grinders"])
        self.assertEqual(result["ai_overview"]["citations"][0]["url"],
                         "https://example.com/grind-guide")
        self.assertEqual(result["people_also_ask"][0]["question"], "Is a burr grinder better?")

    def test_duplicate_does_not_compact_positions(self):
        html = "".join(f'<a href="https://example.com/{path}"><h3>Result</h3></a>'
                       for path in ["one", "one", "three"])
        self.assertEqual([row["position"] for row in self.parse(html)["organic"]], [1, 3])

    def test_unwraps_encoded_url_once(self):
        self.assertEqual(clean_url("/url?q=https%3A%2F%2Fexample.com%2Fa%253Fb&sa=U"),
                         "https://example.com/a%3Fb")

    def test_unsafe_links_are_not_results(self):
        self.assertEqual(clean_url("javascript:alert(1)"), "")
        self.assertEqual(clean_url("/search?q=next"), "")
        self.assertEqual(clean_url("https://[invalid"), "")

    def test_organic_google_property_is_retained_but_navigation_is_not(self):
        html = ('<a href="https://maps.google.com/place"><h3>Map</h3></a>'
                '<a href="https://support.google.com/search"><h3>Support</h3></a>')
        self.assertEqual([row["position"] for row in self.parse(html)["organic"]], [1])
        self.assertEqual(self.parse(html)["organic"][0]["title"], "Support")

    def test_sorry_url_stops_before_parsing_results(self):
        result = self.parse('<a href="https://example.com"><h3>Result</h3></a>',
                            url="https://www.google.com/sorry/index")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["organic"], [])

    def test_sorry_body_and_captcha_are_classified(self):
        for html in ['<form id="captcha-form"></form>',
                     'Our systems have detected unusual traffic from your computer network']:
            self.assertEqual(self.parse(html)["status"], "blocked")

    def test_consent_is_not_reported_as_empty_search(self):
        self.assertEqual(self.parse("Before you continue to Google")["status"], "consent_required")

    def test_unknown_layout_is_not_reported_as_no_matches(self):
        self.assertEqual(self.parse("<html>Changed layout</html>")["status"], "unparsed")
        self.assertEqual(self.parse("Your search did not match any documents")["status"], "no_results")

    def test_generic_card_is_not_invented_ai_overview(self):
        result = self.parse('<div class="ULSxyf">A generic Google feature card.</div>')
        self.assertIsNone(result["ai_overview"])

    def test_nested_feature_cards_are_safe_to_remove(self):
        result = self.parse('<section data-aim><div data-ai-overview>AI text</div></section>')
        self.assertEqual(result["organic"], [])


if __name__ == "__main__":
    unittest.main()
