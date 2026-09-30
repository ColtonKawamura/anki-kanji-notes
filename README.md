# anki-kanji-notes

`updateKanji` is a small macOS command-line tool that fills empty **Notes**
fields in your Anki *Immersion* deck with kanji meanings and readings from
[Jisho.org](https://jisho.org).

For a card whose **Reading** field is `鼻水`, the **Notes** field becomes:

```
鼻 nose, snout Kun: はな On: ビ
水 water Kun: みず、 みず- On: スイ
```

It uses the Python 3 standard library only — no pip packages, no virtualenv.

## Prerequisites

- **macOS** (Windows is not supported).
- **Anki**, running while the tool works.
- The **AnkiConnect** add-on (add-on code `2055492159`).
  In Anki: *Tools → Add-ons → Get Add-ons…*, paste `2055492159`, then restart Anki.
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

With Anki open:

```sh
updateKanji
```

Every note in the deck whose Notes field is empty is looked up and updated:

```
Updated 鼻水
Updated 食べ物

Done. Updated: 2, skipped: 0, errors: 0
```

### Options

| Option | Default | Description |
| --- | --- | --- |
| `--deck DECK` | `Immersion` | Deck to scan. |
| `--reading-field FIELD` | `Reading` | Field that holds the Japanese word. |
| `--notes-field FIELD` | `Notes` | Field to fill in. |
| `--dry-run` | off | Print what would be written, change nothing. |
| `--limit N` | all | Only process the first N notes with an empty Notes field. |
| `--url URL` | `http://127.0.0.1:8765` | AnkiConnect endpoint. |

### Examples

```sh
# See what the first 5 cards would get, without touching Anki
updateKanji --dry-run --limit 5

# A different deck and note type
updateKanji --deck "Japanese::Mining" --reading-field Word --notes-field Meaning
```

## How it works

1. `findNotes` with `deck:<deck>` and `notesInfo` through AnkiConnect.
2. Notes whose Notes field is empty (ignoring whitespace and markup such as
   `<br>`, `&nbsp;` and `<div></div>`) are selected.
3. Each unique kanji in the Reading field is extracted, in order.
4. `https://jisho.org/search/<kanji>%20%23kanji` is fetched for each kanji
   (results are cached per run, with a short pause between requests).
5. The lines are joined with `<br>` and written back with `updateNoteFields`.

Notes without kanji, or where every Jisho lookup fails, are left untouched.

## Tests

The parsing logic is covered by tests that use saved Jisho HTML, so no network
or Anki instance is needed:

```sh
python3 -m unittest discover -s tests
```

## Troubleshooting

- **`Could not reach AnkiConnect`** — Anki is not running, or AnkiConnect is not
  installed/enabled. Restart Anki after installing the add-on.
- **`Note ... has no field 'Notes'`** — your note type uses different field
  names; pass `--reading-field` / `--notes-field`.
- **No notes found** — check the deck name, including `::` subdeck separators.
