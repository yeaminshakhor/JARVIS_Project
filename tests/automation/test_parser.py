import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.automation.parser import CommandParser


class TestCommandParser(unittest.TestCase):
    def setUp(self):
        self.parser = CommandParser(
            app_names=["calculator", "terminal"],
            website_names=["youtube", "google"],
        )

    def test_parse_open_website(self):
        parsed = self.parser.parse("open youtube")
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].get("action"), "open_website")
        self.assertEqual(parsed[0].get("website"), "youtube")

    def test_parse_search(self):
        parsed = self.parser.parse("search python unittest")
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].get("action"), "search_web")
        self.assertEqual(parsed[0].get("query"), "python unittest")

    def test_parse_open_app_fallback(self):
        parsed = self.parser.parse("open mycustomapp")
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].get("action"), "open_app")
        self.assertEqual(parsed[0].get("app_name"), "mycustomapp")

    def test_parse_multi_command(self):
        parsed = self.parser.parse("open youtube and search python unittest then open terminal")
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0].get("action"), "open_website")
        self.assertEqual(parsed[0].get("website"), "youtube")
        self.assertEqual(parsed[1].get("action"), "search_web")
        self.assertEqual(parsed[2].get("action"), "open_app")
        self.assertEqual(parsed[2].get("app_name"), "terminal")

    def test_context_reuse_again(self):
        first = self.parser.parse("open terminal")
        self.assertEqual(first[0].get("action"), "open_app")
        second = self.parser.parse("open it again")
        self.assertEqual(second[0].get("action"), "open_app")
        self.assertEqual(second[0].get("app_name"), "terminal")


if __name__ == "__main__":
    unittest.main()
