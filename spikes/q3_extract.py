# Q3 spike: can Muse Spark find #75025's rejected alternative unaided?
import json, os, requests

GH = "https://api.github.com/repos/apache/airflow"
SPARK = "https://api.meta.ai/v1/responses"
PROMPT = """You are reading a merged pull request. Extract the engineering decisions it records,
including any alternatives that were considered and NOT chosen.
Return ONLY JSON, no prose:
{"decisions": [{"decision": str, "why": str, "decided_by": str,
  "rejected_alternatives": [{"alternative": str, "why_rejected": str, "quote": str}]}]}
Rules: every "quote" must be copied verbatim from the text, character for character.
If nothing was rejected, return an empty list. Do not guess.

PR TEXT:
"""

def get_json(path):
    return requests.get(f"{GH}/{path}", timeout=20).json()

def fetch_pr_text():
    pr, reviews = get_json("pulls/75025"), get_json("pulls/75025/reviews")
    comments = get_json("issues/75025/comments")
    parts = [f"Title: {pr['title']}", f"Author: {pr['user']['login']}", pr.get("body") or ""]
    parts += [f"Review by {r['user']['login']} ({r['state']}): {r.get('body') or ''}" for r in reviews]
    parts += [f"Comment by {c['user']['login']}: {c['body']}" for c in comments]
    return "\n\n".join(parts)

def ask_spark(text):
    body = {"model": "muse-spark-1.3", "input": PROMPT + text, "reasoning": {"summary": "auto"}}
    headers = {"Authorization": f"Bearer {os.environ['MODEL_API_KEY']}"}
    response = requests.post(SPARK, headers=headers, json=body, timeout=300)
    response.raise_for_status()
    return response.json()

def items_of_type(resp, kind):
    return [item for item in resp["output"] if item["type"] == kind]

def answer_json(resp):
    text = items_of_type(resp, "message")[0]["content"][0]["text"].strip()
    return json.loads(text.removeprefix("```json").removesuffix("```").strip())

def reasoning_summary(resp):
    return [s.get("text", "") for r in items_of_type(resp, "reasoning") for s in r.get("summary", [])]

def judge(decisions, pr_text):
    alts = [a for d in decisions for a in d["rejected_alternatives"]]
    for a in alts:
        verbatim = a["quote"] in pr_text
        about_alias = "alias" in a["alternative"].lower()
        print(f"- {a['alternative']}\n  quote verbatim: {verbatim} | about aliasing: {about_alias}")
    return any(a["quote"] in pr_text and "alias" in a["alternative"].lower() for a in alts)

if __name__ == "__main__":
    pr_text = fetch_pr_text()
    resp = ask_spark(pr_text)
    json.dump(resp, open("spikes/q3_raw.json", "w"), indent=2)
    print("REASONING:", *reasoning_summary(resp), sep="\n")
    decisions = answer_json(resp)["decisions"]
    print(json.dumps(decisions, indent=2))
    print("\nGATE:", "PASS" if judge(decisions, pr_text) else "FAIL")