"""Hand-check helper: a Lilex consolidated text (www.gesetze.li/konso/html/<id>?version=<n>) as plain text, cached.
    python -X utf8 lilex_text.py <id> <version|current> <regex> [width]
prints each match with its surroundings (the footnotes are at the end of the text)."""
import html, os, re, subprocess, sys

ID, VER, PAT = sys.argv[1], sys.argv[2], sys.argv[3]
W = int(sys.argv[4]) if len(sys.argv) > 4 else 250
HERE = os.path.dirname(os.path.abspath(__file__))
if VER == "current":
    p = os.path.join(HERE, f"{ID}.idx.html")
    if not os.path.exists(p):
        subprocess.run(["curl", "-s", "-m", "60", "-A", "Mozilla/5.0", f"https://www.gesetze.li/konso/{ID}", "-o", p], check=True)
    VER = re.search(r"version=(\d+)", open(p, encoding="utf-8", errors="replace").read()).group(1)
    print("current version", VER)
f = os.path.join(HERE, f"{ID}.v{VER}.html")
if not os.path.exists(f):
    subprocess.run(["curl", "-s", "-m", "60", "-A", "Mozilla/5.0", f"https://www.gesetze.li/konso/html/{ID}?version={VER}", "-o", f], check=True)
t = open(f, encoding="utf-8", errors="replace").read()
s = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
for m in re.finditer(PAT, s):
    print("...", s[max(0, m.start() - W):m.end() + W], "\n")
