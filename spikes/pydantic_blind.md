# Pydantic blind run

`knack init pydantic/pydantic`, logged to [`pydantic_blind.log`](pydantic_blind.log).
Run log, not checked by reproduce.sh. The log ends mid-run, after #13879's
old-release line, so anything after that point is unrecorded.

- Select: 100 PRs read, 30 kept.
- Extract: 38 decisions, 13 rejected alternatives (13 verbatim), 0 failed.
- Roots: 13 Inferred, 0 Confirmed, 0 Unknown kept. Nothing here can block.
- Compile: 5 PRs with a verbatim rejected alternative. Spark Open
  (`meta-models/muse-spark-open-1026`) writes variants, Spark compiles.
- Held-out so far: #14138 fail (0/3 caught, 3/3 allowed), #14141 fail
  (1/3 caught, 3/3 allowed), #13848 pass (3/3 caught, 3/3 allowed).
  #13879 and the fifth PR have no held-out line in the log.
