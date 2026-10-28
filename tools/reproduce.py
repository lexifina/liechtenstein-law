"""Writes data/fassungen.json and REPRODUCE.md into the Liechtenstein law repository, from the facts of the build that
made it. Called by build.py; kept apart so the record of how the repository was made reads as one document.

The results of the checks (check_repo.py, and the rebuild that compares hashes) are read from verification.json next to
this file, which check_repo.py and `build.py --verify-rebuild` write. They describe the build before the one that writes
this file, from the same data; a rebuild with the same data and the same verification.json gives the same hashes."""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def write_manifest(repo: Path, built: list[dict], today: str):
    """Every source file the text comes from, with its sha256, so a rebuild can show it read the same bytes."""
    out = {'built': today, 'source': 'https://www.gesetze.li', 'acts': [{
        'lgbl': b['act']['lgbl'], 'lr': b['act']['lr'], 'slug': b['act']['slug'], 'title': b['title'],
        'versions': [{'version': v['version'], 'from': v['from'], 'to': v['to'], 'laws': v['laws'], 'html': v['url'],
                      'sha256': v['sha256']} for v in b['versions']],
    } for b in built]}
    (repo / 'data').mkdir(exist_ok=True)
    (repo / 'data' / 'fassungen.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')


def write_reproduce(repo: Path, built: list[dict], log: list[dict], tags: dict, requests: list[dict], today: str):
    blob = subprocess.run(['git', 'hash-object', str(HERE / 'build.py')], capture_output=True, text=True).stdout.strip()
    pyv = subprocess.run(['python', '--version'], capture_output=True, text=True).stdout.strip()
    gitv = subprocess.run(['git', '--version'], capture_output=True, text=True).stdout.strip()
    try:
        import lxml.etree
        lxmlv = '.'.join(str(x) for x in lxml.etree.LXML_VERSION[:3])
    except Exception:
        lxmlv = '?'
    ver = json.loads((HERE / 'verification.json').read_text(encoding='utf-8')) if (HERE / 'verification.json').exists() else {}
    files = {r['file'] for r in requests if r['file'].exists()}
    days = sorted({dt.date.fromtimestamp(f.stat().st_mtime).isoformat() for f in files})
    kinds = {'meta': 0, 'konso': 0, 'chrono': 0}
    for url in {r['url'] for r in requests}:
        kinds['meta' if url.endswith('/meta') else 'konso' if '/konso/html/' in url else 'chrono'] += 1
    n_law = sum(1 for c in log if c['kind'] == 'law')
    n_empty = sum(1 for c in log if c['kind'] == 'law' and not c['units'])
    n_unexp = sum(1 for c in log if c['kind'] == 'unexplained')
    n_start = sum(1 for c in log if c['kind'] == 'start')
    n_clamped = sum(1 for c in log if c['clamped'])
    unexplained_units = sum(len(b['problems']) for b in built)
    rows = '\n'.join(
        f'| {b["act"]["short"]} | LR {b["act"]["lr"]} | {b["title"]} | {len(b["versions"])} | '
        f'{b["versions"][0]["from"]} to {b["versions"][-1]["from"]} | {len(b["versions"][-1]["units"])} |' for b in built)
    retrieved = ', '.join(days) if days else today
    chk = ver.get('check', {})
    det = ver.get('rebuild', {})
    check_line = (f'`{chk["versions"]} versions checked ({chk["files"]} files), {chk["mismatches"]} mismatches; '
                  f'{chk["wordcheck"]} versions word for word against the whole official text, {chk["word_mismatches"]} mismatches`'
                  if chk else '(not yet run)')
    rebuild_line = (f'A second build from the same cache into an empty folder gave the same history: the last law commit '
                    f'was `{det["history_tip"]}` in both, and every one of the {det["commits"]} law commits and {det["tags"]} '
                    f'tags had the same hash.' if det.get('identical') else '(not yet run)')

    text = f"""# How this history was made, and how to make it again

This file records exactly how the repository was built: the sources, the commands, the software, the decisions made
by hand, and what an AI model did and did not do. The build writes it, so it describes the build that made this
commit.

## Short version

```sh
git clone https://github.com/lexifina/liechtenstein-law && cd liechtenstein-law
pip install lxml
python -X utf8 tools/build.py --repo ../rebuilt --today {today}
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
summarised or rewritten. The build read {kinds['meta']} act pages, {kinds['konso']} consolidated versions and
{kinds['chrono']} amending laws:

| What | Where |
| --- | --- |
| Each act's versions, with the days each applies from and to, and the chronology naming the LGBl numbers behind each version (with the issue day and the Government's reports, BuA) | `https://www.gesetze.li/konso/<id>/meta` |
| The text of each version, with its footnotes ("Art. 7 Abs. 2 abgeändert durch LGBl. 2003 Nr. 186.") | `https://www.gesetze.li/konso/html/<id>?version=<n>`, listed with sha256 in `data/fassungen.json` |
| The full title of each amending law (the chronology shortens long titles) | `https://www.gesetze.li/chrono/html/<id>`, the page's description |

| Act | LR | Title | Versions | In force from | Units today |
| --- | --- | --- | ---: | --- | ---: |
{rows}

The data was retrieved on {retrieved}, one request at a time with a pause of at least 1.5 seconds, with the user agent
`lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)`. Lilex has no robots.txt (the address answers
404) and no API; it sits behind a gateway that sets cookies, which the script keeps for the session.

## The build, step by step

1. `python -X utf8 scripts/liechtenstein-law/build.py --today {today}` in Lexifina's own repository fetched the data
   into its cache and wrote this repository. `tools/build.py` here is the same file as
   `scripts/liechtenstein-law/build.py` there (git blob `{blob}`), with `tools/reproduce.py`, which writes this file,
   and `tools/check_repo.py`.
2. `python -X utf8 scripts/liechtenstein-law/check_repo.py` read every version of every act back from this repository
   with `tools/stand_am.py`, on the day it took effect, and compared it file by file with the official text parsed
   afresh from the cached HTML; then it compared the whole act, word for word, with all the words of the official
   page (without its footnotes). Result: {check_line}.
3. `python -X utf8 scripts/liechtenstein-law/build.py --verify-rebuild` built the repository a second time from the
   same cache into a temporary folder and compared the hashes. {rebuild_line}
4. The build was run once more to write these results into this file, and the final `main` was rebuilt again in a
   temporary folder and compared hash for hash before it was pushed.
5. `gh repo create lexifina/liechtenstein-law --private` and `git push -u origin main --tags` published it to GitHub,
   private.

It ran with {pyv}, lxml {lxmlv} and {gitv} on Windows 11. No network service other than Lilex is involved.

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
- **Changes.** Consecutive versions are compared file by file. {sum(c['units'] for c in log if c['kind'] != 'start')}
  changes of a file were found.
- **Cause.** Lilex lists, for each version, the LGBl numbers that produced it. A changed file is credited to the one of
  those laws that its footnotes name. Four further rules, each written in the code: the excerpt of an amending law is
  that law's text; an article number that disappears goes with the law whose footnote names the old number, or whose
  new range of articles covers it; part headings that only moved to a neighbouring article go with the law that
  changed that article; and the heading above the excerpts goes with the law whose excerpt first appears under it.
  {unexplained_units} file changes are explained by none of these, and are never credited to a law (below).
- **Date.** The day the version applies from in Lilex, which for the version an amending law produced is the day the
  law took effect.
- **Commits.** One commit per act, per day and per amending law ({n_law} law commits, of which {n_empty} change no
  words), one for the first version of each act ({n_start}), and one per act and day for the changes no footnote
  explains ({n_unexp}), in the order they took effect, then one for this documentation.
  - The author is the amending law, `LGBl. 2003 Nr. 186`, at an address ending `@gesetze-li.invalid`. The first version
    of an act is credited to the act itself when Lilex's first version is the act as enacted (LV, VRG); otherwise
    (StGHG) to `Rechtsdienst der Regierung (Lilex)`, and its message lists the laws Lilex names for the text before it.
  - Unexplained changes are by `Rechtsdienst der Regierung (Lilex)` and say "Änderung ohne Nachweis" in the subject.
  - Author and committer dates are noon in Vaduz on the day the change took effect. The committer is
    `Lexifina <liechtenstein-law@lexifina.com>`. Git cannot store a date before 1970: the {n_clamped} commits for
    changes in force before then are dated 1 January 1970 (UTC), one second apart in order, and their real day is in
    the `In-force:` trailer, which `tools/stand_am.py` reads.
  - The message has the law's full title, the provisions it inserted, amended or repealed, and the trailers `Dated:`
    (the day in the law's title), `Published:` (the day the LGBl was issued), `In-force:`, `Affecting:`, `Materials:`
    (the Government's reports to the Landtag, BuA), `Source:` and `Consolidated:` (the exact page the text came from).
  - Tags: each act's days (`lv/2003-09-15`) and each amending law (`lgbl/2003-186`).
- **Documentation commit.** Dated {today}, the day the data was retrieved, not the day of the run, so a later rebuild
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

This repository was built on {today} in **Claude Code**, Anthropic's coding tool, by the model **Claude Opus 5.5**
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
"""
    (repo / 'REPRODUCE.md').write_text(text, encoding='utf-8', newline='\n')
