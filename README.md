# Liechtensteinisches Recht: geltende Texte und ausgewählte Versionsgeschichten

**Deutsch** · [English](README.en.md)

<picture>
<source media="(prefers-color-scheme: dark)" srcset="data/de/effort-dark.svg">
<img alt="Liechtensteinisches Recht in diesem Repository: Inhalt, Änderungen nach Jahr des Inkrafttretens, Vollständigkeit gegenüber den amtlichen Quellen und Richtigkeit des Enthaltenen" src="data/de/effort-light.svg" width="880">
</picture>

Teil von [lexifina/global-law](https://github.com/lexifina/global-law), einer einzigen Git-Historie für das Recht aller Länder: Dies ist das Landesrecht Liechtensteins, das global-law unter `liechtenstein/national/acts/` liest.

Ausgewählte vollständige Versionsgeschichten von drei Erlassen des Fürstentums Liechtenstein: der Verfassung (LV,
LR 101), dem Volksrechtegesetz (VRG, LR 161) und dem Staatsgerichtshofgesetz (StGHG, LR 173.10). Jedes
Abänderungsgesetz ist ein Commit, diesem Gesetz zugeschrieben und auf den Tag seines Inkrafttretens datiert, 12 Uhr
mittags in Vaduz. Der Text ist der konsolidierte Text, den der Rechtsdienst der Regierung in [Lilex](https://www.gesetze.li)
veröffentlicht.

## Die Fragen als Git-Befehle

| Frage | Befehl |
| --- | --- |
| Was sagte Art. 7 der Verfassung am 1. Januar 2000? | `python tools/stand_am.py 2000-01-01 lv 7` |
| Die ganze Verfassung im Stand von 1950 | `python tools/stand_am.py 1950-01-01 lv` |
| Welches Gesetz hat welchen Absatz von Art. 7 geschrieben? | `git blame lv/art-007.md` |
| Jede Änderung von Art. 7, mit dem Gesetz und dem Tag | `git log -p lv/art-007.md` |
| Alles, was ein Gesetz geändert hat | `git show lgbl/2003-186` |
| Was sich im VRG an einem Tag geändert hat | `git show vrg/2004-11-12` |
| Die Abänderungsgesetze mit allen ihren Daten | [`erlasse.csv`](erlasse.csv) |
| Änderungen, die keine Fussnote erklärt | `git log --grep="Änderung ohne Nachweis"` |
| Gesetze, die mehrere Erlasse geändert haben | `git log --author="LGBl. 2025"` |

## Die Daten und welches wir verwenden

Ein liechtensteinisches Gesetz hat ein Datum im Titel (`Dated:`, «Verfassungsgesetz vom 8. November 2024»), den
Ausgabetag des Landesgesetzblatts, in dem es kundgemacht wird (`Published:`), und den Tag seines Inkrafttretens
(`In-force:`). **Commits tragen das Datum des Tages, an dem die Änderung in Kraft trat**, 12 Uhr mittags in Vaduz:
Dieser Tag entscheidet, welcher Text gilt. Es ist der Tag, den Lilex als Beginn der Fassung angibt, die aus dem Gesetz
hervorgegangen ist. Alle drei Daten stehen in jeder Commit-Nachricht.

Git kann kein Datum vor 1970 speichern. Die Commits für die Änderungen der Verfassung von 1921 bis 1965 sind auf den
1. Januar 1970 (UTC) datiert, in ihrer Reihenfolge jeweils eine Sekunde auseinander; ihr tatsächlicher Tag steht im
Trailer `In-force:`, den `tools/stand_am.py` liest. Ein Datum in der Quelle ist auffällig und wird so beibehalten, wie
es angegeben ist (LGBl. 1978 Nr. 3, siehe dessen Commit).

## Wie es geprüft wird

`tools/check_repo.py` liest jede Fassung jedes Erlasses am Tag ihres Inkrafttretens aus Git zurück und vergleicht sie
mit dem amtlichen Text: Datei für Datei mit dem Text, der aus der Seite in Lilex geparst wird, und Wort für Wort mit
allen Wörtern der Seite (ohne Fussnoten), unabhängig vom Parser gelesen. Die Ergebnisse stehen in
[`REPRODUCE.md`](REPRODUCE.md).

## Was «Autor» bedeutet

Der Autor eines Commits ist das Gesetz, das die Änderung vorgenommen hat: `LGBl. 2003 Nr. 186` (mit einer Adresse auf
`@gesetze-li.invalid`, die es nicht geben kann), so dass `git blame` das Gesetz nennt. Lilex führt für jede Fassung die
Gesetze auf, aus denen sie hervorgegangen ist, und die Fussnote unter jeder geänderten Bestimmung nennt das Gesetz, das
sie geändert hat («Art. 7 Abs. 2 abgeändert durch LGBl. 2003 Nr. 186.»). Eine Änderung wird einem Gesetz nur
zugeschrieben, wenn die Fussnoten es nennen. Eine Änderung, die keine Fussnote erklärt, meist eine eigene Korrektur von
Rechtschreibung, Zeichensetzung oder Abständen durch Lilex, wird gesondert vom `Rechtsdienst der Regierung (Lilex)`
committet, mit «Änderung ohne Nachweis» im Betreff; sie wird nie einem Gesetz zugeschrieben. Committer ist immer
`Lexifina`.

Die Verfassung und das VRG beginnen mit dem Erlass in seiner ursprünglichen Fassung, dem Erlass selbst zugeschrieben.
Lilex hat keinen Text des StGHG vor dem 3. November 2009; sein erster Commit ist daher diese Fassung, vom Rechtsdienst,
und seine Nachricht nennt die Gesetze, die Lilex für die frühere Geschichte aufführt. Nichts davor wird erraten.

## Was es nicht zeigt

- Fassungen, die Lilex nicht als Text veröffentlicht (das StGHG vor 2009). Die letzte Fassung des VRG in Lilex stammt
  von 2012.
- Die Fussnoten selbst und die Hinweise von Lilex zur Rechtsprechung. Die Fussnoten dienen dazu, Änderungen
  zuzuschreiben.
- Gesetze, die noch nicht in Kraft sind (Lilex führt nur geltende Fassungen; ein Branch `kuenftig` würde sie
  aufnehmen).

Konsolidierte Texte haben keine Rechtswirkung; massgebend ist allein das Landesgesetzblatt.

## Wie es erstellt wird

`tools/build.py` liest Lilex und schreibt dieses Repository von Grund auf neu; dieselben Daten ergeben dieselben Hashes.
Jeder Schritt, die Software, die von Hand getroffenen Entscheidungen und was ein KI-Modell getan hat, stehen in
[`REPRODUCE.md`](REPRODUCE.md). Der Ordner jedes Erlasses enthält eine `README.md`, die seine Bestimmungen auflistet und
angibt, wie oft jede geändert wurde.

## Lizenz

Gesetze und andere amtliche Erlasse sowie amtliche Sammlungen davon sind in Liechtenstein nicht urheberrechtlich
geschützt (Art. 5 URG). Quelle: Lilex, www.gesetze.li, Rechtsdienst der Regierung, Vaduz. Lilex hält fest:
«Konsolidierte Rechtsvorschriften dienen ausschliesslich der Information und entfalten keine Rechtswirkung.» Die
Historie, die Commit-Nachrichten, die Tabellen und die Werkzeuge werden unter [CC0 1.0](LICENSE) freigegeben.

Dies ist eine Übersetzung der englischen Fassung ([README.en.md](README.en.md)); bei Abweichungen gilt die englische Fassung.

## Ergänzung: geltende Texte in der Breite

Das Repository verzeichnet 3'686 weitere geltende Texte, nach der Quelle datiert, neben drei ausgewählten vollständigen
Versionsgeschichten. Die Abdeckung beträgt 3'689 von 3'689 amtlich aufgeführten geltenden Einträgen, Stand
4. November 2026. Jeder Erlass der Breite hat eine Fassung, bezeichnet als «oldest version available» (älteste
verfügbare Fassung); frühere Geschichte ist nicht enthalten. Die Daten sind der amtliche Beginn der Fassung und die
entsprechenden Daten der Chronologie des Landesgesetzblatts. Erlasse, deren Gliederung sich nicht sicher aufteilen
lässt, bleiben als vollständiger Text in einer einzigen Datei erhalten. Amtliche Bilder bleiben an ihrem Platz, als
ursprüngliche Binärdateien, die nach ihrem SHA-256-Wert benannt sind.

| Eintrag | Erlasse |
|---|---:|
| Ausgewählte datierte Versionsgeschichten | 3 |
| Geltende Texte in der Breite | 3'686 |
| Amtliches Verzeichnis der geltenden Erlasse | 3'689 |

Die Metadaten der Erlasse stehen in `data/current-acts.json`; die Eingabe der letzten Ergänzung steht in
`data/breadth-input.json`, frühere Eingaben werden unter `data/inputs/` aufbewahrt.

## Mehr

Aus dem Repository [lexifina/global-law](https://github.com/lexifina/global-law) (auf Englisch):

- [FEATURES.md](https://github.com/lexifina/global-law/blob/main/FEATURES.md): alle Funktionen und was jedes Korpus unterstützen muss (`git blame`, `law.py`, MCP-Werkzeuge)
- [FAQ.md](https://github.com/lexifina/global-law/blob/main/FAQ.md): Fragen und Antworten · [CONTRIBUTING.md](https://github.com/lexifina/global-law/blob/main/CONTRIBUTING.md): Änderungen vorschlagen · [MCP.md](https://github.com/lexifina/global-law/blob/main/MCP.md): MCP-Server · [REPRODUCE.md](https://github.com/lexifina/global-law/blob/main/REPRODUCE.md): wie es erstellt wurde · [CHANGELOG.md](https://github.com/lexifina/global-law/blob/main/CHANGELOG.md)
- [FRESHNESS.md](https://github.com/lexifina/global-law/blob/main/FRESHNESS.md): wie aktuell jedes Korpus ist · [Überwachung](https://github.com/lexifina/global-law/tree/main/monitoring): ob die Aktualisierungen funktionieren · [WATCHING.md](https://github.com/lexifina/global-law/blob/main/WATCHING.md): wie jede amtliche Quelle auf Änderungen überwacht wird
- [performance/](https://github.com/lexifina/global-law/tree/main/performance): wie schnell die Werkzeuge sind, gemessen
- [visualisations/](https://github.com/lexifina/global-law/tree/main/visualisations): Diagramme und Verbindungen im Recht der ganzen Welt
- [Schwachstellen](https://github.com/lexifina/global-law/tree/main/vulnerabilities): Fehler in Rechtsakten, wie sie veröffentlicht wurden
