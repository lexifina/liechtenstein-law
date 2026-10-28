"""Builds a git repository of Liechtenstein law from Lilex (www.gesetze.li), in which every amending law is one commit,
dated the day it took effect.

    python -X utf8 scripts/liechtenstein-law/build.py [--repo ../liechtenstein-law] [--today 2026-10-28] [--offline]

Lilex, the law database of the Government's Legal Service (Rechtsdienst der Regierung), publishes each act of the
consolidated law (Konsolidiertes Recht) in every version ("Fassung") with the day it applies from, and lists for each
version the Landesgesetzblatt (LGBl.) numbers that produced it ("Chronologie der Rechtsvorschrift"). Each amended
provision carries a footnote naming the law that changed it ("Art. 7 Abs. 2 abgeändert durch LGBl. 2003 Nr. 186.").
We take every version of the acts below, compare consecutive versions provision by provision, and credit each change
to the law of that version that the provision's footnotes name. A change no footnote explains is never credited to a
law: it gets its own commit by the Legal Service, labelled as unexplained.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html as htmlmod
import http.cookiejar
import io
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from lxml import html as lhtml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = HERE / '.cache'
BASE = 'https://www.gesetze.li'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
PAUSE = 1.5          # seconds between two requests to Lilex; one request at a time
COMMITTER = ('Lexifina', 'liechtenstein-law@lexifina.com')
RDR = ('Rechtsdienst der Regierung (Lilex)', 'rdr@gesetze-li.invalid')

# The acts in the record: the LGBl number that enacted them (Lilex's identifier), the LR number (the systematic
# collection), and a short slug for the repository's folders.
ACTS = [
    {'lgbl': '1921.015', 'lr': '101', 'slug': 'lv', 'short': 'LV'},
    {'lgbl': '1973.050', 'lr': '161', 'slug': 'vrg', 'short': 'VRG'},
    {'lgbl': '2004.032', 'lr': '173.10', 'slug': 'stghg', 'short': 'StGHG'},
]


# ---------------------------------------------------------------- fetching

REQUESTS: list[dict] = []   # every request the build made, for REPRODUCE.md
_last = [0.0]
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _get(url: str) -> bytes:
    wait = _last[0] + PAUSE - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'de'})
        with _opener.open(req, timeout=120) as r:
            return r.read()
    except Exception as exc:   # a self-signed certificate in the chain on some machines: fall back to curl
        if 'CERTIFICATE' not in str(exc).upper():
            raise
        out = subprocess.run(['curl', '-sS', '-f', '-L', '--max-redirs', '4', '-A', UA, url], capture_output=True)
        if out.returncode:
            raise RuntimeError(f'curl {url}: {out.stderr.decode(errors="replace")}')
        return out.stdout


def fetch(url: str, offline: bool = False) -> bytes:
    """GET with a file cache keyed by the URL, so a rebuild reads the same bytes."""
    key = hashlib.sha256(url.encode()).hexdigest()[:32]
    path = CACHE / key
    REQUESTS.append({'url': url, 'file': path})
    if path.exists():
        return path.read_bytes()
    if offline:
        raise SystemExit(f'not cached: {url}')
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / '.gitignore').write_text('*\n')
    for attempt in range(4):
        try:
            body = _get(url)
            if b'/error_pages/' in body[:4000]:
                raise RuntimeError(f'Lilex error page for {url}')
            path.write_bytes(body)
            return body
        except Exception:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError


def uid(lgbl: str) -> str:
    """1921.015 -> 1921015000, the form Lilex uses in its addresses."""
    y, n = lgbl.split('.')
    return f'{y}{int(n):03d}000'


def lgbl_label(lgbl: str) -> str:
    y, n = lgbl.split('.')
    return f'LGBl. {y} Nr. {int(n)}'


def clean(s: str) -> str:
    return re.sub(r'\s+', ' ', htmlmod.unescape(s).replace('\u00a0', ' ')).strip()


def de_date(s: str) -> str | None:
    m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', s)
    return f'{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else None


MONTHS = {'januar': 1, 'jänner': 1, 'februar': 2, 'märz': 3, 'april': 4, 'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
          'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12}


def long_date(s: str) -> str | None:
    """'vom 8. November 2024' -> 2024-11-08."""
    m = re.search(r'(\d{1,2})\.\s*([A-Za-zäÄ]+)\s+(\d{4})', s)
    if not m or m.group(2).lower() not in MONTHS:
        return None
    return f'{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}'


# ---------------------------------------------------------------- the act's versions and its chronology

def act_meta(act: dict, offline: bool) -> dict:
    """Lilex's page for the act: every version with the days it applies from and to, and the chronology, which names
    the LGBl numbers behind each version."""
    page = fetch(f'{BASE}/konso/{uid(act["lgbl"])}/meta', offline).decode('utf-8')
    versions = []
    for num, label in re.findall(r'<option[^>]*value="(\d+)">\s*([^<]+?)\s*</option>', page):
        days = re.findall(r'\d{2}\.\d{2}\.\d{4}', label)
        versions.append({'version': int(num), 'from': de_date(days[0]), 'to': de_date(days[1]) if len(days) > 1 else None})
    versions.sort(key=lambda v: v['from'])
    chrono = []
    table = page[page.index('Chronologie der Rechtsvorschrift'):]
    for tr in re.findall(r'<tr>(.*?)</tr>', table, re.S):
        tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)
        if len(tds) < 6:
            continue
        v = re.search(r'version=(\d+)', tds[0])
        chrono.append({'version': int(v.group(1)) if v else None, 'from': de_date(clean(re.sub(r'<[^>]+>', ' ', tds[0]))),
                       'lgbl': clean(re.sub(r'<[^>]+>', ' ', tds[1])),
                       'published': de_date(clean(re.sub(r'<[^>]+>', ' ', tds[3]))),
                       'bua': re.findall(r'BuA \d+/\d{4}', clean(re.sub(r'<[^>]+>', ' ', tds[4]))),
                       'lr': clean(re.sub(r'<[^>]+>', ' ', tds[5]))})
    # Group the chronology by version. A row without a version link shares the version of the row above it when it has
    # the same day; otherwise it is older than every version Lilex publishes as text.
    by_version: dict[int, list[dict]] = {v['version']: [] for v in versions}
    earlier: list[dict] = []
    current = None
    for row in chrono:
        if row['version'] is not None:
            current = row
            by_version.setdefault(row['version'], []).append(row)
        elif current is not None and row['from'] == current['from']:
            by_version[current['version']].append(row)
        else:
            if row['from'] >= versions[0]['from']:
                raise SystemExit(f'{act["slug"]}: chronology row {row} is neither in a version nor before the first one')
            earlier.append(row)
    for v in versions:
        rows = by_version.get(v['version'], [])
        if not rows:
            raise SystemExit(f'{act["slug"]}: version {v["version"]} ({v["from"]}) has no chronology row')
        for r in rows:
            if r['from'] != v['from']:
                raise SystemExit(f'{act["slug"]}: version {v["version"]} starts {v["from"]} but its chronology says {r["from"]}')
        v['laws'] = [r['lgbl'] for r in rows]
    title = re.search(r'<meta name="description" content="([^"]*)"', page)
    return {'versions': versions, 'chrono': chrono, 'earlier': sorted(earlier, key=lambda r: (r['from'], r['lgbl'])),
            'rows': {r['lgbl']: r for r in chrono}}


def law_meta(lgbl: str, row: dict, offline: bool) -> dict:
    """The full title of an LGBl number, from the description of its text in Lilex's chronological collection (the
    chronology shortens long titles), and the day in its title ("vom 8. November 2024")."""
    page = fetch(f'{BASE}/chrono/html/{uid(lgbl)}', offline).decode('utf-8')
    m = re.search(r'<meta name="description" content="([^"]*)"', page)
    title = clean(m.group(1)) if m else ''
    head = re.split(r' (?:über|betreffend|zur|zum) ', title)[0]
    m = re.search(r'ausgegeben am\s+([^<]+?)\s*</td>', page)
    return {'lgbl': lgbl, 'label': lgbl_label(lgbl), 'title': title, 'dated': long_date(head) if ' vom ' in head else None,
            'issued': row['published'], 'printed_issue': long_date(m.group(1)) if m else None, 'bua': row['bua'],
            'lr': row['lr'], 'url': f'{BASE}/chrono/{uid(lgbl)}', 'text': f'{BASE}/chrono/html/{uid(lgbl)}'}


# ---------------------------------------------------------------- reading one version

BANNER = re.compile(r'Jahrgang\s+(\d{4})\s+Nr\.\s+(\d+)')
HEADINGS = {'tit1m', 'tit1', 'tit1ue', 'tit2m', 'tit2', 'tit2ue', 'tit3m', 'tit3', 'tit3ue', 'tit4m', 'tit4', 'tit4ue', 'tits'}
INGRESS = {'htit1', 'htit2', 'htit3', 'vom', 'einl'}


def text_of(e) -> str:
    """The words of an element without footnote markers and without its nested block elements."""
    def walk(x, top: bool) -> str:
        if not isinstance(x.tag, str):
            return x.tail or '' if not top else ''
        if x.tag == 'a' and (x.get('href') or '').startswith('#fn'):
            return '\x00' + (x.tail or '')
        if x.tag == 'sup' and re.fullmatch(r'[\s,;]*', x.text_content() or '') and (x.text_content() or '').strip():
            return '\x01' + (x.tail or '')   # the comma Lilex sets between two footnote markers
        if x.tag == 'div' and not top:
            return x.tail or ''   # nested block: read separately; its tail belongs here
        if x.tag == 'br':
            return ' ' + (x.text or '') + ''.join(walk(c, False) for c in x) + (x.tail or '')
        inner = (x.text or '') + ''.join(walk(c, False) for c in x)
        return inner if top else inner + (x.tail or '')
    return clean(drop_markers(walk(e, True).replace('\t', ' ')))


MARKERS = re.compile(r'\s*\x00(?:\s*\x01?\s*\x00)*\s*')


def drop_markers(s: str) -> str:
    """Removes footnote markers. Lilex's HTML is inconsistent about the space next to a marker from one version to the
    next ("Landesangehörigen⁵ Eintrag" and "Landesangehörigen⁵Eintrag"), so a marker counts as a word space between two
    words and as nothing before punctuation or at either end."""
    def repl(m):
        left = s[m.start() - 1] if m.start() > 0 else ''
        right = s[m.end()] if m.end() < len(s) else ''
        if not left or not right or right in ',.;:)!?' or left in '(':
            return ''
        return ' '
    s = MARKERS.sub(repl, s)
    return s.replace('\x01', ',').replace('\x00', '')


def notes_in(e) -> list[int]:
    return [int(a.get('href')[3:]) for a in e.iter('a') if re.fullmatch(r'#fn\d+', a.get('href') or '')]


def block_lines(e, level: int) -> list[dict]:
    """A block element (paragraph, list item, ...) as lines: its own words, then each nested block one level down."""
    out = []
    own = text_of(e)
    if own:
        out.append({'level': level, 'text': own})
    for c in e:
        if isinstance(c.tag, str) and c.tag == 'div':
            out.extend(block_lines(c, level + 1 if own else level))
        elif isinstance(c.tag, str) and c.tag == 'table':
            out.extend(table_lines(c, level + 1))
    return out


def table_lines(t, level: int) -> list[dict]:
    out = []
    for tr in t.iter('tr'):
        # A cell may hold its words directly or in block elements of its own.
        cells = [' '.join(l['text'] for l in block_lines(td, 0)) for td in tr if isinstance(td.tag, str) and td.tag in ('td', 'th')]
        s = ' | '.join(c for c in cells if c)
        if s:
            out.append({'level': level, 'text': s})
    return out


def art_key(name: str) -> str:
    """The anchor 'art:13bis' -> '13bis'; 'art:8c bis 8e' -> '8c-bis-8e'."""
    return re.sub(r'[^0-9a-z]+', '-', name.split(':', 1)[1].lower()).strip('-')


def read_version(raw: bytes) -> dict:
    """One version as units in document order. A unit is the ingress, an article (with the headings of the parts that
    begin with it), the closing part (signatures, promulgation), or the excerpt of one amending law printed at the end
    (its transitional and commencement provisions). Each unit has lines and the footnotes attached to it."""
    doc = lhtml.fromstring(raw.decode('utf-8'))
    body = doc.find('body')
    footnotes: dict[int, dict] = {}
    for fn in body.iter('div'):
        if fn.get('class') == 'fntext':
            a = fn.find('a')
            if a is None or not (a.get('name') or '').startswith('fn'):
                continue
            n = int(a.get('name')[2:])
            laws = [f'{h[8:12]}.{h[12:15]}' for h in (x.get('href') or '' for x in fn.iter('a')) if re.fullmatch(r'/chrono/\d{10}', h)]
            footnotes[n] = {'text': clean(fn.text_content())[len(str(n)):].strip(), 'laws': laws}

    units: list[dict] = []
    state = {'mode': 'ingress', 'pending': [], 'pending_notes': [], 'unit': None}
    seen_keys: dict[str, int] = {}

    def new_unit(key: str, kind: str, label: str) -> dict:
        if key in seen_keys:
            seen_keys[key] += 1
            key = f'{key}-{seen_keys[key]}'
        else:
            seen_keys[key] = 1
        u = {'key': key, 'kind': kind, 'label': label, 'lines': [], 'notes': []}
        units.append(u)
        return u

    def ingress() -> dict:
        if not units or units[0]['kind'] != 'ingress':
            units.insert(0, {'key': 'ingress', 'kind': 'ingress', 'label': 'Ingress', 'lines': [], 'notes': []})
        return units[0]

    def closing() -> dict:
        if state['unit'] is None or state['unit']['kind'] != 'schluss':
            state['unit'] = new_unit('schluss', 'schluss', 'Schlussteil')
        return state['unit']

    def emit(lines: list[dict], notes: list[int]):
        mode = state['mode']
        if mode == 'ingress':
            u = ingress()
        elif mode == 'body':
            u = closing()
        else:
            u = state['unit']
        u['lines'].extend(lines)
        u['notes'].extend(notes)

    def walk(node):
        for c in node:
            if not isinstance(c.tag, str):
                continue
            cls = c.get('class') or ''
            if c.tag == 'hr' or cls == 'fntext':
                continue
            if c.tag == 'table':
                text = clean(' '.join(c.itertext()))
                m = BANNER.search(text)
                if m and 'Landesgesetzblatt' in text:
                    if state['mode'] == 'ueb':
                        lg = f'{m.group(1)}.{int(m.group(2)):03d}'
                        state['unit'] = new_unit(f'ueb-{lg}', 'ueb', f'Übergangsbestimmungen {lgbl_label(lg)}')
                    continue   # the LGBl header of the act or of an amending law: in the file name and the trailers
                emit(table_lines(c, 0), notes_in(c))
                continue
            if c.tag != 'div':
                continue
            if cls == 'art' and state['mode'] in ('ingress', 'body'):
                anchor = next((a.get('name') for a in c.iter('a') if (a.get('name') or '').startswith('art:')), None)
                key = art_key(anchor) if anchor else f'x{len(units)}'
                label = text_of(c)
                u = new_unit(f'art-{key}', 'art', label)
                sacht = [d for d in c if isinstance(d.tag, str) and d.get('class') == 'sacht']
                head = label + (' ' + ' '.join(text_of(s) for s in sacht) if sacht else '')
                u['lines'] = [{'level': -1, 'text': h} for h in state['pending']] + [{'level': -2, 'text': head}]
                u['notes'] = state['pending_notes'] + notes_in(c)
                state['pending'], state['pending_notes'] = [], []
                for d in c:
                    if isinstance(d.tag, str) and d.tag == 'div' and d.get('class') != 'sacht':
                        u['lines'].extend(block_lines(d, 0))
                    elif isinstance(d.tag, str) and d.tag == 'table':
                        u['lines'].extend(table_lines(d, 0))
                state['mode'] = 'body'
                state['unit'] = u
                continue
            if cls == 'tits' and state['mode'] != 'ueb':
                if state['pending']:
                    emit([{'level': -1, 'text': h} for h in state['pending']], state['pending_notes'])
                    state['pending'], state['pending_notes'] = [], []
                state['mode'] = 'ueb'
                state['unit'] = new_unit('ueb-kopf', 'ueb-kopf', 'Übergangsbestimmungen')
                state['unit']['lines'].append({'level': -1, 'text': text_of(c)})
                continue
            if (cls in HEADINGS or cls == 'sacht') and state['mode'] != 'ueb':
                # A heading, or a subject heading set above a group of articles, belongs to the article that follows.
                state['pending'].append(text_of(c))
                state['pending_notes'].extend(notes_in(c))
                continue
            if cls == '':
                walk(c)
                continue
            if state['mode'] in ('ingress', 'body') and state['pending']:
                # Text after a heading but before any article (rare): the heading belongs to that text.
                emit([{'level': -1, 'text': h} for h in state['pending']], state['pending_notes'])
                state['pending'], state['pending_notes'] = [], []
            lines = block_lines(c, 0)
            if cls in HEADINGS or cls in INGRESS:
                for l in lines[:1]:
                    l['level'] = -1 if cls in HEADINGS else 0
            emit(lines, notes_in(c))

    walk(body)
    if state['pending']:
        emit([{'level': -1, 'text': h} for h in state['pending']], state['pending_notes'])
    for u in units:
        u['laws'] = sorted({l for n in u['notes'] for l in footnotes.get(n, {}).get('laws', [])})
        u['notetexts'] = [footnotes[n]['text'] for n in u['notes'] if n in footnotes]
        u['text'] = unit_text(u)
    return {'units': units, 'footnotes': footnotes}


def unit_text(u: dict) -> str:
    """The unit as the repository holds it: one line per heading, article title, paragraph and list item."""
    out = []
    for l in u['lines']:
        if l['level'] == -1:
            out.append(f'## {l["text"]}')
        elif l['level'] == -2:
            out.append(f'# {l["text"]}')
        elif l['level'] == 0:
            out.append(l['text'])
        else:
            out.append('  ' * (l['level'] - 1) + '- ' + l['text'])
    return '\n\n'.join(out) + '\n'


# ---------------------------------------------------------------- file names and order

LATIN = ['bis', 'ter', 'quater', 'quinquies', 'sexies', 'septies', 'octies', 'novies', 'decies']


def unit_order(key: str) -> tuple:
    if key == 'ingress':
        return (0, 0, 0, '')
    m = re.fullmatch(r'art-(\d+)([a-z]*)(.*)', key)
    if m:
        suf = m.group(2)
        rank = 0 if not suf else (LATIN.index(suf) + 2 if suf in LATIN else ord(suf[0]) - 96 if len(suf) == 1 else 50)
        return (1, int(m.group(1)), rank, m.group(3))
    if key.startswith('schluss'):
        return (2, 0, 0, key)
    if key == 'ueb-kopf':
        return (3, 0, 0, '')
    return (4, 0, 0, key)


def file_name(key: str) -> str:
    m = re.fullmatch(r'art-(\d+)(.*)', key)
    if m:
        return f'art-{int(m.group(1)):03d}{m.group(2)}.md'
    if key.startswith('ueb-'):
        return f'uebergang/{key[4:].replace(".", "-")}.md' if key != 'ueb-kopf' else 'uebergang/00-kopf.md'
    return f'{key}.md'


def section_free(text: str) -> str:
    """A unit's text without the part headings at its top (which move when an article is inserted before it)."""
    return '\n\n'.join(l for l in text.split('\n\n') if not l.startswith('## '))


def heading_lines(text: str) -> list[str]:
    return [l for l in text.split('\n\n') if l.startswith('## ')]


def in_range(key: str, rng: str) -> bool:
    """Whether article key 'art-8d' lies in a range unit 'art-8c-bis-8e'."""
    m = re.fullmatch(r'art-(\d+[a-z]*)-bis-(\d+[a-z]*)', rng)
    if not m:
        return False
    return unit_order(f'art-{m.group(1)}') <= unit_order(key) <= unit_order(f'art-{m.group(2)}')


# ---------------------------------------------------------------- one act: versions, changes, causes

def build_act(act: dict, offline: bool) -> dict:
    meta = act_meta(act, offline)
    versions = []
    for v in meta['versions']:
        url = f'{BASE}/konso/html/{uid(act["lgbl"])}?version={v["version"]}'
        raw = fetch(url, offline)
        parsed = read_version(raw)
        versions.append({**v, 'url': url, 'sha256': hashlib.sha256(raw).hexdigest(),
                         'units': {u['key']: u for u in parsed['units']}})
    laws = {r['lgbl']: law_meta(r['lgbl'], r, offline) for r in meta['chrono']}
    changes = []
    problems = []
    for prev, cur in zip(versions, versions[1:]):
        L = set(cur['laws'])
        keys = sorted(set(prev['units']) | set(cur['units']), key=unit_order)
        changed = [k for k in keys if (prev['units'].get(k) or {}).get('text') != (cur['units'].get(k) or {}).get('text')]
        cause: dict[str, str] = {}
        why: dict[str, str] = {}
        also: dict[str, list[str]] = {}
        # 1. The excerpt of an amending law printed at the end of the act is that law's own text.
        for k in changed:
            if k.startswith('ueb-') and k != 'ueb-kopf' and k[4:] in L:
                cause[k], why[k] = k[4:], 'excerpt of the amending law'
        # 2. The footnotes attached to the provision name the law.
        for k in changed:
            if k in cause:
                continue
            u = cur['units'].get(k) or prev['units'][k]
            named = sorted(set(u['laws']) & L)
            if len(named) == 1:
                cause[k], why[k] = named[0], 'footnote'
            elif named:
                # Two laws of the same day amended this provision, and the consolidated text cannot separate them. The
                # change is committed with the later of them, and the commit names the other.
                cause[k], why[k] = named[-1], 'footnote (two laws)'
                also[k] = named[:-1]
        # 3. An article number that disappears because the law renumbered or merged it: the law whose footnote in the
        #    new version names the old number, or whose new range of articles covers it.
        for k in changed:
            if k in cause or k in cur['units'] or not k.startswith('art-'):
                continue
            old = prev['units'][k]['label'].replace('Art. ', '')
            # The footnote that records a renumbering ("Art. 109 (109bis) ... abgeändert durch LGBl. 2003 Nr. 186") is
            # sometimes added only in a later version, so the later versions are searched too.
            later = versions[versions.index(cur):]
            for k2, u2 in [(k2, u2) for v2 in later for k2, u2 in v2['units'].items()]:
                named = sorted(set(u2['laws']) & L)
                if len(named) != 1:
                    continue
                if in_range(k, k2) or any(re.search(r'\(' + re.escape(old) + r'\)', t) for t in u2['notetexts']):
                    cause[k], why[k] = named[0], f'renumbered or merged into {u2["label"]}'
                    break
        # 4. A change of the part headings alone, which moved to or from a provision the same law changed.
        for k in changed:
            if k in cause:
                continue
            a, c = (prev['units'].get(k) or {}).get('text', ''), (cur['units'].get(k) or {}).get('text', '')
            if a and c and section_free(a) == section_free(c):
                moved = set(heading_lines(a)) ^ set(heading_lines(c))
                for k2 in changed:
                    if k2 != k and k2 in cause:
                        t2 = (cur['units'].get(k2) or prev['units'].get(k2))['text']
                        if moved & set(heading_lines(t2)):
                            cause[k], why[k] = cause[k2], f'headings moved with {k2}'
                            break
        # 5. The heading above the excerpts at the end, when the excerpt of a law of this version first appears under it.
        if 'ueb-kopf' in changed and 'ueb-kopf' not in cause:
            new = [k for k in changed if k.startswith('ueb-') and k != 'ueb-kopf' and k not in prev['units'] and cause.get(k) == k[4:]]
            if len(new) == 1:
                cause['ueb-kopf'], why['ueb-kopf'] = cause[new[0]], 'heading of the excerpts'
        for k in changed:
            if k not in cause:
                cause[k], why[k] = 'unexplained', 'no footnote names a law of this version'
                problems.append(f'{cur["from"]} {k}')
        groups: dict[str, list[str]] = {}
        for k in changed:
            groups.setdefault(cause[k], []).append(k)
        for law in cur['laws']:
            groups.setdefault(law, [])
        changes.append({'version': cur['version'], 'from': cur['from'], 'url': cur['url'], 'laws': cur['laws'],
                        'groups': groups, 'why': why, 'also': also, 'prev': prev, 'cur': cur})
    return {'act': act, 'meta': meta, 'versions': versions, 'laws': laws, 'changes': changes, 'problems': problems,
            'title': laws[act['lgbl']]['title']}


# ---------------------------------------------------------------- the git repository

def git(repo: Path, *args: str, env: dict | None = None, input: str | None = None) -> str:
    out = subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, encoding='utf-8', env=env, input=input)
    if out.returncode:
        raise SystemExit(f'git {" ".join(args)} failed: {out.stderr}')
    return out.stdout


def last_sunday(year: int, month: int) -> dt.date:
    d = (dt.date(year, month + 1, 1) if month < 12 else dt.date(year + 1, 1, 1)) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def vaduz_offset(day: dt.date) -> int:
    """Hours ahead of UTC on a day in Vaduz. Liechtenstein keeps Swiss time: summer time since 1981, from the last
    Sunday in March to the last Sunday in September until 1995 and in October since 1996."""
    if day.year < 1981:
        return 1
    end = last_sunday(day.year, 9 if day.year < 1996 else 10)
    return 2 if last_sunday(day.year, 3) < day <= end else 1


def commit_date(day: str, seq: list[int]) -> str:
    """Noon in Vaduz on the day. Git cannot record a time before 1970, so changes in force before then are dated
    1 January 1970 (UTC), one second apart in the order they took effect; the real day is in the In-force trailer."""
    d = dt.date.fromisoformat(day)
    if d.year < 1970:
        seq[0] += 1
        return f'@{seq[0]} +0000'
    off = vaduz_offset(d)
    stamp = int(dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone(dt.timedelta(hours=off))).timestamp())
    return f'@{stamp} +0{off}00'


def author_of(law: str) -> tuple[str, str]:
    y, n = law.split('.')
    return lgbl_label(law), f'lgbl-{y}-{int(n):03d}@gesetze-li.invalid'


def unit_label(u: dict) -> str:
    return u['label'] if u['kind'] == 'art' else {'ingress': 'Ingress', 'schluss': 'Schlussteil',
                                                   'ueb-kopf': 'Titel der Übergangsbestimmungen'}.get(u['kind'], u['label'])


ENDS_REPEALED = re.compile(r'(^|\n\n)(\d+\) )?Aufgehoben\.?\n$')


def change_kind(prev: dict | None, cur: dict | None) -> str:
    if prev is None:
        return 'Eingefügt'
    if cur is None:
        return 'Entfernt'
    if ENDS_REPEALED.search(cur['text']) and not ENDS_REPEALED.search(prev['text']) and cur['kind'] == 'art' \
            and section_free(cur['text']).count('\n\n') == 1:
        return 'Aufgehoben'
    return 'Geändert'


def write_unit(repo: Path, slug: str, key: str, unit: dict | None):
    path = repo / slug / file_name(key)
    if unit is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(unit['text'], encoding='utf-8', newline='\n')


PRE_1970 = ['Git kann kein Datum vor 1970 speichern. Dieser Commit ist deshalb auf den 1. Januar 1970 datiert; der Tag',
            'des Inkrafttretens steht unter In-force. (Git cannot record dates before 1970: the real day is In-force.)', '']


def plan_commits(built: list[dict]) -> list[tuple]:
    """Every commit, sorted by day: the first version of each act first on its day, then one commit per law (in LGBl
    order), then the changes no footnote explains."""
    commits = []
    for ai, b in enumerate(built):
        commits.append((b['versions'][0]['from'], ai, 0, '', {'kind': 'start', 'b': b}))
        for ch in b['changes']:
            for law in sorted(ch['groups']):
                if law != 'unexplained':
                    commits.append((ch['from'], ai, 1, law, {'kind': 'law', 'b': b, 'ch': ch, 'law': law}))
            if 'unexplained' in ch['groups']:
                commits.append((ch['from'], ai, 2, '', {'kind': 'unexplained', 'b': b, 'ch': ch}))
    commits.sort(key=lambda c: c[:4])
    return commits


def start_message(b: dict, day: str) -> tuple[tuple[str, str], list[str], list[str]]:
    act, v = b['act'], b['versions'][0]
    short = act['short']
    trailers = []
    if act['lgbl'] in v['laws']:
        lm = b['laws'][act['lgbl']]
        author = author_of(act['lgbl'])
        msg = [f'{short}: {lm["title"]} ({lgbl_label(act["lgbl"])})', '',
               f'Der Erlass in der ersten Fassung, die Lilex veröffentlicht, in Kraft seit {v["from"]}.', '',
               'The act as enacted: the first version Lilex publishes, in force from this day.', '']
        trailers += [f'Dated: {lm["dated"]}'] if lm['dated'] else []
        trailers += [f'Published: {lm["issued"]} ({lgbl_label(act["lgbl"])})', f'In-force: {v["from"]}']
        trailers += [f'Materials: {", ".join(lm["bua"])}'] if lm['bua'] else []
        trailers += [f'Source: {lm["url"]}']
    else:
        author = RDR
        earlier = b['meta']['earlier'] + [b['meta']['rows'][l] for l in v['laws']]
        msg = [f'{short}: Stand am {v["from"]} (älteste Fassung in Lilex)', '',
               f'{b["title"]} (LR {act["lr"]}) in der ältesten Fassung, die Lilex als Text veröffentlicht. Frühere',
               'Fassungen gibt es dort nicht als Text, deshalb ist dieser Commit keinem Gesetz zugeschrieben.',
               'Die Chronologie von Lilex nennt die Erlasse, aus denen dieser Stand hervorgegangen ist:', '']
        msg += [f'- {lgbl_label(r["lgbl"])}, in Kraft seit {r["from"]}: {b["laws"][r["lgbl"]]["title"]}' for r in earlier]
        msg += ['', 'The oldest version Lilex publishes as text. Earlier versions are not available as text, so this',
                'commit is not credited to a law; the laws Lilex lists as having produced it are named above.', '']
        trailers += [f'In-force: {v["from"]}', f'Earlier: {", ".join(lgbl_label(r["lgbl"]) for r in earlier)}']
    trailers += [f'Consolidated: {v["url"]}']
    if day < '1970-01-01':
        msg += PRE_1970
    return author, msg, trailers


def change_message(b: dict, ch: dict, law: str | None, day: str) -> tuple[tuple[str, str], list[str], list[str], list[str]]:
    act = b['act']
    short = act['short']
    keys = sorted(ch['groups'].get(law or 'unexplained', []), key=unit_order)
    units = [(k, ch['prev']['units'].get(k), ch['cur']['units'].get(k)) for k in keys]
    labels = [unit_label(c or p) for k, p, c in units]
    affecting = ', '.join(f'LR {act["lr"]} {l}' for l in labels)
    trailers = []
    if law:
        lm = b['laws'][law]
        author = author_of(law)
        subject = f'{short}: {", ".join(labels) if labels else "Wortlaut unverändert"} ({lgbl_label(law)})'
        if len(subject) > 100:
            subject = f'{short}: {len(labels)} Bestimmungen ({lgbl_label(law)})'
        msg = [subject, '', lm['title'], '']
        by_kind: dict[str, list[str]] = {}
        for (k, p, c), l in zip(units, labels):
            by_kind.setdefault(change_kind(p, c), []).append(l)
        for name in ('Eingefügt', 'Geändert', 'Aufgehoben', 'Entfernt'):
            if name in by_kind:
                msg.append(f'{name}: {", ".join(by_kind[name])}')
        if by_kind:
            msg.append('')
        if not keys:
            msg += ['Lilex nennt dieses Gesetz für die Fassung ab diesem Tag, aber am Wortlaut des Erlasses hat',
                    'sich dadurch nichts geändert (zum Beispiel nur an den Fussnoten).', '',
                    'Lilex lists this law for the version from this day, but none of the words changed.', '']
        shared = [k for k in keys if k in ch['also']]
        if shared:
            others = sorted({x for k in shared for x in ch['also'][k]})
            msg += ['Am selben Tag hat auch ' + ', '.join(lgbl_label(x) for x in others) + ' geändert: '
                    + ', '.join(unit_label(ch['cur']['units'].get(k) or ch['prev']['units'][k]) for k in shared) + '.',
                    'Der konsolidierte Text trennt die beiden Änderungen nicht; beide stehen in diesem Commit.', '',
                    'Another law of the same day also amended these provisions; the consolidated text does not separate',
                    'the two, so both are in this commit, which is credited to the later law.', '']
            trailers += [f'Also-amended-by: {lgbl_label(x)}' for x in others]
        trailers += [f'Dated: {lm["dated"]}'] if lm['dated'] else []
        trailers += [f'Published: {lm["issued"]} ({lgbl_label(law)})', f'In-force: {day}']
        if lm['dated'] and day < lm['dated']:
            msg += [f'Hinweis: Lilex lässt diese Fassung am {day} beginnen, vor dem Datum des Gesetzes ({lm["dated"]}).',
                    f'Auch das gedruckte Landesgesetzblatt nennt als Ausgabetag den {lm["issued"]}. Der Tag ist hier so',
                    'übernommen, wie die Quelle ihn angibt, und nicht berichtigt.', '',
                    f'Note: the source dates this version from {day}, before the date of the law itself ({lm["dated"]}),',
                    'and the printed gazette gives the same issue day. It is kept as the source gives it.', '']
            trailers += ['Date-note: the in-force day in the source is earlier than the date of the law']
        if affecting:
            trailers.append(f'Affecting: {affecting}')
        trailers += [f'Materials: {", ".join(lm["bua"])}'] if lm['bua'] else []
        trailers += [f'Source: {lm["url"]}']
    else:
        author = RDR
        msg = [f'{short}: {", ".join(labels)} (Änderung ohne Nachweis)' if len(labels) < 5 else
               f'{short}: {len(labels)} Bestimmungen (Änderung ohne Nachweis)', '',
               'Der konsolidierte Text in Lilex hat sich an diesem Tag geändert, aber keine Fussnote nennt dafür ein',
               f'Gesetz dieser Fassung ({", ".join(lgbl_label(l) for l in ch["laws"])}). Dieser Commit schreibt die',
               'Änderung deshalb keinem Gesetz zu. Betroffen: ' + ', '.join(labels) + '.', '',
               'Lilex\'s consolidated text changed on this day, but no footnote names a law of this version for it, so',
               'the change is not credited to any law.', '']
        trailers += [f'In-force: {day}', f'Affecting: {affecting}', f'Version-laws: {", ".join(lgbl_label(l) for l in ch["laws"])}']
    trailers += [f'Consolidated: {ch["url"]}']
    if day < '1970-01-01':
        msg += PRE_1970
    return author, msg, trailers, keys


def write_repo(repo: Path, built: list[dict], docs: Path, today: str) -> tuple[list[dict], dict]:
    # The history is rebuilt from scratch each time (it is deterministic), keeping the remote it is pushed to. Git
    # marks its object files read-only, which Windows will not delete without clearing the flag first.
    remote = None
    if (repo / '.git').exists():
        out = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=repo, capture_output=True, text=True)
        remote = out.stdout.strip() or None

    def force(fn, path, _exc):
        os.chmod(path, 0o700)
        fn(path)
    if repo.exists():
        for p in repo.iterdir():
            shutil.rmtree(p, onexc=force) if p.is_dir() else p.unlink()
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, 'init', '-q', '-b', 'main')
    git(repo, 'config', 'core.autocrlf', 'false')
    if remote:
        git(repo, 'remote', 'add', 'origin', remote)

    seq = [0]
    tags: dict[str, str] = {}
    switched = False
    log = []
    for day, ai, _, law, c in plan_commits(built):
        b = c['b']
        slug = b['act']['slug']
        if day > today and not switched:
            # Changes already published but not yet in force live on their own branch, so main is the law today.
            git(repo, 'checkout', '-q', '-b', 'kuenftig')
            switched = True
        if c['kind'] == 'start':
            for key, u in b['versions'][0]['units'].items():
                write_unit(repo, slug, key, u)
            author, msg, trailers = start_message(b, day)
            keys = list(b['versions'][0]['units'])
        else:
            author, msg, trailers, keys = change_message(b, c['ch'], law or None, day)
            for k in keys:
                write_unit(repo, slug, k, c['ch']['cur']['units'].get(k))
        git(repo, 'add', '-A')
        when = commit_date(day, seq)
        env = {**os.environ, 'GIT_AUTHOR_NAME': author[0], 'GIT_AUTHOR_EMAIL': author[1], 'GIT_AUTHOR_DATE': when,
               'GIT_COMMITTER_NAME': COMMITTER[0], 'GIT_COMMITTER_EMAIL': COMMITTER[1], 'GIT_COMMITTER_DATE': when}
        git(repo, 'commit', '-q', '--allow-empty', '--cleanup=verbatim', '-F', '-', env=env,
            input='\n'.join(msg).rstrip('\n') + '\n\n' + '\n'.join(trailers) + '\n')
        head = git(repo, 'rev-parse', 'HEAD').strip()
        tags[f'{slug}/{day}'] = head
        if c['kind'] == 'law' or (c['kind'] == 'start' and b['act']['lgbl'] in b['versions'][0]['laws']):
            lg = law or b['act']['lgbl']
            tags.setdefault(f'lgbl/{lg.replace(".", "-")}', head)
        log.append({'day': day, 'slug': slug, 'kind': c['kind'], 'law': law, 'author': author[0], 'units': len(keys),
                    'clamped': day < '1970-01-01'})
    for name, head in tags.items():
        git(repo, 'tag', '-f', name, head)
    if switched:
        git(repo, 'checkout', '-q', 'main')
    # Documentation, tables, the build scripts and the record of how it was made come last, by Lexifina, dated the
    # day the data was retrieved, so the same data gives the same hashes on any later day.
    for p in sorted(docs.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            dest = repo / p.relative_to(docs)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(p.read_bytes())
    for name in ('build.py', 'reproduce.py', 'check_repo.py'):
        (repo / 'tools' / name).write_bytes((HERE / name).read_bytes())
    write_tables(repo, built)
    from reproduce import write_manifest, write_reproduce
    write_manifest(repo, built, today)
    write_reproduce(repo, built, log, tags, REQUESTS, today)
    git(repo, 'add', '-A')
    when = commit_date(today, seq)
    env = {**os.environ, 'GIT_AUTHOR_NAME': COMMITTER[0], 'GIT_AUTHOR_EMAIL': COMMITTER[1], 'GIT_AUTHOR_DATE': when,
           'GIT_COMMITTER_NAME': COMMITTER[0], 'GIT_COMMITTER_EMAIL': COMMITTER[1], 'GIT_COMMITTER_DATE': when}
    git(repo, 'commit', '-q', '-m', 'Dokumentation, Tabellen, Werkzeuge und REPRODUCE.md', env=env)
    if switched:
        git(repo, 'checkout', '-q', 'kuenftig')
        git(repo, 'merge', '-q', '--no-edit', 'main', env=env)
        git(repo, 'checkout', '-q', 'main')
    return log, tags


def write_tables(repo: Path, built: list[dict]):
    rows = []
    for b in built:
        first = b['versions'][0]
        for r in b['meta']['earlier']:
            rows.append((b, r['lgbl'], r['from'], '', 'vor der ältesten Fassung in Lilex'))
        for law in first['laws']:
            rows.append((b, law, first['from'], len(first['units']),
                         'Grunderlass' if law == b['act']['lgbl'] else 'in der ältesten Fassung in Lilex enthalten'))
        for ch in b['changes']:
            for law in ch['laws']:
                rows.append((b, law, ch['from'], len(ch['groups'].get(law, [])), ''))
    out = []
    for b, law, day, n, note in rows:
        lm = b['laws'][law]
        out.append({'erlass': b['act']['short'], 'lgbl': lgbl_label(law), 'titel': lm['title'], 'datum': lm['dated'] or '',
                    'ausgegeben': lm['issued'] or '', 'in_kraft': day, 'bestimmungen': n, 'hinweis': note,
                    'materialien': ' '.join(lm['bua']), 'quelle': lm['url']})
    out.sort(key=lambda r: (r['in_kraft'], r['erlass'], r['lgbl']))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(out[0]), lineterminator='\n')
    w.writeheader()
    w.writerows(out)
    (repo / 'erlasse.csv').write_text(buf.getvalue(), encoding='utf-8', newline='\n')

    for b in built:
        act = b['act']
        last = b['versions'][-1]
        counts: dict[str, int] = {}
        lastday: dict[str, str] = {}
        for ch in b['changes']:
            for keys in ch['groups'].values():
                for k in keys:
                    counts[k] = counts.get(k, 0) + 1
                    lastday[k] = ch['from']
        out = [f'# {b["title"]}', '',
               f'LR {act["lr"]} · {act["short"]} · {lgbl_label(act["lgbl"])} · <{BASE}/konso/{act["lgbl"]}>', '',
               f'{len(b["versions"])} Fassungen in Lilex, gültig ab {b["versions"][0]["from"]} bis heute (letzte ab {last["from"]}).', '',
               '| Bestimmung | Datei | Änderungen | Zuletzt geändert |', '| --- | --- | ---: | --- |']
        for k in sorted(last['units'], key=unit_order):
            u = last['units'][k]
            out.append(f'| {unit_label(u)} | [{file_name(k)}]({file_name(k)}) | {counts.get(k, 0)} | {lastday.get(k, "")} |')
        (repo / act['slug'] / 'README.md').write_text('\n'.join(out) + '\n', encoding='utf-8', newline='\n')


# ---------------------------------------------------------------- main

def data_day() -> str:
    """The day the cached source data was retrieved (the newest file in the cache), so the documentation commit made by
    a rebuild on any later day carries the same date."""
    files = [p for p in CACHE.iterdir() if p.name != '.gitignore'] if CACHE.exists() else []
    if not files:
        return dt.date.today().isoformat()
    return dt.date.fromtimestamp(max(p.stat().st_mtime for p in files)).isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=str(ROOT.parent / 'liechtenstein-law'))
    ap.add_argument('--offline', action='store_true', help='read only the cache; fail on anything not cached')
    ap.add_argument('--today', default=None, help='the build day (default: the day the cached data was retrieved)')
    ap.add_argument('--verify-rebuild', action='store_true',
                    help='build again into a temporary folder from the cache, compare every hash with --repo, and record the result')
    args = ap.parse_args()
    if args.verify_rebuild:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = subprocess.run([os.sys.executable, '-X', 'utf8', str(HERE / 'build.py'), '--offline', '--repo', tmp]
                                 + (['--today', args.today] if args.today else []), capture_output=True, text=True)
            if out.returncode:
                raise SystemExit(out.stderr)

            def hashes(r):
                log = git(Path(r), 'log', '--format=%H', 'main').split()
                tags = dict(l.split(' ', 1)[::-1] for l in git(Path(r), 'show-ref', '--tags').split('\n') if l)
                return log, tags
            a, b = hashes(args.repo), hashes(tmp)
            same_history = a[0][1:] == b[0][1:]
            rec = {'identical': same_history and a[1] == b[1], 'history_tip': a[0][1], 'commits': len(a[0]) - 1,
                   'tags': len(a[1]), 'main_identical': a[0][0] == b[0][0], 'main': a[0][0], 'rebuilt_main': b[0][0]}
            print(json.dumps(rec, indent=1))
            p = HERE / 'verification.json'
            ver = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
            ver['rebuild'] = {k: rec[k] for k in ('identical', 'history_tip', 'commits', 'tags')}
            p.write_text(json.dumps(ver, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
            # Git marks its objects read-only; clear the flag so the temporary folder can be removed on Windows.
            for f in Path(tmp).rglob('*'):
                os.chmod(f, 0o700)
            raise SystemExit(0 if rec['identical'] else 1)
    built = [build_act(a, args.offline) for a in ACTS]
    today = args.today or data_day()
    for b in built:
        n = sum(len(ks) for ch in b['changes'] for ks in ch['groups'].values())
        print(f'{b["act"]["slug"]}: {len(b["versions"])} versions {b["versions"][0]["from"]}..{b["versions"][-1]["from"]}, '
              f'{len(b["versions"][-1]["units"])} units, {n} unit changes, {len(b["problems"])} unexplained')
        for p in b['problems']:
            print('   unexplained:', p)
    log, tags = write_repo(Path(args.repo), built, HERE / 'repo', today)
    print(f'repo: {len(log)} commits + 1 documentation commit, {len(tags)} tags -> {args.repo}')


if __name__ == '__main__':
    main()
