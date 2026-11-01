# KN-73 open-weights spike: KN-70 and KN-71

Raw requests and responses are in `spikes/open_weights/kn70/` and `kn71/`. The probe script is `kn71/probe.py`.

## KN-70: confidence brake (Spark Open logprobs)
- Not measured. Baseten's `meta-models/muse-spark-open-1026` returns HTTP 200 with no `logprobs` field. The same is true for `logprobs: true` on chat, streamed chat, and `/v1/completions` (logprobs=1).
- The undated id `meta-models/muse-spark-open` returns 403 for this key.
- Baseten's docs say logprob support "varies by model". The usage blocks show speculative decoding, which likely turns them off.
- Real-mean, none-mean, gap, threshold errors: n/a. No PRs were run, because without logprobs the measurement is impossible on this endpoint.
- The 13 real outcomes are the 13 held-out PRs (12 installed rules plus fastapi #16043).
- Blocked, not disproven. Unblocking needs a Spark Open deployment that returns logprobs.
- **NO**

## KN-71: Glimmer as blind second label
- Agreement with the stored label: not measured. All 42 pilot runs (`bench/runs-1030b.jsonl`) have `diff_path` in deleted `/var/folders` temp dirs. Only the judge's answers survive, not its inputs.
- Timing probe only, on one blind prompt: ticket fastapi-16062, plus the one surviving bench edit `bench/misses/16062-none-2.edit.json` (1030c, not pilot).
- Glimmer local (`muse-glimmer:30b`, Ollama, 24 GB Mac): 1 run, 19 min 40 s, 2,362 output tokens at about 3.5 tok/s with memory swapping. Label "no". API cost $0.
- Spark Open on Baseten: 2 runs, 12.8 s and 12.5 s, about 3.7k output tokens each. Label "no" both times. Cost about $0.016–0.017 per label.
  - That cost assumes $1.25 per 1M input and $4.25 per 1M output tokens, from a third-party snapshot of Baseten's pricing page.
- Glimmer costs less but is about 94x slower. A 54-run bench would spend about 18 hours on labels.
- The 1/1 agreement on the probe is not pilot data and does not count toward the 4/5 bar.
- Unblocking means rerunning pilot tickets so the diffs are kept, then labelling them with both models.
- **NO**
