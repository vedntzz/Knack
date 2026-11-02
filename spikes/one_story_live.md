# One story, live (KN-96b)

`KNACK_STORY_MODELS=live scripts/one_story.sh`, run once on 2026-11-02 from 14:44:38Z to 14:45:07Z, with real Spark (`muse-spark-1.3`, api.meta.ai) and Spark Open (`meta-models/muse-spark-open-1026`, inference.baseten.co), in its sandbox HOME. No retries. The output is frozen, unchanged, in [`mockups/fixtures/one_story/`](../mockups/fixtures/one_story/).

Each edit is replayed inside the captured Muse Code PreToolUse payload (`tests/hooks/fixtures/edit_event.json`), so every guard receipt and both rulings record the agent from its `model` field: `muse-spark-1.3-contributor`. Only `tool_input`, `cwd` and `session_id` (`one-story`) are replaced.

## The chain, on one block receipt (`0e7ab6083866`)

1. block: deny, with #75025's verbatim quote, rule airflow-75025, root airflow-75025-1.
2. argue "alias state and start_date…": HOLD, citing the two quoted sentences verbatim as one quote. Spark only.
3. argue "Airflow's REST API is documented and public; … deprecation cycle …": ESCALATE. Spark escalated, Spark Open was asked and agreed (both trace ids are in `rulings.jsonl`), and a provisional must-pass case was held for a person.
4. resolve uphold by Vedant Srivastava, reason "The decision stands: these two sort options never worked (they returned an error), so there was nothing to deprecate. Sort by last_run_state and last_run_start_date.": the held case closed and no case was added.
5. corrected edit (lines 135–136 deleted): allowed.
6. `knack receipts verify`: 8 receipts, chain intact.

## Latency

Guard verdict is the deny or allow receipt's `latency_ms` (the ast-grep scan). Hook round trip is the step's wall time: `sh -c`, Python start, and the envelope, as Muse Code runs the installed hook. Both come from `latency.json`.

- Guard verdict, this run: 17.3 ms (block), 17.0 ms (corrected edit).
- Hook round trip, this run: 171 ms (block), 198 ms (corrected edit).
- Guard verdict, today's runs: 16.3–18.4 ms.
- Hook round trip, today's runs: 163–256 ms.

"Today's runs" covers the three live runs on 2026-11-02: this run and the two before it. The earlier runs' outputs are not in the repo, so their `latency.json` figures are quoted here as their only record:

- 14:33:21Z, stopped and not frozen. Its ESCALATE step held on a customer-contract objection that the record already answers, and its rulings recorded no agent.
- 14:36:20Z, matched the chain and was frozen, then replaced by this run after the uphold reason changed.

```json
{"14:33:21Z": {"guard_ms": {"block": 17.748167003446724, "corrected": 18.394958999124356},
               "wall_ms": {"block": 255.5, "corrected": 205.8}},
 "14:36:20Z": {"guard_ms": {"block": 16.531083005247638, "corrected": 16.324999996868428},
               "wall_ms": {"block": 163.3, "corrected": 180.0}}}
```

Three runs on one laptop, all on the same day. This is not a distribution.
