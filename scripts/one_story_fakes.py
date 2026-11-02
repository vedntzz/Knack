"""The real knack CLI with Spark and Spark Open swapped for labelled fakes, for one_story.sh.

Every command runs the real code; only the two model clients change. Each fake names
itself fake-* on a host that says no network, so a ruling never claims a real model.
"""

import json
import sys

from knack import cli

HOST = "no network (scripts/one_story_fakes.py)"
QUOTE = "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`."
# The #75025 quotes never mention a customer contract, so both fakes escalate on it.
UNADDRESSED = "contract"
HOLD = {
    "decision": "hold",
    "reply": "The team removed these sort keys instead of aliasing them.",
    "cited_quotes": [QUOTE],
}
ESCALATE = {
    "decision": "escalate",
    "reply": "The quotes say nothing about a customer contract that pins order_by=state.",
    "cited_quotes": [],
}


def ruling_for(prompt: str) -> str:
    # Escalates on the case the quotes never mention; holds on anything else.
    objection = prompt.rpartition("OBJECTION:")[2]
    return json.dumps(ESCALATE if UNADDRESSED in objection else HOLD)


class FakeSpark:
    # argue's Ask, named like SparkRuling; no response id, so its trace is not recorded.
    model = "fake-spark"
    host = HOST
    last_trace_id: str | None = None

    def __call__(self, prompt: str) -> str:
        return ruling_for(prompt)


class FakeSparkOpen:
    # The second opinion, asked only after Spark escalates.
    model = "fake-spark-open"
    host = HOST
    last_trace_id: str | None = None

    def ask(self, prompt: str) -> str:
        return ruling_for(prompt)


def install_fakes() -> None:
    cli.ask_spark = FakeSpark()
    cli.partner_client = lambda extractor: FakeSparkOpen()
    cli.second_opinion_client = lambda: FakeSparkOpen()


if __name__ == "__main__":
    install_fakes()
    sys.exit(cli.main(sys.argv[1:]))
