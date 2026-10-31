"""Leak check: Spark Open sees only the ticket text and guesses the fix."""
import json, os, sys
from pathlib import Path
from knack.pipeline.spark_open import SparkOpenApi

ASK = "Here is a bug report.\n\n{ticket}\n\nGuess the code change that fixes it. Be concrete and brief (under 150 words)."
api = SparkOpenApi(os.environ["BASETEN_API_KEY"])
out = Path(sys.argv[2])
for line in Path(sys.argv[1]).read_text().splitlines():
    t = json.loads(line)
    if len(sys.argv) > 3 and t["id"] not in sys.argv[3:]:
        continue
    answer = api.ask(ASK.format(ticket=t["ticket"]))
    with out.open("a") as f:
        f.write(json.dumps({"id": t["id"], "ticket": t["ticket"], "guess": answer}) + "\n")
    print("=====", t["id"], "\n", answer, "\n")
