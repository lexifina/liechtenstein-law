# Liechtenstein law, change by change

Three acts of the Principality of Liechtenstein as a git repository: the Constitution (Verfassung, LV, LR 101), the
People's Rights Act (Volksrechtegesetz, VRG, LR 161) and the Constitutional Court Act (Staatsgerichtshofgesetz, StGHG,
LR 173.10). Each amending law is one commit, credited to that law and dated the day it took effect, at noon in Vaduz.
The text is the consolidated text published by the Government's Legal Service in [Lilex](https://www.gesetze.li).

*Deutsch: [unten](#deutsch).*

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
- Any act beyond these three. The same build works for any act in Lilex: add it to `ACTS` in `tools/build.py`.

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

---

## Deutsch

Drei Erlasse des Fürstentums Liechtenstein als Git-Repository: die Verfassung (LR 101), das Volksrechtegesetz
(LR 161) und das Staatsgerichtshofgesetz (LR 173.10), im konsolidierten Text aus Lilex.

- **Jeder Commit ist ein Abänderungserlass**, als Autor eingetragen (`LGBl. 2003 Nr. 186`), so dass `git blame` zeigt,
  welches Gesetz welchen Absatz geschrieben hat. Den Erlass nennen die Chronologie von Lilex und die Fussnote unter
  der Bestimmung.
- **Jeder Commit trägt das Datum des Inkrafttretens**, Mittag in Vaduz. In der Nachricht stehen auch das Datum des
  Gesetzes und der Ausgabetag des Landesgesetzblatts.
- **Jeder Artikel ist eine Datei**, jeder Absatz eine Zeile.
- **Änderungen ohne Nachweis sind keine Gesetze.** Wo sich der Text ohne Fussnote geändert hat, ist der Commit vom
  Rechtsdienst der Regierung und so bezeichnet.

Konsolidierte Rechtsvorschriften entfalten keine Rechtswirkung; massgebend ist allein das Landesgesetzblatt.
