# Tools

The scripts behind this Liechtenstein-only run of global-law's vulnerability detectors. They run inside a copy of
[global-law/vulnerabilities/scripts](https://github.com/lexifina/global-law/tree/main/vulnerabilities/scripts) (Python 3.11+,
`pip install duckdb pyarrow`), with a bare clone of this repository at `sources/corpus/liechtenstein-law.git`, a blobless
bare clone of global-law at `sources/global-law.git`, and a `pins.json` that names only liechtenstein-law, its commit and
its language (`de`). `build_vulns.py`, `flags_chart.py`, `late_ext_select.py`, `late_ext_rebut.py` and `config.json` sit
three folders up, next to the copy of global-law (`gl/vulnerabilities/scripts/`).

| Script | What it does |
| --- | --- |
| `run.sh` | Indexes the history and texts, adds this repository's history rows, and runs the detectors (`bash run.sh <shards>`) |
| `add_root.py` | Builds the history rows from this repository's own commits (global-law replays it only up to an earlier commit), so the history detectors read every change |
| `run_triage.sh` | The model review: the 40 strongest flags per category, the 40 strongest lapsed time limits in law texts, and the empty periods |
| `late_ext_select.py` | Chooses the empty periods for global-law's review of that category (there were none here) |
| `late_ext_rebut.py` | Adds the second, arguing-against pass to the empty-period review, as `triage.py` does for the other categories |
| `build_vulns.py` | Builds `data/flags.csv`, `data/reviewed.csv` and `data/by_category.csv` from the findings and the model review |
| `flags_chart.py` | Draws the chart at the top of the READMEs, in German and English, light and dark |
| `config.json` | The repository, the German category names, the files and folders that are not law, and the chart's labels |
| `apply_patches.py` | Applies the patches below to the copy of global-law's scripts, each once and in a fixed order, `patch_li.py` last, and records each one in `.kit_patches.json` (`python -X utf8 apply_patches.py <scripts dir>`) |
| `patch_detectors.py` | Fixes blind spots found in runs on several country repositories (`python -X utf8 patch_detectors.py <scripts dir>`; a fix already in place is skipped) |
| `patch_detectors_vi.py` | The same for Vietnamese dates, references and amounts; it changes nothing here, but `redo.py` runs it on every repository |
| `patch_es.py`, `patch_ca.py`, `patch_pt.py`, `patch_en.py`, `patch_en_et.py`, `patch_co.py`, `patch_sv.py` | The same for Spanish, Catalan, Portuguese, English, Ethiopian English, Colombian Spanish and Swedish texts; they change nothing here |
| `patch_de.py` | The German fixes made for the Austrian run: "Jänner" and "Feber", "bis zum Ablauf des", another act named after a section or article, the RIS's notes and corrections, and the schilling |
| `patch_li.py` | The Liechtenstein fixes below |
| `map_moved.py` | For a repository that moved its act folders (`data/paths.json`), rewrites the paths in the history table to each act's folder since the move; this repository has not moved its folders, so it does nothing here |
| `redo.py` | Runs the patches through `apply_patches.py`, then again only the scans and detectors the fixes change, the model review of lapsed time limits, references to deleted provisions and empty periods, and the build (`python -X utf8 redo.py <run folder> [--keep-reviews] [--full]`; `--keep-reviews` keeps every review already made and reviews only new strong flags; `--full` runs every step again through `run.sh`, sends every category to the model and keeps every review already made; `EMBED_FONTS` names the script that embeds the chart's fonts) |
| `lilex_text.py` | Hand-check helper: a consolidated text from Lilex (www.gesetze.li) as plain text, cached, with the matches of a pattern; its footnotes name the act that repealed or changed each provision (`python -X utf8 lilex_text.py <Lilex id> <version or current> <regex>`) |

The model review needs `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` and `LLM_AUTH` set for an OpenAI-compatible Responses API.
It was run as `bash run_triage.sh '^(data|tools|vulnerabilities)/|/README[.]md$'`; no lapsed time limit is in those
files, so the 40 strongest lapsed time limits in law texts are the 40 strongest of all.

Changes made for this repository:

- `add_root.py` counts an act's first text marked `Kind: start` (500 acts, credited to the law Lilex names for that
  version) as a first copy, like `Kind: baseline` (3,186 acts, mostly credited to Lilex). Without it, the reference
  scan and the ranking of lapsed time limits (by each file's last change), which read only history rows of kind `law` or
  `baseline`, would have left those 500 acts out or without a date. The 99 changes to
  the Constitution, the VRG and the StGHG carry no `Kind:` and count as law; the 4 `Kind: documentation` commits do not.
- `config.json` also lists `README.md` under `not_law_files`: each act's folder has one, a description written by
  Lexifina, not law.
- `patch_li.py`, applied last, after `patch_de.py`; every change in it has a marker comment (`FRANKEN_DE`,
  `SCHILLING_S_DE`, `LI_BST`, `LI_EU_ACT`, `LI_ENABLING`), so a second run sees it in place. All apply only where
  `pins.json` gives the language as `de`:
  - Dead currencies: "Franken" counted as a dead franc, because a fix for Czech and Dutch ("frank") matched the German
    word too, and "1'000 Franken" in German is the Swiss franc, legal tender in Liechtenstein: 2,192 flags in this
    repository. A German text now flags only a franc named as Belgian, French or Luxembourg. `patch_de.py`'s schilling
    "S" after an amount also matched codes and symbols ("NO88S", "S00S", "12S", "BISD 27S/24", "S-300", "S.E.") and
    "Schilling" the end of "Jagdpachtschilling" (a hunting lease); "S" now needs a space after the amount and no "-",
    "/" or ".X" after it, and "Schilling" must be a word of its own. Dead currencies went from 2,259 to 67 and then to 12.
  - References: Liechtenstein (and Swiss) law writes "Bst." (Buchstabe) where Austria writes "lit.", so "Art. 2 Abs. 2
    Bst. d des Grundverkehrsgesetzes" and "Art. 6 Abs. 1 Bst. e des Gesetzes" (an ordinance citing its parent act) were
    read as references to the citing act; "Bst." now counts like "lit.". An EU regulation or directive named after the
    number ("Art. 4 Abs. 1 Ziff. 21 der Richtlinie 2014/65/EU", "Art. 6 Bst. a der Delegierten Verordnung (EU)
    2017/1943") is another act. An ordinance's enabling clause ("Aufgrund von Art. 2 Abs. 1, ..., Art. 25 Abs. 3 ... des
    Asylgesetzes ... verordnet die Regierung:") is skipped. References to repealed placeholders went from 53 to 35. These
    fixes were made after the reference scan; only the two detectors that read references themselves
    (`placeholder_ref.py` and `dead_fine.py`) were run again. The reference scan's own output, read by the search for
    references to deleted provisions, can only lose references through them, and that search found none before them.
- `run.sh` ran with 6 shards; the reference scan took 32 minutes, as it reads every one of the 3,689 act folders.
