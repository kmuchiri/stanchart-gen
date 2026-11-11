import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json

import scrape


class TestScraper(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.events_file = Path(self.test_dir) / "events.json"
        self.output_dir = Path(self.test_dir) / "xml"
        self.log_file = Path(self.test_dir) / "logs" / "test.log"

        self.mock_events = [
            {"eventName": "5K", "eventURL": "https://example.com/races/5k/"},
            {"eventName": "10K", "eventURL": "https://example.com/races/10k/"},
            {"eventName": "half-marathon", "eventURL": "https://example.com/races/half/"}
        ]

        with open(self.events_file, "w") as f:
            json.dump(self.mock_events, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_valid_event(self):
        self.assertEqual(scrape.validEvent(self.mock_events, "5K"), "https://example.com/races/5k/")
        # Case insensitive check
        self.assertEqual(scrape.validEvent(self.mock_events, "5k"), "https://example.com/races/5k/")
        self.assertEqual(scrape.validEvent(self.mock_events, "HALF-MARATHON"), "https://example.com/races/half/")
        # Non-existent event
        self.assertIsNone(scrape.validEvent(self.mock_events, "ultra-marathon"))

    @patch("scrape.requests.get")
    def test_load_xml_success_not_last(self, mock_get):
        xml_content = b"<PagedResponse><last>false</last><numberOfElements>10</numberOfElements></PagedResponse>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = xml_content
        mock_get.return_value = mock_resp

        dest = Path(self.output_dir) / "page_0"
        is_last = scrape.loadXML("https://example.com/page0", str(dest))
        self.assertFalse(is_last)
        self.assertTrue(Path(f"{dest}.xml").exists())
        with open(f"{dest}.xml", "rb") as f:
            self.assertEqual(f.read(), xml_content)

    @patch("scrape.requests.get")
    def test_load_xml_success_last_page(self, mock_get):
        xml_content = b"<PagedResponse><last>true</last><numberOfElements>5</numberOfElements></PagedResponse>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = xml_content
        mock_get.return_value = mock_resp

        dest = Path(self.output_dir) / "page_last"
        is_last = scrape.loadXML("https://example.com/last", str(dest))
        self.assertTrue(is_last)

    @patch("scrape.loadXML")
    def test_fetch_event_pagination(self, mock_load_xml):
        # Page 0 not last, Page 1 last
        mock_load_xml.side_effect = [False, True]

        pages = scrape.fetchEvent("5K", "https://example.com/5k/", output_dir=self.output_dir, delay=0.01)
        self.assertEqual(pages, 2)
        self.assertEqual(mock_load_xml.call_count, 2)

        # Check call URLs
        first_call_url = mock_load_xml.call_args_list[0][0][0]
        second_call_url = mock_load_xml.call_args_list[1][0][0]
        self.assertIn("page=0", first_call_url)
        self.assertIn("page=1", second_call_url)

    @patch("scrape.loadXML")
    def test_fetch_event_custom_start_page(self, mock_load_xml):
        # Start from page 5, page 5 not last, page 6 last
        mock_load_xml.side_effect = [False, True]

        pages = scrape.fetchEvent(
            "5K",
            "https://example.com/5k/",
            output_dir=self.output_dir,
            delay=0.01,
            start_page=5,
        )
        self.assertEqual(pages, 2)
        self.assertEqual(mock_load_xml.call_count, 2)

        first_call_url = mock_load_xml.call_args_list[0][0][0]
        second_call_url = mock_load_xml.call_args_list[1][0][0]
        self.assertIn("page=5", first_call_url)
        self.assertIn("page=6", second_call_url)

    @patch("scrape.fetchEvent")
    def test_main_start_from_page_option(self, mock_fetch):
        for flag in ["-p", "--start-page", "--start-from-page"]:
            mock_fetch.reset_mock()
            test_args = [
                "scrape.py",
                "-e", "5K",
                flag, "10",
                "--events-file", str(self.events_file),
                "--output-dir", str(self.output_dir),
                "--log-file", str(self.log_file),
                "--delay", "0.01"
            ]
            with patch.object(sys, "argv", test_args):
                scrape.main()

            self.assertEqual(mock_fetch.call_count, 1)
            self.assertEqual(mock_fetch.call_args[1]["start_page"], 10)

            with open(self.log_file, "r") as f:
                log_text = f.read()
            self.assertIn("Start page: 10", log_text)

    def test_main_negative_start_page(self):
        test_args = [
            "scrape.py",
            "-e", "5K",
            "--start-page", "-1",
            "--events-file", str(self.events_file),
            "--output-dir", str(self.output_dir),
            "--log-file", str(self.log_file),
        ]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                scrape.main()
            self.assertEqual(cm.exception.code, 2)

    @patch("scrape.fetchEvent")
    def test_main_all_events(self, mock_fetch):
        test_args = [
            "scrape.py",
            "--events-file", str(self.events_file),
            "--output-dir", str(self.output_dir),
            "--log-file", str(self.log_file),
            "--delay", "0.01"
        ]
        with patch.object(sys, "argv", test_args):
            scrape.main()

        self.assertEqual(mock_fetch.call_count, 3)

        # Check log file contents
        self.assertTrue(self.log_file.exists())
        with open(self.log_file, "r") as f:
            log_text = f.read()
        self.assertIn("Scraper started at:", log_text)
        self.assertIn("Scrape target: all events", log_text)
        self.assertIn("Scraper completed at:", log_text)

    @patch("scrape.fetchEvent")
    def test_main_specific_event_flag(self, mock_fetch):
        test_args = [
            "scrape.py",
            "-e", "10K",
            "--events-file", str(self.events_file),
            "--output-dir", str(self.output_dir),
            "--log-file", str(self.log_file),
            "--delay", "0.01"
        ]
        with patch.object(sys, "argv", test_args):
            scrape.main()

        self.assertEqual(mock_fetch.call_count, 1)
        self.assertEqual(mock_fetch.call_args[1]["eventName"], "10K")

        with open(self.log_file, "r") as f:
            log_text = f.read()
        self.assertIn("Scrape target: specific event '10K'", log_text)
        self.assertIn("Scraper completed at:", log_text)

    @patch("scrape.fetchEvent")
    def test_main_specific_event_positional(self, mock_fetch):
        test_args = [
            "scrape.py",
            "half-marathon",
            "--events-file", str(self.events_file),
            "--output-dir", str(self.output_dir),
            "--log-file", str(self.log_file),
            "--delay", "0.01"
        ]
        with patch.object(sys, "argv", test_args):
            scrape.main()

        self.assertEqual(mock_fetch.call_count, 1)
        self.assertEqual(mock_fetch.call_args[1]["eventName"], "half-marathon")

        with open(self.log_file, "r") as f:
            log_text = f.read()
        self.assertIn("Scrape target: specific event 'half-marathon'", log_text)
        self.assertIn("Scraper completed at:", log_text)

    @patch("scrape.fetchEvent")
    def test_main_keyboard_interrupt(self, mock_fetch):
        mock_fetch.side_effect = KeyboardInterrupt()

        test_args = [
            "scrape.py",
            "-e", "5K",
            "--events-file", str(self.events_file),
            "--output-dir", str(self.output_dir),
            "--log-file", str(self.log_file),
            "--delay", "0.01"
        ]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                scrape.main()
            self.assertEqual(cm.exception.code, 130)

        with open(self.log_file, "r") as f:
            log_text = f.read()
        self.assertIn("Scraper interrupted at:", log_text)

    @patch("scrape.fetchEvent")
    def test_main_error_logging(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError("Connection dropped")

        test_args = [
            "scrape.py",
            "-e", "5K",
            "--events-file", str(self.events_file),
            "--output-dir", str(self.output_dir),
            "--log-file", str(self.log_file),
            "--delay", "0.01"
        ]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                scrape.main()
            self.assertEqual(cm.exception.code, 1)

        with open(self.log_file, "r") as f:
            log_text = f.read()
        self.assertIn("Scraper failed with error at:", log_text)
        self.assertIn("Connection dropped", log_text)


if __name__ == "__main__":
    import sys
    unittest.main()
