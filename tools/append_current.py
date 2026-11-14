"""Append source-checked breadth-first current acts to a published clone."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


IDENTITY = {
    "GIT_AUTHOR_NAME": "Lexifina",
    "GIT_AUTHOR_EMAIL": "liechtenstein-law@lexifina.com",
    "GIT_COMMITTER_NAME": "Lexifina",
    "GIT_COMMITTER_EMAIL": "liechtenstein-law@lexifina.com",
}


def run(repo: Path, *args: str, stdin: str | None = None) -> str:
    env = os.environ.copy()
    env.update(IDENTITY)
    proc = subprocess.run(
        ["git", "-c", "gc.auto=0", *args], cwd=repo, env=env, input=stdin,
        text=True, encoding="utf-8", capture_output=True,
    )
    if proc.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def lgbl_label(value: str) -> str:
    match = re.fullmatch(r"(\d{4})\.(\d+)(?:\.(\d+))?", value)
    if not match:
        raise ValueError(f"invalid LGBl identifier: {value}")
    if match.group(3) is not None:
        return f"LGBl. {value}"
    return f"LGBl. {match.group(1)} Nr. {int(match.group(2))}"


def git_day(day: str, ordinal: int) -> str:
    parsed = dt.date.fromisoformat(day)
    if parsed < dt.date(1970, 1, 1):
        return f"1970-01-01T12:{ordinal // 60 % 60:02d}:{ordinal % 60:02d}+0100"
    return f"{day}T12:00:{ordinal % 60:02d}+0100"


def fast_import_day(day: str, ordinal: int) -> str:
    parsed = dt.date.fromisoformat(day)
    if parsed < dt.date(1970, 1, 1):
        parsed = dt.date(1970, 1, 1)
    moment = dt.datetime.combine(
        parsed, dt.time(12, (ordinal // 60) % 60, ordinal % 60),
        tzinfo=dt.timezone(dt.timedelta(hours=1)),
    )
    return f"{int(moment.timestamp())} +0100"


def validate_record(record: dict) -> None:
    act = record["act"]
    required = {"id", "lgbl", "lr", "slug", "source_url", "title"}
    if not required <= set(act):
        raise ValueError(f"{act.get('id', '?')}: incomplete act metadata")
    if record.get("first_law") is not None or record.get("label") != "oldest version available":
        raise ValueError(f"{act['id']}: not a breadth-first first version")
    dt.date.fromisoformat(record["in_force"])
    details = record.get("source_law_details")
    if not details or sorted(item["law"] for item in details) != record.get("source_laws"):
        raise ValueError(f"{act['id']}: source-law details do not match version laws")
    for item in details:
        lgbl_label(item["law"])
        dt.date.fromisoformat(item["published"])
        if not item["title"]:
            raise ValueError(f"{act['id']}: empty source-law title")
    files = record.get("files", {})
    if not files or any(Path(name).is_absolute() or ".." in Path(name).parts for name in files):
        raise ValueError(f"{act['id']}: unsafe or empty file set")
    if record.get("file_order") is None or set(record["file_order"]) != set(files):
        raise ValueError(f"{act['id']}: file order does not cover the file set")
    gate = record.get("gate", {})
    if not gate.get("two_identical_parses") or not gate.get("word_for_word"):
        raise ValueError(f"{act['id']}: source gate is incomplete")
    assets = record.get("assets", [])
    if gate.get("official_images") != len(assets):
        raise ValueError(f"{act['id']}: official image count does not match assets")
    if assets and (not gate.get("assets_complete") or not gate.get("placements_complete")):
        raise ValueError(f"{act['id']}: image completeness gate is incomplete")
    for asset in assets:
        if (not re.fullmatch(r"assets/[0-9a-f]{64}\.(?:jpg|png|gif)", asset.get("path", ""))
                or not re.fullmatch(r"[0-9a-f]{64}", asset.get("sha256", ""))
                or Path(asset["path"]).stem != asset["sha256"]
                or asset.get("bytes", 0) < 1):
            raise ValueError(f"{act['id']}: invalid official asset metadata")


def act_readme(record: dict) -> str:
    act = record["act"]
    details = record["source_law_details"]
    rows = "\n".join(
        f"- {lgbl_label(item['law'])}, issued {item['published']}: {item['title']}"
        for item in details
    )
    file_rows = "\n".join(f"- `{name}`" for name in record["file_order"])
    asset_note = ""
    if record.get("assets"):
        asset_note = (
            f"\nThe official text contains {len(record['assets'])} embedded image(s). Their original bytes are "
            "preserved under `assets/` and referenced at their source positions in `text.md`.\n"
        )
    return (
        f"# {act['title']}\n\n"
        f"LR {act['lr']} · LGBl. {act['lgbl']} · <{act['source_url']}>\n\n"
        f"One current consolidated version is recorded, effective {record['in_force']}. "
        "It is labelled as the oldest version available; earlier history is not included in this breadth append.\n\n"
        "The official chronology names the following source law or laws for this version:\n\n"
        f"{rows}\n\n"
        f"Text layout: {record['mode']}. Files:\n\n{file_rows}\n{asset_note}"
    )


def message(record: dict) -> str:
    act = record["act"]
    details = record["source_law_details"]
    published = "\n".join(
        f"Published: {item['published']} ({lgbl_label(item['law'])})" for item in details
    )
    return (
        f"{act['title']} (LR {act['lr']}): oldest version available\n\n"
        "Current consolidated text published by the Rechtsdienst der Regierung. "
        "Earlier versions are deferred to the history pass.\n\n"
        f"{published}\n"
        f"In-force: {record['in_force']}\n"
        "Kind: start\n"
        "First-law: none\n"
        f"Act-path: {act['slug']}\n"
        f"Version-laws: {', '.join(record['source_laws'])}\n"
        f"Source: {act['source_url']}\n"
        f"Consolidated: {act['source_url']}\n"
        f"Current-text: {record['source_url']}\n"
    )


def law_author(record: dict) -> tuple[str, str]:
    laws = record["source_laws"]
    if len(laws) == 1:
        value = laws[0]
        return lgbl_label(value), f"lgbl-{value.replace('.', '-')}@gesetze-li.invalid"
    return "Rechtsdienst der Regierung (Lilex)", "rdr@gesetze-li.invalid"


def fast_import_records(repo: Path, records: list[dict], base: str, part_path: Path) -> None:
    env = os.environ.copy()
    env.update(IDENTITY)
    proc = subprocess.Popen(
        ["git", "-c", "gc.auto=0", "fast-import", "--quiet"], cwd=repo, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None

    def write(value: str | bytes) -> None:
        proc.stdin.write(value.encode("utf-8") if isinstance(value, str) else value)

    def data_bytes(raw: bytes) -> None:
        write(f"data {len(raw)}\n")
        write(raw)
        write(b"\n")

    def data(value: str) -> None:
        data_bytes(value.encode("utf-8"))

    job = part_path.resolve().parents[1] if part_path.parent.name == "current-parts" else None
    cache = job / "lane-cache" if job else None
    input_repo = part_path.resolve().parent.parent if part_path.name == "breadth-input.json" else None

    def asset_bytes(record: dict, asset: dict) -> bytes:
        candidates = []
        if cache:
            candidates.append(cache / hashlib.sha256(asset["source_url"].encode()).hexdigest())
        if input_repo:
            candidates.append(input_repo / record["act"]["slug"] / asset["path"])
        for candidate in candidates:
            if candidate.exists():
                raw = candidate.read_bytes()
                if hashlib.sha256(raw).hexdigest() == asset["sha256"] and len(raw) == asset["bytes"]:
                    return raw
        raise ValueError(f"{record['act']['id']}: official asset bytes unavailable or changed: {asset['source_url']}")

    try:
        write("feature done\n")
        for ordinal, record in enumerate(records, 1):
            act = record["act"]
            stamp = fast_import_day(record["in_force"], ordinal - 1)
            author_name, author_email = law_author(record)
            write("commit refs/heads/main\n")
            write(f"mark :{ordinal}\n")
            write(f"author {author_name} <{author_email}> {stamp}\n")
            write(f"committer Lexifina <liechtenstein-law@lexifina.com> {stamp}\n")
            data(message(record))
            write(f"from {base if ordinal == 1 else ':' + str(ordinal - 1)}\n")
            all_files = dict(record["files"])
            all_files["README.md"] = act_readme(record)
            for name, content in all_files.items():
                path = f"{act['slug']}/{name}"
                if not re.fullmatch(r"[A-Za-z0-9_./-]+", path):
                    raise ValueError(f"fast-import path requires quoting: {path}")
                write(f"M 100644 inline {path}\n")
                data(content)
            for asset in record.get("assets", []):
                path = f"{act['slug']}/{asset['path']}"
                write(f"M 100644 inline {path}\n")
                data_bytes(asset_bytes(record, asset))
        write("done\n")
        proc.stdin.close()
        stdout = proc.stdout.read() if proc.stdout else b""
        stderr = proc.stderr.read() if proc.stderr else b""
        code = proc.wait()
        if code:
            raise RuntimeError(
                f"git fast-import failed ({code}): {stderr.decode('utf-8', 'replace').strip()} "
                f"{stdout.decode('utf-8', 'replace').strip()}"
            )
    except BaseException:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        raise

    # fast-import updates the branch ref, not the checked-out index/worktree.
    # This append deletes nothing, so checking out all current index entries is sufficient.
    run(repo, "read-tree", "HEAD")
    run(repo, "checkout-index", "-a", "-f")


def update_docs(repo: Path, part: dict, base: str) -> None:
    acts = part["acts"]
    manifest = []
    for record in acts:
        act = record["act"]
        manifest.append({
            "id": act["id"], "slug": act["slug"], "lr": act["lr"],
            "lgbl": act["lgbl"], "title": act["title"],
            "in_force": record["in_force"], "version": record["version"],
            "available_versions": record["available_versions"], "mode": record["mode"],
            "source_url": record["source_url"], "source_sha256": record["source_sha256"],
            "source_law_details": record["source_law_details"],
            "assets": record.get("assets", []),
            "files": record["file_order"],
        })
    data = repo / "data"
    data.mkdir(exist_ok=True)
    (data / "current-acts.json").write_text(
        json.dumps({"as_of": part["as_of"], "base": base, "acts": manifest},
                   ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (data / "breadth-input.json").write_text(
        json.dumps(part, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    corpus_path = repo / "corpus.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    corpus["name"] = "Liechtenstein: current national acts and selected full histories"
    corpus["checked_on"] = part["as_of"]
    corpus["record_to"] = max(corpus.get("record_to", part["as_of"]), part["as_of"])
    corpus["record_note"] = (
        f"The breadth append contains {len(acts)} source-checked current-text acts as at {part['as_of']}; "
        "LV, VRG and StGHG retain their published histories."
    )
    corpus["breadth_current"] = {
        "as_of": part["as_of"], "acts": len(acts), "official_listing": 3689,
        "label": "oldest version available", "manifest": "data/current-acts.json",
    }
    corpus_path.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (repo / ".gitattributes").write_text(
        "**/assets/*.jpg binary\n**/assets/*.png binary\n**/assets/*.gif binary\n",
        encoding="utf-8", newline="\n",
    )

    readme_path = repo / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    # Since 2026-11-14 README.md is the German README on the serbia-law model (README.en.md beside it), with its counts written by hand: it is left as it is.
    if '](README.en.md)' not in readme:
        marker = "## Current-text breadth append"
        if marker in readme:
            readme = readme.split(marker, 1)[0].rstrip() + "\n\n"
        readme += (
            f"{marker}\n\n"
            f"This repository also records {len(acts)} further current consolidated acts from the official Lilex "
            f"listing as at {part['as_of']}. Each is one source-dated version labelled “oldest version available”; "
            "earlier versions are deferred. The source chronology supplies each effective date and gazette issue date. "
            "Structured acts are split into provision files; acts the reader cannot safely split are retained as a "
            "single complete text file. Official embedded images are preserved as original assets and referenced at "
            "their source positions. Metadata is in `data/current-acts.json`.\n"
        )
        readme_path.write_text(readme, encoding="utf-8")

    tools = repo / "tools"
    tools.mkdir(exist_ok=True)
    here = Path(__file__).resolve().parent
    for name in ("append_current.py", "check_current.py"):
        source = here / name
        if source.exists():
            shutil.copy2(source, tools / name)

    reproduce = repo / "REPRODUCE.md"
    existing = reproduce.read_text(encoding="utf-8")
    marker = "## Breadth-first current-text append"
    if marker in existing:
        existing = existing.split(marker, 1)[0].rstrip() + "\n\n"
    existing += f"""{marker}

The repository was later extended from published base `{base}` with {len(acts)} current-text acts observed on
{part['as_of']}. The exact deterministic input is `data/breadth-input.json`; it contains each official source URL and
SHA-256, version and gazette dates, ordered text files, and the URL, SHA-256, size, format and placement path of every
official embedded image. The original image bytes are also present as `assets/<sha256>.<ext>` in each affected act,
and `.gitattributes` declares those files binary.

To reproduce the append, first make a separate clone fixed at the base above. From this final repository clone run:

```sh
python -X utf8 tools/append_current.py --part data/breadth-input.json --repo ../rebuilt --expected-base {base}
python -X utf8 tools/check_current.py --part data/breadth-input.json --repo ../rebuilt --cache <fresh-official-cache> --base {base}
```

`data/breadth-input.json` is the complete append input rather than a private staging reference: it records the ordered
text of every committed law file and all source/date/asset metadata needed by the builder. The committed act folders
supply the exact asset bytes, checked against the hashes in that input. For an independent source recheck, obtain the
official URLs listed in the input into a new directory and pass that directory as `<fresh-official-cache>` above.
The checker requires every HTML and image SHA-256 to match, all source dates and text words to match, and every official
image to have the same ordered inline reference and committed bytes. A second clean append must produce the identical
head.

This breadth append and its image-completeness repair were built by an OpenAI GPT-6 worker in Codex. The model wrote
and ran collection/build/check tooling and documentation. It did not write, edit or OCR legal text or official
images; all law text and asset bytes come from Lilex, and no model is called by the deterministic build.
"""
    reproduce.write_text(existing, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--part", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--expected-base", required=True)
    args = parser.parse_args()
    if args.part.resolve().parent.name == "current-parts":
        job = args.part.resolve().parents[1]
    else:
        job = args.repo.resolve().parent
    with (job / "pids.txt").open("a", encoding="utf-8") as pid_file:
        pid_file.write(f"{os.getpid()} Python append_current\n")
    part = json.loads(args.part.read_text(encoding="utf-8"))
    repo = args.repo.resolve()
    base = run(repo, "rev-parse", "HEAD")
    if base != args.expected_base:
        raise RuntimeError(f"scratch base {base} is not expected {args.expected_base}")
    if part.get("sha256") != digest(part.get("acts")):
        raise ValueError("part digest does not match its acts")
    if part.get("repository_gate") != "pending" or part.get("publication") != "held":
        raise ValueError("part is not held for the repository gate")
    records = part.get("acts", [])
    if len(records) < 500:
        raise ValueError("breadth append must contain at least 500 acts")
    slugs = [record["act"]["slug"] for record in records]
    if len(slugs) != len(set(slugs)):
        raise ValueError("duplicate act paths")
    if any((repo / slug).exists() for slug in slugs):
        raise ValueError("an appended act path already exists")

    for record in records:
        validate_record(record)
        act = record["act"]
    fast_import_records(repo, records, base, args.part)

    update_docs(repo, part, base)
    run(repo, "add", "--", "README.md", "REPRODUCE.md", "corpus.json",
        ".gitattributes", "data/current-acts.json", "data/breadth-input.json", "tools")
    env = os.environ.copy()
    env.update(IDENTITY)
    env["GIT_AUTHOR_DATE"] = f"{part['as_of']}T12:00:00+0100"
    env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"]
    docs_message = (
        f"Document {len(records)} current-text acts\n\n"
        "Adds the source and date manifest for the breadth-first append. No previously published law text changes.\n\n"
        f"In-force: {part['as_of']}\nKind: documentation\n"
    )
    proc = subprocess.run(
        ["git", "-c", "gc.auto=0", "commit", "-q", "--cleanup=verbatim", "-F", "-"],
        cwd=repo, env=env, input=docs_message, text=True, encoding="utf-8", capture_output=True,
    )
    if proc.returncode:
        raise RuntimeError(f"documentation commit failed: {proc.stderr.strip()}")
    print(json.dumps({"base": base, "head": run(repo, "rev-parse", "HEAD"),
                      "acts": len(records), "commits": len(records) + 1}, sort_keys=True))


if __name__ == "__main__":
    main()
