# Liechtenstein law: current texts and selected histories

[Deutsch](README.md) · **English**

<picture>
<source media="(prefers-color-scheme: dark)" srcset="data/effort-dark.svg">
<img alt="Liechtenstein law in this repository: what it holds, changes by the year they took effect, completeness against the official sources, and the correctness of what is held" src="data/effort-light.svg" width="880">
</picture>

Part of [lexifina/global-law](https://github.com/lexifina/global-law), one git history for every country's law: this is Liechtenstein's national law, which global-law reads at `liechtenstein/national/acts/`.

Selected full histories of three acts of the Principality of Liechtenstein: the Constitution (Verfassung, LV, LR 101), the
People's Rights Act (Volksrechtegesetz, VRG, LR 161) and the Constitutional Court Act (Staatsgerichtshofgesetz, StGHG,
LR 173.10). Each amending law is one commit, credited to that law and dated the day it took effect, at noon in Vaduz.
The text is the consolidated text published by the Government's Legal Service in [Lilex](https://www.gesetze.li).

## The questions, as git commands

| Question | Command |
| --- | --- |
| What did Art. 7 of the Constitution say on 1 January 2000? | `python tools/stand_am.py 2000-01-01 lv 7` |
| The whole Constitution as it stood in 1950 | `python tools/stand_am.py 1950-01-01 lv` |
| Which law wrote each paragraph of Art. 7? | `git blame lv/art-007.md` |
| Every change to Art. 7, with the law and the day | `git log -p lv/art-007.md` |
| Everything one law changed | `git show lgbl/2003-186` |
| What changed in the VRG on one day | `git show vrg/2004-11-12` |
| The amending laws with all their dates | [`erlasse.csv`](erlasse.csv) |
| Changes no footnote explains | `git log --grep="Änderung ohne Nachweis"` |
| Laws that touched several acts | `git log --author="LGBl. 2025"` |

## The dates, and which one we use

A Liechtenstein law has a date in its title (`Dated:`, "Verfassungsgesetz vom 8. November 2024"), the day the
Landesgesetzblatt that publishes it is issued (`Published:`), and the day it takes effect (`In-force:`). **Commits are
dated the day the change took effect**, at noon in Vaduz: that is the day that decides which text applies. It is the
day Lilex gives as the start of the version the law produced. All three dates are in every commit message.

Git cannot store a date before 1970. The commits for the Constitution's changes from 1921 to 1965 are dated
1 January 1970 (UTC), a second apart in order, and their real day is in the `In-force:` trailer, which
`tools/stand_am.py` reads. One date in the source is anomalous and kept as given (LGBl. 1978 Nr. 3, see its commit).

## How it is checked

`tools/check_repo.py` reads every version of every act back from git on the day it took effect and compares it with
the official text: file by file with the text parsed from Lilex's page, and word for word with all the words of the
page (without footnotes), read independently of the parser. The results are in [`REPRODUCE.md`](REPRODUCE.md).

## What "author" means

The author of a commit is the law that made the change: `LGBl. 2003 Nr. 186` (with an address ending
`@gesetze-li.invalid`, which cannot exist), so `git blame` names the law. Lilex lists, for each version, the laws that
produced it, and the footnote under each amended provision names the law that changed it ("Art. 7 Abs. 2 abgeändert
durch LGBl. 2003 Nr. 186."). A change is credited to a law only when the footnotes name it. A change no footnote
explains, usually Lilex's own correction of spelling, punctuation or spacing, is committed separately by
`Rechtsdienst der Regierung (Lilex)`, with "Änderung ohne Nachweis" in its subject; it is never credited to a law.
The committer is always `Lexifina`.

The Constitution and the VRG begin with the act as enacted, credited to the act itself. Lilex has no text of the StGHG
before 3 November 2009, so its first commit is that version, by the Legal Service, and its message names the laws Lilex
lists for the earlier history. Nothing before it is guessed.

## What it does not show

- Versions Lilex does not publish as text (the StGHG before 2009). The VRG's last version in Lilex is from 2012.
- The footnotes themselves, and Lilex's notes on case law. The footnotes are used to credit changes.
- Laws not yet in force (Lilex lists only versions in force; a branch `kuenftig` would hold them).

Consolidated texts have no legal force; only the Landesgesetzblatt is authoritative.

## How it is built

`tools/build.py` reads Lilex and writes this repository from scratch; the same data gives the same hashes. Every
step, the software, the decisions made by hand and what an AI model did are in [`REPRODUCE.md`](REPRODUCE.md). Each
act's folder has a `README.md` listing its provisions with how often each changed.

## Licence

Laws and other official enactments, and official collections of them, are not protected by copyright in Liechtenstein
(Art. 5 URG). Source: Lilex, www.gesetze.li, Rechtsdienst der Regierung, Vaduz. Lilex states: "Konsolidierte
Rechtsvorschriften dienen ausschliesslich der Information und entfalten keine Rechtswirkung." The history, commit
messages, tables and tools are released under [CC0 1.0](LICENSE).

## Current-text breadth append

The repository records 3686 further source-dated current texts, alongside three selected full histories. Coverage is 3689 of 3689 officially listed current records as at 2026-11-04. Every breadth act has one version, labelled “oldest version available”; earlier history is not included. Dates are the official version start and matching gazette chronology dates. Complete single-file texts retain acts whose structure cannot safely be split. Official images remain in place as original SHA-256-named binary assets.

| Record | Acts |
|---|---:|
| Selected dated histories | 3 |
| Current-text breadth acts | 3686 |
| Official current listing | 3689 |

Act metadata is in `data/current-acts.json`; the latest append input is in `data/breadth-input.json`, and earlier append inputs are retained under `data/inputs/`.

## More

From [lexifina/global-law](https://github.com/lexifina/global-law):

- [FEATURES.md](https://github.com/lexifina/global-law/blob/main/FEATURES.md): every feature, and what every corpus must support (`git blame`, `law.py`, the MCP tools)
- [FAQ.md](https://github.com/lexifina/global-law/blob/main/FAQ.md): questions and answers · [CONTRIBUTING.md](https://github.com/lexifina/global-law/blob/main/CONTRIBUTING.md): proposing changes · [MCP.md](https://github.com/lexifina/global-law/blob/main/MCP.md): the MCP server · [REPRODUCE.md](https://github.com/lexifina/global-law/blob/main/REPRODUCE.md): how it was built · [CHANGELOG.md](https://github.com/lexifina/global-law/blob/main/CHANGELOG.md)
- [FRESHNESS.md](https://github.com/lexifina/global-law/blob/main/FRESHNESS.md): how current each corpus is · [Monitoring](https://github.com/lexifina/global-law/tree/main/monitoring): whether updates are running · [WATCHING.md](https://github.com/lexifina/global-law/blob/main/WATCHING.md): how each official source is watched for changes
- [performance/](https://github.com/lexifina/global-law/tree/main/performance): how fast the tools are, measured
- [visualisations/](https://github.com/lexifina/global-law/tree/main/visualisations): charts and bridges across the world's law
- [Vulnerabilities](https://github.com/lexifina/global-law/tree/main/vulnerabilities): mistakes in legislation as published
