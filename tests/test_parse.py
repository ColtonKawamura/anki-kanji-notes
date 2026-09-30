"""Tests for kanji extraction and Jisho HTML parsing (no network required)."""

import importlib.util
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _load_script():
    path = os.path.join(REPO_ROOT, "updateKanji")
    spec = importlib.util.spec_from_loader(
        "updatekanji", importlib.machinery.SourceFileLoader("updatekanji", path)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


updateKanji = _load_script()


def read_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return handle.read()


class StripHtmlTest(unittest.TestCase):
    def test_empty_variants(self):
        for value in ["", "   ", "<br>", "<br/>", "&nbsp;", "<div></div>", "<div><br></div>"]:
            self.assertTrue(updateKanji.is_field_empty(value), value)

    def test_non_empty(self):
        self.assertFalse(updateKanji.is_field_empty("<div>水 water</div>"))


class ExtractKanjiTest(unittest.TestCase):
    def test_simple_word(self):
        self.assertEqual(updateKanji.extract_kanji("鼻水"), ["鼻", "水"])

    def test_ignores_kana_and_punctuation(self):
        self.assertEqual(updateKanji.extract_kanji("食べ物を、買う！"), ["食", "物", "買"])

    def test_ignores_html(self):
        self.assertEqual(updateKanji.extract_kanji("<div>鼻<br>水</div>"), ["鼻", "水"])

    def test_unique_in_order(self):
        self.assertEqual(updateKanji.extract_kanji("人人々人生"), ["人", "生"])

    def test_extension_a(self):
        self.assertEqual(updateKanji.extract_kanji("㐀"), ["㐀"])

    def test_no_kanji(self):
        self.assertEqual(updateKanji.extract_kanji("ひらがなだけ"), [])


class ParseJishoTest(unittest.TestCase):
    def test_single_readings(self):
        meanings, kun, on = updateKanji.parse_jisho_kanji_page(read_fixture("jisho_hana.html"))
        self.assertEqual(meanings, "nose, snout")
        self.assertEqual(kun, ["はな"])
        self.assertEqual(on, ["ビ"])

    def test_multiple_kun_readings(self):
        meanings, kun, on = updateKanji.parse_jisho_kanji_page(read_fixture("jisho_mizu.html"))
        self.assertEqual(meanings, "water")
        self.assertEqual(kun, ["みず", "みず-"])
        self.assertEqual(on, ["スイ"])

    def test_page_without_kanji(self):
        meanings, kun, on = updateKanji.parse_jisho_kanji_page(
            "<html><body><div id='result_area'></div></body></html>"
        )
        self.assertEqual((meanings, kun, on), ("", [], []))


class FormatTest(unittest.TestCase):
    def test_format_line(self):
        self.assertEqual(
            updateKanji.format_kanji_line("水", "water", ["みず", "みず-"], ["スイ"]),
            "水 water Kun: みず、 みず- On: スイ",
        )

    def test_omits_empty_parts(self):
        self.assertEqual(updateKanji.format_kanji_line("々", "repetition", [], []), "々 repetition")
        self.assertEqual(
            updateKanji.format_kanji_line("鼻", "nose, snout", [], ["ビ"]), "鼻 nose, snout On: ビ"
        )

    def test_notes_html_joins_with_br(self):
        client = updateKanji.JishoClient(
            delay=0,
            fetcher=lambda kanji: read_fixture(
                "jisho_hana.html" if kanji == "鼻" else "jisho_mizu.html"
            ),
        )
        lines = [client.lookup(k) for k in updateKanji.extract_kanji("鼻水")]
        self.assertEqual(
            updateKanji.build_notes_html(lines),
            "鼻 nose, snout Kun: はな On: ビ<br>水 water Kun: みず、 みず- On: スイ",
        )


class JishoClientCacheTest(unittest.TestCase):
    def test_lookup_is_cached(self):
        calls = []

        def fetcher(kanji):
            calls.append(kanji)
            return read_fixture("jisho_hana.html")

        client = updateKanji.JishoClient(delay=0, fetcher=fetcher)
        self.assertEqual(client.lookup("鼻"), client.lookup("鼻"))
        self.assertEqual(calls, ["鼻"])


if __name__ == "__main__":
    unittest.main()
