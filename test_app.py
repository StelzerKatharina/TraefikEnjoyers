import unittest

from app import format_visible_at, parse_observation, render_page


class AppTests(unittest.TestCase):
    def test_parse_observation_accepts_valid_payload(self) -> None:
        entry = parse_observation("animal=Fox&stream=North+Cam&visibleAt=2026-10-28T14%3A00")
        self.assertEqual(
            entry,
            {"animal": "Fox", "stream": "North Cam", "visible_at": "2026-10-28 14:00"},
        )

    def test_parse_observation_rejects_missing_fields(self) -> None:
        self.assertIsNone(parse_observation("animal=Fox&stream=&visibleAt=2026-10-28T14%3A00"))

    def test_render_page_escapes_content(self) -> None:
        html = render_page(
            [{"animal": "<wolf>", "stream": "C&N", "visible_at": "2026-10-28 14:00"}]
        ).decode("utf-8")
        self.assertIn("&lt;wolf&gt;", html)
        self.assertIn("C&amp;N", html)

    def test_format_visible_at_keeps_invalid_value(self) -> None:
        self.assertEqual(format_visible_at("not-a-date"), "not-a-date")


if __name__ == "__main__":
    unittest.main()
