"""Prints an act, or one provision of it, as it stood on a given day, from this repository's history.

    python tools/stand_am.py 2003-09-15 lv 7          # Art. 7 of the Constitution on 15 September 2003
    python tools/stand_am.py 1950-01-01 lv            # the whole Constitution on 1 January 1950
    python tools/stand_am.py 2012-01-01 vrg schluss   # the closing part of the VRG

Each commit carries the day its change took effect in an `In-force:` trailer (git cannot store dates before 1970, so
the trailer, not the commit date, is the source of truth). The text in force on a day is the last commit on or before
it. Changes published but not yet in force would be on the branch "kuenftig"; a date after today reads from there.
Standard library only.
"""
import datetime as dt
import re
import subprocess
import sys

LATIN = ['bis', 'ter', 'quater', 'quinquies', 'sexies', 'septies', 'octies', 'novies', 'decies']


def git(*args: str) -> str:
    return subprocess.run(['git', *args], capture_output=True, text=True, encoding='utf-8', check=True).stdout


def order(path: str) -> tuple:
    """The order of the act's files: ingress, articles by number, closing part, the excerpts of amending laws."""
    name = path.split('/', 1)[1]
    if name == 'ingress.md':
        return (0, 0, 0, '')
    m = re.fullmatch(r'art-(\d+)([a-z]*)(.*)\.md', name)
    if m:
        suf = m.group(2)
        rank = 0 if not suf else (LATIN.index(suf) + 2 if suf in LATIN else ord(suf[0]) - 96 if len(suf) == 1 else 50)
        return (1, int(m.group(1)), rank, m.group(3))
    if name.startswith('schluss'):
        return (2, 0, 0, name)
    return (3, 0, 0, name)


def file_for(key: str) -> str:
    m = re.fullmatch(r'(\d+)(.*)', key)
    if m:
        return f'art-{int(m.group(1)):03d}{m.group(2)}.md'
    return key if key.endswith('.md') else f'{key}.md'


def commit_on(day: str, act: str) -> str:
    branch = 'kuenftig' if day > dt.date.today().isoformat() and git('branch', '--list', 'kuenftig').strip() else 'main'
    out = git('log', '--format=%H%x09%(trailers:key=In-force,valueonly,separator=)', branch, '--', act)
    for line in out.splitlines():
        h, _, d = line.partition('\t')
        if d.strip() and d.strip() <= day:
            return h
    return ''


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    day, act = sys.argv[1], sys.argv[2]
    dt.date.fromisoformat(day)
    commit = commit_on(day, act)
    if not commit:
        sys.exit(f'{act} is not in the record on {day}.')
    if len(sys.argv) > 3:
        name = file_for(sys.argv[3])
        try:
            sys.stdout.write(git('show', f'{commit}:{act}/{name}'))
        except subprocess.CalledProcessError:
            sys.exit(f'{act}/{name} was not in the text on {day}.')
        return
    files = [f for f in git('ls-tree', '-r', '--name-only', commit, f'{act}/').split('\n')
             if f.endswith('.md') and not f.endswith('/README.md')]
    for f in sorted(files, key=order):
        sys.stdout.write(git('show', f'{commit}:{f}') + '\n')


if __name__ == '__main__':
    main()
