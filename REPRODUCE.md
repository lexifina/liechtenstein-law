# How this history was made, and how to make it again

This file records exactly how the repository was built: the sources, the commands, the software, the decisions made
by hand, and what an AI model did and did not do. The build writes it, so it describes the build that made this
commit.

## Short version

```sh
git clone https://github.com/lexifina/liechtenstein-law && cd liechtenstein-law
pip install lxml
python -X utf8 tools/build.py --repo ../rebuilt --today 2026-10-28
git -C ../rebuilt rev-parse main        # the same hash as this repository's main
python -X utf8 tools/check_repo.py --repo ../rebuilt
```

`tools/build.py` needs Python 3.12 or later with `lxml`, and git. It reads Lilex (or its own cache, `.cache/` next to
the script) and writes this repository into `--repo`. With the same Lilex data and the same `--today` it gives the same
commits with the same hashes. `data/fassungen.json` lists every consolidated version it read with the sha256 of the HTML,
so a rebuild can show it read the same bytes; Lilex may change its pages, and then the hashes change too.

## Sources

All legal text and all information about versions and amending laws come from **Lilex** (www.gesetze.li), the law
database of the Liechtenstein Government's Legal Service (Rechtsdienst der Regierung, RDR). Nothing was typed in,
summarised or rewritten. The build read 3 act pages, 69 consolidated versions and
76 amending laws:

| What | Where |
| --- | --- |
| Each act's versions, with the days each applies from and to, and the chronology naming the LGBl numbers behind each version (with the issue day and the Government's reports, BuA) | `https://www.gesetze.li/konso/<id>/meta` |
| The text of each version, with its footnotes ("Art. 7 Abs. 2 abgeändert durch LGBl. 2003 Nr. 186.") | `https://www.gesetze.li/konso/html/<id>?version=<n>`, listed with sha256 in `data/fassungen.json` |
| The full title of each amending law (the chronology shortens long titles) | `https://www.gesetze.li/chrono/html/<id>`, the page's description |

| Act | LR | Title | Versions | In force from | Units today |
| --- | --- | --- | ---: | --- | ---: |
| LV | LR 101 | Verfassung des Fürstentums Liechtenstein vom 5. Oktober 1921 | 41 | 1921-10-24 to 2026-01-01 | 126 |
| VRG | LR 161 | Gesetz vom 17. Juli 1973 betreffend die Ausübung der politischen Volksrechte in Landesangelegenheiten | 19 | 1973-11-23 to 2012-12-01 | 114 |
| StGHG | LR 173.10 | Gesetz vom 27. November 2003 über den Staatsgerichtshof (StGHG) | 9 | 2009-11-03 to 2026-01-01 | 74 |

The data was retrieved on 2026-10-28, one request at a time with a pause of at least 1.5 seconds, with the user agent
`lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)`. Lilex has no robots.txt (the address answers
404) and no API; it sits behind a gateway that sets cookies, which the script keeps for the session.

## The build, step by step

1. `python -X utf8 scripts/liechtenstein-law/build.py --today 2026-10-28` in Lexifina's own repository fetched the data
   into its cache and wrote this repository. `tools/build.py` here is the same file as
   `scripts/liechtenstein-law/build.py` there (git blob `e44498a2d306a2f7812b952afb9e641fd8c3a2e6`), with `tools/reproduce.py`, which writes this file,
   and `tools/check_repo.py`.
2. `python -X utf8 scripts/liechtenstein-law/check_repo.py` read every version of every act back from this repository
   with `tools/stand_am.py`, on the day it took effect, and compared it file by file with the official text parsed
   afresh from the cached HTML; then it compared the whole act, word for word, with all the words of the official
   page (without its footnotes). Result: `69 versions checked (7628 files), 0 mismatches; 69 versions word for word against the whole official text, 0 mismatches`.
3. `python -X utf8 scripts/liechtenstein-law/build.py --verify-rebuild` built the repository a second time from the
   same cache into a temporary folder and compared the hashes. A second build from the same cache into an empty folder gave the same history: the last law commit was `d4f511d6adadae5f38c1168ea86b69eb2c2096f4` in both, and every one of the 99 law commits and 143 tags had the same hash.
4. The build was run once more to write these results into this file, and the final `main` was rebuilt again in a
   temporary folder and compared hash for hash before it was pushed.
5. `gh repo create lexifina/liechtenstein-law --private` and `git push -u origin main --tags` published it to GitHub,
   private.

It ran with Python 3.12.10, lxml 6.1.3 and git version 2.46.0.windows.1 on Windows 11. No network service other than Lilex is involved.

## How the text and the commits are derived

Everything below is done by `tools/build.py`, deterministically.

- **Text.** Each act is a folder (`lv/`, `vrg/`, `stghg/`). Each article is one file, `art-001.md`, `art-013bis.md`
  (a range of repealed articles printed as one, "Art. 8c bis 8e", is one file `art-008c-bis-8e.md`). The headings of
  the parts that begin with an article are `##` lines at the top of its file; the article number and its subject
  heading are the `#` line; each paragraph (Absatz) and each list item is one line. `ingress.md` holds the title and
  the enacting words, `schluss.md` the signatures and closing words, and `uebergang/` the transitional and commencement
  provisions of amending laws that Lilex prints after the act, one file per law (`uebergang/2025-015.md`). Repealed
  articles stay in the text as Lilex prints them ("Aufgehoben").
- **Left out.** The footnotes, which the build reads separately, and the Landesgesetzblatt banner at the top of the act
  and of each excerpt (year, number, issue day), which are in the file names and trailers.
- **Normalised.** Only the space next to a footnote marker. Lilex's HTML has "Landesangehörigen⁵ Eintrag" in one
  version and "Landesangehörigen⁵Eintrag" in another, and sets a comma between two markers; a marker counts as a word
  space between two words and as nothing before punctuation or at either end. Every other character is kept, so
  Lilex's own corrections of spelling and punctuation are changes in the record.
- **Changes.** Consecutive versions are compared file by file. 323
  changes of a file were found.
- **Cause.** Lilex lists, for each version, the LGBl numbers that produced it. A changed file is credited to the one of
  those laws that its footnotes name. Four further rules, each written in the code: the excerpt of an amending law is
  that law's text; an article number that disappears goes with the law whose footnote names the old number, or whose
  new range of articles covers it; part headings that only moved to a neighbouring article go with the law that
  changed that article; and the heading above the excerpts goes with the law whose excerpt first appears under it.
  55 file changes are explained by none of these, and are never credited to a law (below).
- **Date.** The day the version applies from in Lilex, which for the version an amending law produced is the day the
  law took effect.
- **Commits.** One commit per act, per day and per amending law (72 law commits, of which 2 change no
  words), one for the first version of each act (3), and one per act and day for the changes no footnote
  explains (24), in the order they took effect, then one for this documentation.
  - The author is the amending law, `LGBl. 2003 Nr. 186`, at an address ending `@gesetze-li.invalid`. The first version
    of an act is credited to the act itself when Lilex's first version is the act as enacted (LV, VRG); otherwise
    (StGHG) to `Rechtsdienst der Regierung (Lilex)`, and its message lists the laws Lilex names for the text before it.
  - Unexplained changes are by `Rechtsdienst der Regierung (Lilex)` and say "Änderung ohne Nachweis" in the subject.
  - Author and committer dates are noon in Vaduz on the day the change took effect. The committer is
    `Lexifina <liechtenstein-law@lexifina.com>`. Git cannot store a date before 1970: the 17 commits for
    changes in force before then are dated 1 January 1970 (UTC), one second apart in order, and their real day is in
    the `In-force:` trailer, which `tools/stand_am.py` reads.
  - The message has the law's full title, the provisions it inserted, amended or repealed, and the trailers `Dated:`
    (the day in the law's title), `Published:` (the day the LGBl was issued), `In-force:`, `Affecting:`, `Materials:`
    (the Government's reports to the Landtag, BuA), `Source:` and `Consolidated:` (the exact page the text came from).
  - Tags: each act's days (`lv/2003-09-15`) and each amending law (`lgbl/2003-186`).
- **Documentation commit.** Dated 2026-10-28, the day the data was retrieved, not the day of the run, so a later rebuild
  of the same data gives the same hash.

## Decisions made by hand

These choices were made when the tool was written, after looking at the data. They are in the code.

1. **The acts.** The Constitution (LV, LR 101), because Lilex has every version since 1921 and it is the act readers
   ask about first; the People's Rights Act (VRG, LR 161), because it is amended often and Lilex has every version
   since its enactment in 1973, with clean footnotes; and the Constitutional Court Act (StGHG, LR 173.10), because it
   is amended with the Constitution (the 2018 and 2024 reforms) and shows how an act is recorded when Lilex lacks its
   earliest versions.
2. **Lilex's version days are the in-force days.** Lilex gives one day per version and names the laws behind it; the
   laws' own commencement clauses were not parsed.
3. **A change no footnote explains is never credited to a law**, even when only one law produced that version: it is
   committed separately by the Legal Service and labelled. Most are Lilex's own corrections of spelling, punctuation
   and spacing, and some reverse an earlier one.
4. **Two laws on one provision on one day.** Where the footnotes name two laws of the same version for one provision,
   the consolidated text cannot separate their changes; the change is committed with the later law (by LGBl number)
   and the commit names the other in `Also-amended-by:`.
5. **Source anomalies are kept, not corrected.** LGBl. 1978 Nr. 3 (a law of 24 November 1977) is shown by Lilex, and in
   the printed gazette's own header, as issued and in force on 11 January 1977. The commit keeps that day and says so
   in a `Date-note:` trailer.
6. **The text before the record is not guessed.** Lilex has no text of the StGHG before 3 November 2009. The first
   commit is that version, labelled as such and credited to no law.
7. **German only.** German is the only official language of Liechtenstein.

## What an AI model did

This repository was built on 2026-10-28 in **Claude Code**, Anthropic's coding tool, by the model **Claude Opus 5.5**
(model id `claude-opus-5-5`), working from a brief by the user at Lexifina: a private "git for law" repository for
Liechtenstein to the same standard as Lexifina's other corpora (the US Code, the Grundgesetz, UK and Swiss law).

The model:

- **Researched the source:** Lilex's pages, the shape of its HTML, its terms, and the Liechtenstein parser of
  legalize-dev (below).
- **Wrote all the code and text in this repository:** `tools/build.py`, `tools/reproduce.py`, `tools/check_repo.py`,
  `tools/stand_am.py`, the README, this file and the licence, and chose the design described in them.
- **Ran the commands above** and checked the results.

The model did **not**:

- **Write or edit any legal text.** Every word of every provision, every date and every law's title is copied by the
  script from Lilex.
- **Take part in building the history.** No AI model is called when the history is built or checked.

The user decided what was in scope and decides whether the repository is ever made public. The work was not reviewed
line by line by a lawyer. Lilex itself says that consolidated texts are for information only and have no legal effect;
only the Landesgesetzblatt is authoritative.

## Prior art

- [legalize-dev/legalize-pipeline](https://github.com/legalize-dev/legalize-pipeline), `src/legalize/fetcher/li/`:
  a Lilex scraper. From it we took three facts about the site, checked against it: the addresses of the version pages
  (`/konso/html/<id>?version=<n>`), that the gateway sets cookies and turns parallel requests into a redirect loop (so
  this build makes one request at a time), and that the shortened titles are complete in the page description. No code
  was copied.
- [legalize-dev/legalize-li](https://github.com/legalize-dev/legalize-li): about 3,500 Liechtenstein acts, one commit
  per consolidated version, credited to a generic author. This repository instead makes each commit one amending law,
  named from the footnotes, and keeps Lilex's own corrections apart.
- Lexifina's other corpora, whose rules this one follows: Swiss federal law (lexifina/swiss-law), the Grundgesetz, UK
  legislation and the US Code.
