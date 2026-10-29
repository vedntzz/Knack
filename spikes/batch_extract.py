# Batch spike: run the Q3 extraction over a repo's prs.json (plus Airflow's #75025), resumably.
import json, os, sys

import requests

from batch_repo import Batch, repo_parser
from q3_extract import answer_json, ask_spark, reasoning_summary

EXTRA = {"apache/airflow": [75025]}


def parse_args(argv=None):
    return repo_parser("extract decisions from a repo's selected PRs").parse_args(argv)


def extras(batch):
    return EXTRA.get(batch.repo, [])


def gh_headers():
    token = os.environ.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def get_json(batch, path):
    response = requests.get(f"{batch.api}/{path}", headers=gh_headers(), timeout=20)
    response.raise_for_status()
    return response.json()


def get_all(batch, path):
    items, page = [], 1
    while chunk := get_json(batch, f"{path}?per_page=100&page={page}"):
        items += chunk
        page += 1
    return items


def fetch_pr_text(batch, number):
    pr, reviews = get_json(batch, f"pulls/{number}"), get_all(batch, f"pulls/{number}/reviews")
    comments = get_all(batch, f"issues/{number}/comments")
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


def done_numbers(batch):
    if not batch.decisions.exists():
        return set()
    return {json.loads(line)["number"] for line in batch.decisions.read_text().splitlines() if line.strip()}


def extract(batch, number):
    pr_text = fetch_pr_text(batch, number)
    resp = ask_spark(pr_text)
    decisions = mark_verbatim(answer_json(resp)["decisions"], pr_text)
    flags = [a["verbatim"] for d in decisions for a in d.get("rejected_alternatives", [])]
    return {"number": number, "decisions": decisions, "verbatim": flags,
            "reasoning_summary": reasoning_summary(resp), "usage": resp.get("usage")}


def report(batch):
    rows = [json.loads(line) for line in batch.decisions.read_text().splitlines() if line.strip()]
    flags = [f for r in rows for f in r["verbatim"]]
    print(f"PRs processed: {len(rows)}")
    print(f"PRs with >=1 decision: {sum(1 for r in rows if r['decisions'])}")
    print(f"PRs with >=1 rejected alternative: {sum(1 for r in rows if r['verbatim'])}")
    print(f"quotes verbatim / total: {sum(flags)} / {len(flags)}")


def main(argv=None):
    batch = Batch(parse_args(argv).repo)
    if not os.environ.get("MODEL_API_KEY"):
        sys.exit("MODEL_API_KEY is not set")
    numbers = [p["number"] for p in json.loads(batch.prs.read_text())] + extras(batch)
    done = done_numbers(batch)
    todo = [n for n in dict.fromkeys(numbers) if n not in done]
    print(f"{len(done)} already done, {len(todo)} to go", file=sys.stderr)
    for i, number in enumerate(todo, 1):
        try:
            row = extract(batch, number)
        except Exception as e:  # leave it out of the file so a rerun retries it
            print(f"[{i}/{len(todo)}] #{number} FAILED: {e!r}", file=sys.stderr)
            continue
        with batch.decisions.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"[{i}/{len(todo)}] #{number}: {len(row['decisions'])} decisions, "
              f"{sum(row['verbatim'])}/{len(row['verbatim'])} verbatim", file=sys.stderr)
    report(batch)


if __name__ == "__main__":
    main()
