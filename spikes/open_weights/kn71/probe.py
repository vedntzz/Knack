# KN-71 timing probe: one blind-judge prompt to local Glimmer and to Baseten Spark Open.
import difflib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from knack.bench.blind import blind_prompt, parse_blind
from knack.bench.classify import rule_and_alternatives

OUT = Path(__file__).parent
ROOT = OUT.parents[2]
TARGETS = {
    "glimmer-local": ("http://localhost:11434/v1/chat/completions", "muse-glimmer:30b", None),
    "spark-open-baseten": (
        "https://inference.baseten.co/v1/chat/completions",
        "meta-models/muse-spark-open-1026",
        "BASETEN_API_KEY",
    ),
}


def probe_prompt() -> str:
    # Ticket fastapi-16062 with the one surviving bench edit (1030c, not pilot) as diff.
    ticket = next(json.loads(l) for l in open(ROOT / "bench/tickets.jsonl") if "fastapi-16062" in l)
    edit = json.load(open(ROOT / "bench/misses/16062-none-2.edit.json"))
    diff = "".join(difflib.unified_diff(edit["before"].splitlines(True), edit["after"].splitlines(True), "a/" + edit["file"], "b/" + edit["file"]))
    _, alternatives = rule_and_alternatives(ROOT / "data/registry/fastapi.json", "fastapi-16062")
    return blind_prompt(ticket["ticket"], alternatives, diff)


def call(name: str, prompt: str, run: int) -> None:
    url, model, key_env = TARGETS[name]
    body = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    headers = {"Content-Type": "application/json"}
    if key_env:
        headers["Authorization"] = f"Bearer {os.environ[key_env]}"
    (OUT / f"{name}.{run}.request.json").write_text(json.dumps({"url": url, "body": body}, indent=1))
    started = time.monotonic()
    with urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), headers), timeout=1800) as r:
        raw = r.read()
    seconds = time.monotonic() - started
    (OUT / f"{name}.{run}.response.json").write_bytes(raw)
    data = json.loads(raw)
    label = parse_blind(data["choices"][0]["message"].get("content") or "")
    print(json.dumps({"target": name, "run": run, "seconds": round(seconds, 1), "label": label, "usage": data.get("usage")}))


if __name__ == "__main__":
    prompt = probe_prompt()
    for run in range(int(sys.argv[2]) if len(sys.argv) > 2 else 1):
        call(sys.argv[1], prompt, run)
