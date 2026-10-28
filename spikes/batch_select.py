"""Spike: pick 50 recent merged apache/airflow PRs worth replaying through the guard."""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO = "apache/airflow"
API = "https://api.github.com"
OUT = Path(__file__).parent / "batch" / "prs.json"
TARGET = 50
MIN_BODY = 400
WINDOW_DAYS = 7
DOC_SUFFIXES = (".rst", ".md", ".txt")


def session():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    return s


def get(s, url, **params):
    for _ in range(5):
        r = s.get(url, params=params, timeout=30)
        if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
            wait = int(r.headers.get("X-RateLimit-Reset", time.time() + 60)) - time.time()
            print(f"rate limited, sleeping {int(wait) + 1}s", file=sys.stderr)
            time.sleep(max(wait, 0) + 1)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"gave up on {url}")


def search_window(s, start, end):
    # Search caps at 1000 results, so a week-wide window keeps us well under it.
    q = f"repo:{REPO} is:pr is:merged merged:{start:%Y-%m-%dT%H:%M:%SZ}..{end:%Y-%m-%dT%H:%M:%SZ}"
    items, page = [], 1
    while True:
        data = get(s, f"{API}/search/issues", q=q, per_page=100, page=page)
        items += data["items"]
        if len(data["items"]) < 100 or len(items) >= 1000:
            return items
        page += 1


def is_test(path):
    name = path.rsplit("/", 1)[-1]
    return path.startswith("tests/") or "/tests/" in path or name.startswith("test_") or name == "conftest.py"


def is_doc(path):
    return path.startswith("docs/") or "/docs/" in path or path.endswith(DOC_SUFFIXES)


def pr_files(s, number):
    files, page = [], 1
    while True:
        batch = get(s, f"{API}/repos/{REPO}/pulls/{number}/files", per_page=100, page=page)
        files += batch
        if len(batch) < 100:
            return files
        page += 1


def qualifies(files):
    paths = [f["filename"] for f in files]
    py = [p for p in paths if p.endswith(".py")]
    only_tests_or_docs = all(is_test(p) or is_doc(p) for p in paths)
    return 1 <= len(py) <= 5 and not only_tests_or_docs


def record(s, number, files):
    pr = get(s, f"{API}/repos/{REPO}/pulls/{number}")
    return {
        "number": number,
        "title": pr["title"],
        "author": pr["user"]["login"],
        "merged_at": pr["merged_at"],
        "base_sha": pr["base"]["sha"],
        "head_sha": pr["head"]["sha"],
        "changed_files": [{"filename": f["filename"], "status": f["status"]} for f in files],
    }


def main():
    s = session()
    now = datetime.now(timezone.utc)
    floor = now - timedelta(days=365)
    kept, seen, end = [], 0, now
    while end > floor and len(kept) < TARGET:
        start = max(end - timedelta(days=WINDOW_DAYS), floor)
        items = search_window(s, start, end)
        items.sort(key=lambda i: i["pull_request"]["merged_at"], reverse=True)
        for item in items:
            if len(kept) >= TARGET:
                break
            seen += 1
            if len(item.get("body") or "") <= MIN_BODY:
                continue
            files = pr_files(s, item["number"])
            if qualifies(files):
                kept.append(record(s, item["number"], files))
                print(f"  kept #{item['number']} ({len(kept)}/{TARGET})", file=sys.stderr)
        end = start
    kept.sort(key=lambda p: p["merged_at"], reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(kept, indent=2) + "\n")
    print(f"scanned {seen} merged PRs, kept {len(kept)} -> {OUT}")


if __name__ == "__main__":
    main()
