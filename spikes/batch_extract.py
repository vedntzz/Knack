# Batch spike: run the Q3 extraction over spikes/batch/prs.json plus #75025, resumably.
import json, os, sys
from pathlib import Path

import requests

from q3_extract import GH, answer_json, ask_spark, reasoning_summary

BATCH = Path(__file__).parent / "batch"
PRS = BATCH / "prs.json"
OUT = BATCH / "decisions.jsonl"
EXTRA = [75025]


def gh_headers():
    token = os.environ.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def get_json(path):
    response = requests.get(f"{GH}/{path}", headers=gh_headers(), timeout=20)
    response.raise_for_status()
    return response.json()


def get_all(path):
    items, page = [], 1
    while batch := get_json(f"{path}?per_page=100&page={page}"):
        items += batch
        page += 1
    return items


def fetch_pr_text(number):
    pr, reviews = get_json(f"pulls/{number}"), get_all(f"pulls/{number}/reviews")
    comments = get_all(f"issues/{number}/comments")
    parts = [f"Title: {pr['title']}", f"Author: {pr['user']['login']}", pr.get("body") or ""]
    parts += [f"Review by {r['user']['login']} ({r['state']}): {r.get('body') or ''}" for r in reviews]
    parts += [f"Comment by {c['user']['login']}: {c['body']}" for c in comments]
    return "\n\n".join(parts)


def mark_verbatim(decisions, pr_text):
    for d in decisions:
        for a in d.get("rejected_alternatives", []):
            quote = a.get("quote")
            a["verbatim"] = isinstance(quote, str) and bool(quote) and quote in pr_text
    return decisions


def done_numbers():
    if not OUT.exists():
        return set()
    return {json.loads(line)["number"] for line in OUT.read_text().splitlines() if line.strip()}


def extract(number):
    pr_text = fetch_pr_text(number)
    resp = ask_spark(pr_text)
    decisions = mark_verbatim(answer_json(resp)["decisions"], pr_text)
    flags = [a["verbatim"] for d in decisions for a in d.get("rejected_alternatives", [])]
    return {"number": number, "decisions": decisions, "verbatim": flags,
            "reasoning_summary": reasoning_summary(resp), "usage": resp.get("usage")}


def report():
    rows = [json.loads(line) for line in OUT.read_text().splitlines() if line.strip()]
    flags = [f for r in rows for f in r["verbatim"]]
    print(f"PRs processed: {len(rows)}")
    print(f"PRs with >=1 decision: {sum(1 for r in rows if r['decisions'])}")
    print(f"PRs with >=1 rejected alternative: {sum(1 for r in rows if r['verbatim'])}")
    print(f"quotes verbatim / total: {sum(flags)} / {len(flags)}")


def main():
    if not os.environ.get("MODEL_API_KEY"):
        sys.exit("MODEL_API_KEY is not set")
    numbers = [p["number"] for p in json.loads(PRS.read_text())] + EXTRA
    done = done_numbers()
    todo = [n for n in dict.fromkeys(numbers) if n not in done]
    print(f"{len(done)} already done, {len(todo)} to go", file=sys.stderr)
    for i, number in enumerate(todo, 1):
        try:
            row = extract(number)
        except Exception as e:  # leave it out of the file so a rerun retries it
            print(f"[{i}/{len(todo)}] #{number} FAILED: {e!r}", file=sys.stderr)
            continue
        with OUT.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"[{i}/{len(todo)}] #{number}: {len(row['decisions'])} decisions, "
              f"{sum(row['verbatim'])}/{len(row['verbatim'])} verbatim", file=sys.stderr)
    report()


if __name__ == "__main__":
    main()
