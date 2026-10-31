`GET /api/v2/dags` says you can sort by `state` and `start_date`. Try either one and the request fails:

```
GET /api/v2/dags?order_by=state
AttributeError: type object 'DagModel' has no attribute 'state'
```

Neither column exists on `DagModel`. `SortParam` returns a clean 400 for a name that is not on its allowed list, but these two are on the list, so it skips that check and goes straight to `getattr(self.model, name)`, which raises.

The UI endpoint behind `/ui/dags` lists the same two names and fails the same way.

### Where they came from

#44345 moved the last-run sorts into `to_replace`:

```diff
-["dag_id", "dag_display_name", "next_dagrun", "last_run_state", "last_run_start_date"],
+["dag_id", "dag_display_name", "next_dagrun", "state", "start_date"],
 DagModel,
+{"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date},
```

The mapping is correct and both `last_run_*` names work. The mistake was writing the `DagRun` column names into the allowed list instead of deleting them. They have been advertised and broken ever since.

### What this does

Removes the two names from both endpoints. Sorting by them now gets the same 400 as any other unknown attribute, and the spec stops offering them. `last_run_state` and `last_run_start_date` are untouched and remain the way to sort by the latest run.

I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`. The `last_run_*` spelling predates the refactor and already works, so a second name for the same sort felt worse than one. Happy to alias instead if you would rather keep the advertised names working.

### Checks

Six tests, three per endpoint, covering `state`, `start_date` and `-state`. All six fail without the change, each with that `AttributeError` rather than a status code. `test_dags.py` for the public and UI routes is at 276 passed.

I checked the other 32 `SortParam` call sites the same way, 155 advertised attributes in all, including the keyword-argument form in `hitl.py` and the two in `grid.py` that take their attributes from `timetable.run_ordering`. These two endpoints were the only mismatches.

The spec, the private UI spec and the six generated UI files all come from their hooks and are stable on a second run. The only lines that change in them are the `order_by` descriptions.

---

##### Was generative AI tooling used to co-author this PR?

- [X] Yes - Claude Code (Opus 5)
