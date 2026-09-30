"""Tests for reading/writing an Anki collection file directly (no Anki needed)."""

import contextlib
import io
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

from test_parse import read_fixture, updateKanji

READING_NTID = 1000
DECK_IMMERSION = 1
DECK_SUB = 2
DECK_OTHER = 3


def _unicase(a, b):
    a, b = a.casefold(), b.casefold()
    return (a > b) - (a < b)


def make_collection(path):
    """Create a tiny collection using Anki's modern (schema 18) layout."""
    db = sqlite3.connect(path)
    db.create_collation("unicase", _unicase)
    db.executescript(
        """
        CREATE TABLE col (id integer primary key, crt integer, mod integer, scm integer,
            ver integer, dty integer, usn integer, ls integer, conf text, models text,
            decks text, dconf text, tags text);
        CREATE TABLE notes (id integer primary key, guid text, mid integer, mod integer,
            usn integer, tags text, flds text, sfld integer, csum integer, flags integer,
            data text);
        CREATE TABLE cards (id integer primary key, nid integer, did integer, ord integer,
            mod integer, usn integer, type integer, queue integer, due integer,
            ivl integer, factor integer, reps integer, lapses integer, left integer,
            odue integer, odid integer, flags integer, data text);
        CREATE TABLE decks (id integer primary key not null, name text not null collate unicase,
            mtime_secs integer, usn integer, common blob, kind blob);
        CREATE TABLE notetypes (id integer primary key not null, name text not null collate unicase,
            mtime_secs integer, usn integer, config blob);
        CREATE TABLE fields (ntid integer, ord integer, name text not null collate unicase,
            config blob, primary key (ntid, ord)) without rowid;
        CREATE UNIQUE INDEX idx_decks_name ON decks (name);
        """
    )
    db.execute("INSERT INTO col (id, mod) VALUES (1, 5)")
    for did, name in [(DECK_IMMERSION, "Immersion"), (DECK_SUB, "Immersion\x1fAnime"),
                      (DECK_OTHER, "Other")]:
        db.execute("INSERT INTO decks (id, name) VALUES (?, ?)", (did, name))
    # sort_field_idx (protobuf field 2) = 1 -> the Reading field
    db.execute("INSERT INTO notetypes (id, name, config) VALUES (?, 'Japanese', ?)",
               (READING_NTID, b"\x08\x00\x10\x01\x1a\x03css"))
    for ord_, name in enumerate(["Word", "Reading", "Notes"]):
        db.execute("INSERT INTO fields VALUES (?, ?, ?, x'')", (READING_NTID, ord_, name))
    notes = [
        (10, DECK_IMMERSION, ["w1", "鼻水", ""]),
        (11, DECK_SUB, ["w2", "水", "<br>"]),
        (12, DECK_IMMERSION, ["w3", "みず", ""]),
        (13, DECK_IMMERSION, ["w4", "水", "already filled"]),
        (14, DECK_OTHER, ["w5", "水", ""]),
    ]
    for nid, did, values in notes:
        db.execute(
            "INSERT INTO notes (id, mid, mod, usn, flds, sfld) VALUES (?, ?, 1, 3, ?, ?)",
            (nid, READING_NTID, "\x1f".join(values), values[1]),
        )
        db.execute("INSERT INTO cards (id, nid, did, odid) VALUES (?, ?, ?, 0)",
                   (nid * 10, nid, did))
    db.commit()
    db.close()


def fake_fetch(kanji):
    return read_fixture({"鼻": "jisho_hana.html", "水": "jisho_mizu.html"}[kanji])


class CollectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "collection.anki2")
        make_collection(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def notes_row(self, nid):
        db = sqlite3.connect(self.path)
        try:
            return db.execute("SELECT flds, usn, mod FROM notes WHERE id = ?", (nid,)).fetchone()
        finally:
            db.close()

    def test_find_notes_includes_subdecks_only(self):
        col = updateKanji.AnkiCollection(self.path)
        try:
            notes = col.find_notes("immersion")
        finally:
            col.close()
        self.assertEqual([n["noteId"] for n in notes], [10, 11, 12, 13])
        self.assertEqual(notes[0]["fields"]["Reading"], "鼻水")
        self.assertEqual(notes[0]["sortIdx"], 1)

    def test_unknown_deck(self):
        col = updateKanji.AnkiCollection(self.path)
        try:
            self.assertEqual(col.find_notes("Nope"), [])
        finally:
            col.close()

    def test_locked_collection(self):
        holder = sqlite3.connect(self.path, isolation_level=None)
        holder.execute("PRAGMA locking_mode = EXCLUSIVE")
        holder.execute("BEGIN EXCLUSIVE")
        try:
            with self.assertRaises(updateKanji.AnkiError) as ctx:
                updateKanji.AnkiCollection(self.path)
            self.assertIn("Quit Anki", str(ctx.exception))
        finally:
            holder.execute("ROLLBACK")
            holder.close()

    def test_collection_locked_while_open(self):
        col = updateKanji.AnkiCollection(self.path)
        try:
            other = sqlite3.connect(self.path, timeout=0.1)
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    other.execute("SELECT count(*) FROM notes").fetchone()
            finally:
                other.close()
        finally:
            col.close()
        db = sqlite3.connect(self.path)
        try:
            self.assertEqual(db.execute("SELECT count(*) FROM notes").fetchone()[0], 5)
        finally:
            db.close()

    def test_damaged_collection_is_refused(self):
        db = sqlite3.connect(self.path)
        page_size = db.execute("PRAGMA page_size").fetchone()[0]
        root = db.execute(
            "SELECT rootpage FROM sqlite_master WHERE name = 'notes'").fetchone()[0]
        db.close()
        with open(self.path, "r+b") as f:
            f.seek((root - 1) * page_size)
            f.write(b"\xff" * 64)
        with self.assertRaises(updateKanji.AnkiCorruptError) as ctx:
            updateKanji.AnkiCollection(self.path)
        self.assertIn("Check Database", str(ctx.exception))
        code, _ = self.run_main()
        self.assertEqual(code, 1)
        self.assertEqual([n for n in os.listdir(self.tmp.name) if n.endswith(".bak")], [])

    def test_corrupt_write_stops_run(self):
        calls = []

        def broken_update(col, note, field, value):
            calls.append(note["noteId"])
            raise updateKanji.AnkiCorruptError("database disk image is malformed")

        with mock.patch.object(updateKanji.AnkiCollection, "update_field", broken_update):
            code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertEqual(calls, [10])
        self.assertNotIn("Done.", out)

    def run_main(self, *extra):
        out = io.StringIO()
        real_client = updateKanji.JishoClient
        client = lambda: real_client(delay=0, fetcher=fake_fetch)
        with mock.patch.object(updateKanji, "JishoClient", client), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = updateKanji.main(["--collection", self.path] + list(extra))
        return code, out.getvalue()

    def test_dry_run_changes_nothing(self):
        before = self.notes_row(10)
        code, out = self.run_main("--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("Would update 鼻水", out)
        self.assertEqual(self.notes_row(10), before)
        self.assertEqual(os.listdir(self.tmp.name), ["collection.anki2"])

    def test_updates_empty_notes(self):
        code, out = self.run_main()
        self.assertEqual(code, 0)
        flds, usn, mod = self.notes_row(10)
        self.assertEqual(
            flds.split("\x1f"),
            ["w1", "鼻水", "鼻 nose, snout Kun: はな On: ビ<br>"
             "水 water Kun: みず、 みず- On: スイ"],
        )
        self.assertEqual(usn, -1)
        self.assertGreater(mod, 1)
        self.assertEqual(self.notes_row(11)[0].split("\x1f")[2],
                         "水 water Kun: みず、 みず- On: スイ")
        self.assertEqual(self.notes_row(12)[0].split("\x1f")[2], "")
        self.assertEqual(self.notes_row(13)[0].split("\x1f")[2], "already filled")
        self.assertEqual(self.notes_row(14)[0].split("\x1f")[2], "")
        self.assertIn("Updated: 2, skipped: 1", out)

        db = sqlite3.connect(self.path)
        try:
            self.assertGreater(db.execute("SELECT mod FROM col").fetchone()[0], 5)
        finally:
            db.close()
        backups = [n for n in os.listdir(self.tmp.name) if n.endswith(".bak")]
        self.assertEqual(len(backups), 1)

    def test_missing_field(self):
        code, _ = self.run_main("--notes-field", "Meaning")
        self.assertEqual(code, 1)


class FindCollectionTest(unittest.TestCase):
    def test_single_and_multiple_profiles(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(updateKanji.AnkiError):
                updateKanji.find_collection(anki_dir=root)
            os.makedirs(os.path.join(root, "User 1"))
            open(os.path.join(root, "User 1", "collection.anki2"), "w").close()
            os.makedirs(os.path.join(root, "addons21"))
            self.assertEqual(updateKanji.find_collection(anki_dir=root),
                             os.path.join(root, "User 1", "collection.anki2"))
            os.makedirs(os.path.join(root, "Work"))
            open(os.path.join(root, "Work", "collection.anki2"), "w").close()
            with self.assertRaises(updateKanji.AnkiError):
                updateKanji.find_collection(anki_dir=root)
            self.assertEqual(updateKanji.find_collection("Work", anki_dir=root),
                             os.path.join(root, "Work", "collection.anki2"))


class ProtobufTest(unittest.TestCase):
    def test_sort_field(self):
        self.assertEqual(updateKanji.protobuf_uint_field(b"\x08\x01\x10\x02", 2), 2)
        self.assertEqual(updateKanji.protobuf_uint_field(b"\x1a\x02ab", 2), 0)
        self.assertEqual(updateKanji.protobuf_uint_field(b"", 2), 0)


if __name__ == "__main__":
    unittest.main()
