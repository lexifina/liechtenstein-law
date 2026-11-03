"""Independent official-source and append-only gate for current-act batches."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from lxml import html


HERE = Path(__file__).resolve().parent
if HERE.name == "tools":
    SOURCE = HERE.parent
else:
    SOURCE = HERE
sys.path.insert(0, str(SOURCE))
import check_repo  # noqa: E402


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, text=True, encoding="utf-8", capture_output=True)
    if proc.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def lgbl_label(value: str) -> str:
    parts = value.split(".")
    if len(parts) == 2:
        return f"LGBl. {parts[0]} Nr. {int(parts[1])}"
    return f"LGBl. {value}"


def official_images(raw: bytes) -> list[str]:
    doc = html.fromstring(raw.decode("utf-8"))
    base = "https://www.gesetze.li/"
    return [
        urljoin(base, src) for src in doc.xpath("//body//img/@src")
        if "/systexte_bilder/" in urlparse(urljoin(base, src)).path
        and urlparse(urljoin(base, src)).netloc == "www.gesetze.li"
    ]


def valid_image(asset: dict, raw: bytes) -> bool:
    kind = asset.get("format")
    return ((kind == "jpg" and raw.startswith(b"\xff\xd8\xff"))
            or (kind == "png" and raw.startswith(b"\x89PNG\r\n\x1a\n"))
            or (kind == "gif" and raw.startswith((b"GIF87a", b"GIF89a"))))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--part", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    part = json.loads(args.part.read_text(encoding="utf-8"))
    records = part["acts"]
    repo = args.repo.resolve()
    errors: list[str] = []

    if part.get("sha256") != digest(records):
        errors.append("part digest mismatch")
    if git(repo, "merge-base", "--is-ancestor", args.base, "HEAD") != "":
        errors.append("published base is not an ancestor")
    commits = int(git(repo, "rev-list", "--count", f"{args.base}..HEAD"))
    if commits != len(records) + 1:
        errors.append(f"commit count {commits}, expected {len(records) + 1}")
    changed = set(git(repo, "diff", "--name-only", f"{args.base}..HEAD").splitlines())
    protected = [path for path in changed if path.split("/", 1)[0] in {"lv", "vrg", "stghg"}]
    if protected:
        errors.append(f"previously published act files changed: {protected[:5]}")
    commit_messages: dict[str, list[tuple[str, str]]] = {}
    range_log = git(repo, "log", "--format=%H%x1f%B%x1e", f"{args.base}..HEAD")
    for entry in range_log.split("\x1e"):
        entry = entry.strip()
        if not entry or "\x1f" not in entry:
            continue
        commit_id, body = entry.split("\x1f", 1)
        match = re.search(r"(?m)^Act-path: (.+)$", body)
        if match:
            commit_messages.setdefault(match.group(1).strip(), []).append((commit_id, body))

    checked_tokens = 0
    single_file = 0
    checked_images = 0
    image_acts = 0
    for record in records:
        act = record["act"]
        slug = act["slug"]
        cache_path = args.cache / hashlib.sha256(record["source_url"].encode()).hexdigest()
        if not cache_path.exists():
            errors.append(f"{act['id']}: official source body missing from independent cache")
            continue
        raw = cache_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["source_sha256"]:
            errors.append(f"{act['id']}: official source hash mismatch")
            continue
        official = check_repo.official_words(raw)
        repository_texts = []
        expected_paths = set()
        for name in record["file_order"]:
            expected = record["files"][name]
            path = repo / slug / name
            expected_paths.add(Path(name).as_posix())
            if not path.exists():
                errors.append(f"{act['id']}: missing {name}")
                continue
            actual = path.read_text(encoding="utf-8")
            if actual != expected:
                errors.append(f"{act['id']}: staged/source-derived bytes differ for {name}")
            repository_texts.append(actual)
        repository_text = "\n".join(repository_texts)
        image_references = re.findall(
            r"!\[Official source image \d+\]\((assets/[0-9a-f]{64}\.(?:jpg|png|gif))\)",
            repository_text,
        )
        text_for_words = re.sub(
            r"!\[Official source image \d+\]\(assets/[0-9a-f]{64}\.(?:jpg|png|gif)\)",
            "", repository_text,
        )
        repository = check_repo.repo_words(text_for_words)
        if repository != official:
            errors.append(
                f"{act['id']}: official/repository words differ "
                f"({len(official)} official, {len(repository)} repository)"
            )
        else:
            checked_tokens += len(official)
        if record["mode"] == "single-file":
            single_file += 1

        source_images = official_images(raw)
        assets = record.get("assets", [])
        asset_urls = [asset.get("source_url") for asset in assets]
        asset_paths = [asset.get("path") for asset in assets]
        for asset in assets:
            if (not re.fullmatch(r"assets/[0-9a-f]{64}\.(?:jpg|png|gif)", asset.get("path", ""))
                    or Path(asset["path"]).stem != asset.get("sha256")):
                errors.append(f"{act['id']}: asset path is not its SHA-256: {asset.get('path')}")
        if source_images != asset_urls:
            errors.append(f"{act['id']}: official image sequence differs from asset manifest")
        if image_references != asset_paths:
            errors.append(f"{act['id']}: inline image placement sequence differs from asset manifest")
        if source_images:
            image_acts += 1
            if record["mode"] != "single-file-with-assets":
                errors.append(f"{act['id']}: image-bearing act is not placement-preserving single-file text")
        for asset in assets:
            asset_cache = args.cache / hashlib.sha256(asset["source_url"].encode()).hexdigest()
            asset_path = repo / slug / asset["path"]
            if not asset_cache.exists() or not asset_path.exists():
                errors.append(f"{act['id']}: missing official image cache or repository asset {asset['path']}")
                continue
            cached = asset_cache.read_bytes()
            committed = asset_path.read_bytes()
            if (cached != committed or hashlib.sha256(cached).hexdigest() != asset["sha256"]
                    or len(cached) != asset["bytes"] or not valid_image(asset, cached)):
                errors.append(f"{act['id']}: official image bytes/hash/format differ for {asset['path']}")
            else:
                checked_images += 1

        actual_files = {
            path.relative_to(repo / slug).as_posix()
            for path in (repo / slug).rglob("*") if path.is_file() and path.name != "README.md"
        }
        expected_paths.update(asset_paths)
        if actual_files != expected_paths:
            errors.append(f"{act['id']}: repository file set differs from staged record")

        act_commits = commit_messages.get(slug, [])
        if len(act_commits) != 1:
            errors.append(f"{act['id']}: expected one act commit, found {len(act_commits)}")
            continue
        body = act_commits[0][1]
        required = [
            f"In-force: {record['in_force']}", "Kind: start", "First-law: none",
            f"Act-path: {slug}", f"Version-laws: {', '.join(record['source_laws'])}",
            f"Current-text: {record['source_url']}",
        ]
        required.extend(
            f"Published: {item['published']} ({lgbl_label(item['law'])})"
            for item in record["source_law_details"]
        )
        for line in required:
            if line not in body:
                errors.append(f"{act['id']}: commit lacks {line}")

    identities = git(repo, "log", "--format=%ae %ce", f"{args.base}..HEAD").splitlines()
    bad_identities = [line for line in identities if not re.fullmatch(
        r"(?:\S+@gesetze-li\.invalid|\S+@lexifina\.com) \S+@lexifina\.com", line
    )]
    if bad_identities:
        errors.append(f"non-Lexifina commit identities: {bad_identities[:3]}")

    all_asset_paths = [f"{record['act']['slug']}/{asset['path']}"
                       for record in records for asset in record.get("assets", [])]
    if all_asset_paths:
        proc = subprocess.run(
            ["git", "check-attr", "--cached", "binary", "diff", "merge", "text", "--stdin"],
            cwd=repo, input=("\n".join(all_asset_paths) + "\n").encode("utf-8"),
            capture_output=True,
        )
        if proc.returncode:
            errors.append(f"git check-attr failed: {proc.stderr.decode('utf-8', errors='replace').strip()}")
        else:
            attributes: dict[str, dict[str, str]] = {}
            for line in proc.stdout.decode("utf-8").splitlines():
                path, attribute, value = line.split(": ", 2)
                attributes.setdefault(path, {})[attribute] = value
            expected_attributes = {"binary": "set", "diff": "unset", "merge": "unset", "text": "unset"}
            for path in all_asset_paths:
                if attributes.get(path) != expected_attributes:
                    errors.append(f"{path}: binary attributes are {attributes.get(path)}")

    manifest = json.loads((repo / "data" / "current-acts.json").read_text(encoding="utf-8"))
    if manifest.get("base") != args.base or len(manifest.get("acts", [])) != len(records):
        errors.append("current-act manifest does not describe this append")
    corpus = json.loads((repo / "corpus.json").read_text(encoding="utf-8"))
    breadth = corpus.get("breadth_current", {})
    if breadth.get("acts") != len(records) or breadth.get("as_of") != part["as_of"]:
        errors.append("corpus breadth metadata mismatch")

    result = {
        "acts": len(records), "commits": commits, "official_tokens": checked_tokens,
        "single_file_acts": single_file, "image_acts": image_acts,
        "official_images": checked_images, "binary_assets": len(all_asset_paths),
        "errors": len(errors), "details": errors[:50],
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
