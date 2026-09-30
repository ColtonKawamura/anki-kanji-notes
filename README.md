# anki-kanji-notes

`updateKanji` is a small macOS command-line tool that fills empty **Notes**
fields in your Anki *Immersion* deck with kanji meanings and readings from
[Jisho.org](https://jisho.org).

For a card whose **Reading** field is `鼻水`, the **Notes** field becomes:

```
鼻 nose, snout Kun: はな On: ビ
水 water Kun: みず、 みず- On: スイ
```

It uses the Python 3 standard library only — no pip packages, no virtualenv,
and no Anki add-ons. It edits your Anki collection file directly.

## Prerequisites

- **macOS** (Windows is not supported).
- **Anki**, which must be **closed** while the tool works. No add-ons are needed.
- **Python 3**, which ships with the Xcode Command Line Tools
  (`xcode-select --install`) or can be installed with Homebrew (`brew install python`).

## Install

```sh
git clone https://github.com/ColtonKawamura/anki-kanji-notes.git
cd anki-kanji-notes
./install.sh
```

`install.sh` marks the script executable and symlinks it into `/usr/local/bin`,
falling back to `~/.local/bin` when `/usr/local/bin` is not writable. If that
directory is not on your `PATH`, the installer prints the `~/.zshrc` line to add.

You can also run the script directly without installing:

```sh
./updateKanji --dry-run
```

## Usage

Quit Anki, then run:

```sh
updateKanji
```

Every note in the deck (and its subdecks) whose Notes field is empty is looked
up and updated:

```
Backed up collection to .../collection.anki2.20260930-120000.bak
Updated 鼻水
Updated 食べ物

Done. Updated: 2, skipped: 0, errors: 0
```

Open Anki again afterwards; the changes sync like any other edit.

### Options

| Option | Default | Description |
| --- | --- | --- |
| `--deck DECK` | `Immersion` | Deck to scan. |
| `--reading-field FIELD` | `Reading` | Field that holds the Japanese word. |
| `--notes-field FIELD` | `Notes` | Field to fill in. |
| `--dry-run` | off | Print what would be written, change nothing. |
| `--limit N` | all | Only process the first N notes with an empty Notes field. |
| `--profile NAME` | the only profile | Anki profile folder in `~/Library/Application Support/Anki2`. Required if you have several profiles. |
| `--collection PATH` | — | Path to a `collection.anki2` file (overrides `--profile`). |

### Examples

```sh
# See what the first 5 cards would get, without touching Anki
updateKanji --dry-run --limit 5

# A different deck and note type
updateKanji --deck "Japanese::Mining" --reading-field Word --notes-field Meaning
```

## How it works

1. The profile's `collection.anki2` (an SQLite database) is opened with Python's
   built-in `sqlite3`, and the notes that have cards in the deck or its
   subdecks are read.
2. Notes whose Notes field is empty (ignoring whitespace and markup such as
   `<br>`, `&nbsp;` and `<div></div>`) are selected.
3. Each unique kanji in the Reading field is extracted, in order.
4. `https://jisho.org/search/<kanji>%20%23kanji` is fetched for each kanji
   (results are cached per run, with a short pause between requests).
5. Before the first write, the collection is backed up next to itself as
   `collection.anki2.<timestamp>.bak`.
6. The lines are joined with `<br>` and written into the note. The note and the
   collection are marked as modified so the change syncs to AnkiWeb.

Notes without kanji, or where every Jisho lookup fails, are left untouched.

## Tests

The tests use saved Jisho HTML and a small throwaway collection file, so no
network or Anki install is needed:

```sh
python3 -m unittest discover -s tests
```

## Troubleshooting

- **`The Anki collection is in use`** — Anki is still open. Quit it fully
  (⌘Q) and run the tool again.
- **`Several Anki profiles found`** — pass `--profile "User 1"` (the folder
  name under `~/Library/Application Support/Anki2`).
- **Undo** — quit Anki and replace `collection.anki2` with the `.bak` file the
  tool printed (rename it back to `collection.anki2`).
- **`Note ... has no field 'Notes'`** — your note type uses different field
  names; pass `--reading-field` / `--notes-field`.
- **No notes found** — check the deck name, including `::` subdeck separators.
