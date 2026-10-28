"""Checks the git repository against the official text: every version of every act in Lilex, read back from git with
tools/stand_am.py on the day it took effect, must equal that version's consolidated text.

    python -X utf8 scripts/liechtenstein-law/check_repo.py [--repo ../liechtenstein-law] [--no-record]

Two checks per version, from the cached Lilex HTML (no network):
1. File by file: the act's files in git on that day are exactly the files the build's parser makes from that version's
   HTML (same set of files, same bytes).
2. Word for word: the whole act printed by stand_am.py, with its markdown marks removed, has the same words in the
   same order as the whole official page, read independently of the parser (every text node of the page's body except
   the footnotes, the footnote markers and the Landesgesetzblatt banners).
The result is written to verification.json next to this script (unless --no-record), for REPRODUCE.md.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from lxml import html as lhtml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402

TOKEN = re.compile(r'\w+|[^\w\s]')


BANNER_MARK = 'LGBLBANNERMARK'


def official_segments(raw: bytes) -> list[list[str]]:
    """The page's words split at each Landesgesetzblatt banner after the first: the act itself, then the excerpt of
    each amending law that Lilex prints after it."""
    words = official_words(raw, mark=True)
    segs, cur = [], []
    for w in words:
        if w == BANNER_MARK:
            segs.append(cur)
            cur = []
        else:
            cur.append(w)
    segs.append(cur)
    return [segs[0] + segs[1]] + segs[2:] if len(segs) > 1 else segs


def official_words(raw: bytes, mark: bool = False) -> list[str]:
    """All words of the page, without footnotes, footnote markers (and the commas between them) and banners."""
    doc = lhtml.fromstring(raw.decode('utf-8'))
    body = doc.find('body')
    for e in list(body.iter()):
        if not isinstance(e.tag, str):
            continue
        drop = (e.tag == 'div' and e.get('class') == 'fntext') or \
               (e.tag == 'a' and re.fullmatch(r'#fn\d+', e.get('href') or '')) or \
               (e.tag == 'sup' and re.fullmatch(r'[\s,;]*', e.text_content() or '') and (e.text_content() or '').strip()) or \
               (e.tag == 'table' and 'Landesgesetzblatt' in ' '.join(e.itertext()) and build.BANNER.search(' '.join(e.itertext())))
        if drop:
            if mark and e.tag == 'table':
                e.tail = f' {BANNER_MARK} ' + (e.tail or '')
            tail = e.tail
            parent = e.getparent()
            prev = e.getprevious()
            if tail:
                if prev is not None:
                    prev.tail = (prev.tail or '') + ' ' + tail
                else:
                    parent.text = (parent.text or '') + ' ' + tail
            parent.remove(e)
    return re.findall(r'\w+|[^\w\s]', ' '.join(body.itertext()).replace('\u00a0', ' '))


def stand_order(f: str) -> tuple:
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'repo' / 'tools'))
    import stand_am
    return stand_am.order('x/' + f)


def repo_words(text: str) -> list[str]:
    lines = []
    for l in text.split('\n'):
        l = re.sub(r'^\s*(#+ |- )', '', l)
        lines.append(l.replace(' | ', ' '))   # the separator between the cells of a table row
    return TOKEN.findall(' '.join(lines))


def run(repo: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, 'tools/stand_am.py', *args], cwd=repo, capture_output=True, text=True, encoding='utf-8')


def files_at(repo: str, commit: str, slug: str) -> dict[str, str]:
    """The act's files at a commit, read with one ls-tree and one cat-file --batch (not one git show per file)."""
    out = subprocess.run(['git', 'ls-tree', '-r', commit, f'{slug}/'], cwd=repo, capture_output=True,
                         text=True, encoding='utf-8').stdout.split('\n')
    blobs = []
    for line in out:
        if not line:
            continue
        info, f = line.split('\t', 1)
        if f.endswith('.md') and not f.endswith('/README.md'):
            blobs.append((f[len(slug) + 1:], info.split()[2]))
    if not blobs:
        return {}
    data = subprocess.run(['git', 'cat-file', '--batch'], cwd=repo, input=''.join(f'{sha}\n' for _, sha in blobs).encode(),
                          capture_output=True).stdout
    res, pos = {}, 0
    for name, _ in blobs:
        nl = data.index(b'\n', pos)
        size = int(data[pos:nl].split()[2])
        res[name] = data[nl + 1:nl + 1 + size].decode('utf-8')
        pos = nl + 1 + size + 1
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=str(build.ROOT.parent / 'liechtenstein-law'))
    ap.add_argument('--no-record', action='store_true')
    args = ap.parse_args()
    versions = files = bad = words = wbad = reordered = 0
    per_act = {}
    for act in build.ACTS:
        meta = build.act_meta(act, offline=True)
        for v in meta['versions']:
            raw = build.fetch(f'{build.BASE}/konso/html/{build.uid(act["lgbl"])}?version={v["version"]}', offline=True)
            expected = {build.file_name(u['key']): u['text'] for u in build.read_version(raw)['units']}
            commit = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, "tools"); import stand_am; '
                                     f'print(stand_am.commit_on("{v["from"]}", "{act["slug"]}"))'],
                                    cwd=args.repo, capture_output=True, text=True).stdout.strip()
            got = files_at(args.repo, commit, act['slug']) if commit else {}
            versions += 1
            per_act[act['slug']] = per_act.get(act['slug'], 0) + 1
            files += len(expected)
            if got != expected:
                bad += 1
                diff = sorted(set(got) ^ set(expected)) or [k for k in expected if got.get(k) != expected[k]]
                print(f'MISMATCH {act["slug"]} {v["from"]}: {diff[:5]}')
            whole = run(args.repo, v['from'], act['slug'])
            words += 1
            ow, rw = official_words(raw), repo_words(whole.stdout)
            if not whole.returncode and ow != rw:
                # Lilex prints the excerpts of amending laws in its own order (by the day they took effect), the reader
                # in the order of their LGBl numbers: compare the act, then the excerpts as a set.
                segs = official_segments(raw)
                main_files = [k for k in sorted(got, key=lambda f: stand_order(f)) if not re.fullmatch(r'uebergang/\d{4}-\d{3}\.md', k)]
                excerpts = [k for k in got if re.fullmatch(r'uebergang/\d{4}-\d{3}\.md', k)]
                if segs[0] == repo_words('\n'.join(got[k] for k in main_files)) and \
                        sorted(segs[1:]) == sorted(repo_words(got[k]) for k in excerpts):
                    reordered += 1
                    continue
            if whole.returncode or ow != rw:
                wbad += 1
                i = next((i for i, (a, b) in enumerate(zip(ow, rw)) if a != b), min(len(ow), len(rw)))
                print(f'WORDS {act["slug"]} {v["from"]}: official {len(ow)} vs repo {len(rw)} words; first difference at '
                      f'{i}: {" ".join(ow[max(0, i - 5):i + 5])!r} / {" ".join(rw[max(0, i - 5):i + 5])!r}')
    print(f'{versions} versions checked ({files} files), {bad} mismatches; {words} versions word for word, {wbad} mismatches '
          f'({reordered} of them equal only with the excerpts of amending laws in LGBl order)')
    print('per act:', per_act)
    if not args.no_record:
        p = HERE / 'verification.json'
        rec = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        rec['check'] = {'versions': versions, 'files': files, 'mismatches': bad, 'wordcheck': words, 'word_mismatches': wbad, 'excerpts_reordered': reordered,
                        'per_act': per_act}
        p.write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    raise SystemExit(1 if bad or wbad else 0)


if __name__ == '__main__':
    main()
