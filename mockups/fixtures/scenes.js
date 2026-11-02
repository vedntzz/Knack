// Frozen by freeze.py; see mockups/SOURCES.md.
window.KNACK = {
  "captured_at": "2026-11-01T23:35:40+00:00",
  "day": {
    "repo": "apache/airflow",
    "branch": "main",
    "date": "2026-11-01",
    "events": [
      {
        "type": "commit",
        "sha": "a2548563ebc5dcf888c738b9e3d2b12669e252a6",
        "author": "knack demo",
        "message": "base",
        "time": "2026-11-01T16:34:51-05:00"
      },
      {
        "type": "receipt",
        "kind": "block",
        "time": "2026-11-01T21:34:52.285310+00:00",
        "root_id": "airflow-75025-1",
        "decider": "Pushkal Gupta (author); approved and merged by bbovenzi",
        "receipt_hash": "4be4607b22184423e2cf6c9506b5ed3a0b0a028f5390adfda3ae49747b11d066"
      }
    ],
    "pulls_error": "GITHUB_TOKEN is not set",
    "seats": [
      {
        "root_id": "airflow-75025-1",
        "decided_by": "Pushkal Gupta (author); approved and merged by bbovenzi",
        "confirmed_by": null,
        "pr": 75025,
        "merged_at": "2026-10-19T21:36:02Z"
      },
      {
        "root_id": "airflow-75774-1",
        "decided_by": "stegololz",
        "confirmed_by": null,
        "pr": 75774,
        "merged_at": "2026-10-28T16:53:52Z"
      }
    ],
    "registry_error": null
  },
  "root": {
    "id": "airflow-75025-1",
    "title": "Remove two Dag list sort options that never worked",
    "decision": "Dag list endpoints do not accept bare state or start_date as sort keys; the latest run is sorted only as last_run_state and last_run_start_date.",
    "why": "The `last_run_*` spelling predates the refactor and already works, so a second name for the same sort felt worse than one.",
    "decided_by": "Pushkal Gupta (author); approved and merged by bbovenzi",
    "source_url": "https://github.com/apache/airflow/pull/75025",
    "quote": "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`.",
    "status": "Confirmed",
    "rejected_alternative": "Alias state and start_date onto DagRun.state and DagRun.start_date.",
    "seeded": false,
    "models": [],
    "merged_at": "2026-10-19T21:36:02Z"
  },
  "block": {
    "reason": {
      "Decision": "Dag list endpoints do not accept bare state or start_date as sort keys; the latest run is sorted only as last_run_state and last_run_start_date.",
      "Decided by": "Pushkal Gupta (author); approved and merged by bbovenzi",
      "Quote": "\"I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`.\"",
      "Source": "https://github.com/apache/airflow/pull/75025",
      "Rejected alternative": "Alias state and start_date onto DagRun.state and DagRun.start_date."
    },
    "verdict_ms": "18.7",
    "round_trip_ms": "212",
    "scan": "ast-grep",
    "no_model": "No model, no network.",
    "receipt": "80b311c17a3980dd2e9c712f2dc113c0d2be9ff94e45136d790f86cac64bef16",
    "attempted": {
      "file": "airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py",
      "rows": [
        {
          "line": 135,
          "text": "\"state\": DagRun.state",
          "code": "\"state\": DagRun.state,"
        },
        {
          "line": 136,
          "text": "\"start_date\": DagRun.start_date",
          "code": "\"start_date\": DagRun.start_date,"
        }
      ]
    },
    "log_commit": "b8c3032 2026-11-01T13:09:04-05:00"
  },
  "rejected_base": [
    {
      "file": "airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py",
      "line": 132,
      "code": "[\"dag_id\", \"dag_display_name\", \"next_dagrun\", \"state\", \"start_date\"],"
    },
    {
      "file": "airflow-core/src/airflow/api_fastapi/core_api/routes/ui/dags.py",
      "line": 139,
      "code": "[\"dag_id\", \"dag_display_name\", \"next_dagrun\", \"state\", \"start_date\"],"
    }
  ],
  "grid": {
    "gates": [
      "base",
      "head",
      "0 FP tree",
      "0 FP release",
      "rename",
      "variants",
      "compliant",
      "held-out"
    ],
    "cells": {
      "base": "PASS",
      "head": "PASS",
      "0 FP tree": "PASS",
      "0 FP release": "PASS",
      "rename": "PASS",
      "variants": "PASS",
      "compliant": "PASS",
      "held-out": "PASS"
    },
    "tier": "block"
  },
  "proof": {
    "old_release": "3.3.2",
    "fp": 0
  },
  "hold": {
    "time": "2026-11-01T16:13:45.609951+00:00",
    "receipt_hash": "13f19d15e9004021ca849af1a05c11408d90e26c9e28d016c1345b20652bb86f",
    "objection": "The frontend still sends order_by=state. Let me alias state and start_date onto DagRun.state and DagRun.start_date.",
    "decision": "hold",
    "reply": "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`.",
    "cited_quotes": [
      "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`."
    ],
    "model": "muse-spark-1.3"
  },
  "escalate": {
    "time": "2026-10-31T18:18:46.342163+00:00",
    "receipt_hash": "1983f52b4751dc29c81c30c52b442c6540667465fa4c62143b0a3569c7431520",
    "objection": "A customer dashboard has pinned order_by=state in a contract that runs until March; removing it breaks them.",
    "decision": "escalate",
    "reply": "My recorded decision does not cover a customer dashboard pinned to order_by=state or a contract running until March breaking. A person will decide.",
    "cited_quotes": [
      "I removed them rather than aliasing them onto `DagRun.state` and `DagRun.start_date`."
    ],
    "model": "muse-spark-1.3"
  },
  "spark": {
    "model": "muse-spark-1.3",
    "host": "api.meta.ai"
  },
  "spark_open": {
    "model": "meta-models/muse-spark-open-1026",
    "host": "inference.baseten.co"
  },
  "readme": {
    "verify": "bash scripts/reproduce.sh",
    "resolve": "knack resolve <receipt> allow|retire --reason"
  },
  "receipts_verify": "37 receipts, chain intact",
  "miss": {
    "root": {
      "id": "fastapi-16062-1",
      "title": "♻️ Update the lru_cache limit for dependencies to account for large apps",
      "decision": "Update the lru_cache limit for dependencies to account for large apps",
      "why": "Some users reported a number of dependencies larger than 1024, this should account for larger apps.",
      "decided_by": "tiangolo",
      "source_url": "https://github.com/fastapi/fastapi/pull/16062",
      "quote": "I'll wait to see if anyone requests an even larger bump, for now this should work.",
      "status": "Inferred",
      "rejected_alternative": "an even larger bump",
      "seeded": false,
      "models": [
        "muse-spark-1.3"
      ],
      "merged_at": "2026-07-27T11:18:26Z"
    },
    "edit_note": "Rebuilt, not the agent's bytes: the run's diff.patch was deleted with its temp work folder. Evidence (bench/AUDIT-1030c.md, section b): the blind judge says the diff 'enlarges the bound 8x to 8192 on all three call-type caches'; the run recorded 0 rule hits, yet a literal maxsize=8192 matches the rule, so the size most likely came through a name. This edit sets 8192 through a module-level constant.",
    "edit_file": "fastapi/dependencies/models.py",
    "edit_after": "import inspect\nimport sys\nfrom collections.abc import Callable\nfrom dataclasses import dataclass, field\nfrom functools import lru_cache, partial\nfrom typing import Any, Literal\n\nfrom fastapi._compat import ModelField\nfrom fastapi.security.base import SecurityBase\nfrom fastapi.types import DependencyCacheKey\n\nif sys.version_info >= (3, 13):  # pragma: no cover\n    from inspect import iscoroutinefunction\nelse:  # pragma: no cover\n    from asyncio import iscoroutinefunction\n\n# Large apps have a few thousand distinct dependency callables; entries are tiny.\n_CALLABLE_CACHE_SIZE = 8192\n\n\ndef _unwrapped_call(call: Callable[..., Any] | None) -> Any:\n    if call is None:\n        return call  # pragma: no cover\n    unwrapped = inspect.unwrap(_impartial(call))\n    return unwrapped\n\n\ndef _impartial(func: Callable[..., Any]) -> Callable[..., Any]:\n    while isinstance(func, partial):\n        func = func.func\n    return func\n\n\n@dataclass(slots=True)\nclass Dependant:\n    path_params: list[ModelField] = field(default_factory=list)\n    query_params: list[ModelField] = field(default_factory=list)\n    header_params: list[ModelField] = field(default_factory=list)\n    cookie_params: list[ModelField] = field(default_factory=list)\n    body_params: list[ModelField] = field(default_factory=list)\n    dependencies: list[\"Dependant\"] = field(default_factory=list)\n    name: str | None = None\n    call: Callable[..., Any] | None = None\n    request_param_name: str | None = None\n    websocket_param_name: str | None = None\n    http_connection_param_name: str | None = None\n    response_param_name: str | None = None\n    background_tasks_param_name: str | None = None\n    security_scopes_param_name: str | None = None\n    own_oauth_scopes: list[str] | None = None\n    parent_oauth_scopes: list[str] | None = None\n    use_cache: bool = True\n    path: str | None = None\n    scope: Literal[\"function\", \"request\"] | None = None\n\n\n_UsesScopesCache = dict[int, tuple[Dependant, bool]]\n\n\nclass _CallIdentity:\n    __slots__ = (\"call\",)\n\n    def __init__(self, call: Callable[..., Any]) -> None:\n        self.call = call\n\n    def __hash__(self) -> int:\n        return id(self.call)\n\n    def __eq__(self, other: object) -> bool:\n        return isinstance(other, _CallIdentity) and self.call is other.call\n\n\ndef _get_oauth_scopes(*, dependant: Dependant) -> list[str]:\n    scopes = (\n        dependant.parent_oauth_scopes.copy() if dependant.parent_oauth_scopes else []\n    )\n    # This doesn't use a set to preserve order, just in case\n    for scope in dependant.own_oauth_scopes or []:\n        if scope not in scopes:\n            scopes.append(scope)\n    return scopes\n\n\ndef _get_cache_key(\n    *,\n    dependant: Dependant,\n    uses_scopes_cache: _UsesScopesCache | None = None,\n) -> DependencyCacheKey:\n    scopes_for_cache = (\n        tuple(sorted(set(_get_oauth_scopes(dependant=dependant))))\n        if _uses_scopes(dependant=dependant, cache=uses_scopes_cache)\n        else ()\n    )\n    return (\n        dependant.call,\n        scopes_for_cache,\n        _get_computed_scope(dependant=dependant) or \"\",\n    )\n\n\ndef _uses_scopes(\n    *, dependant: Dependant, cache: _UsesScopesCache | None = None\n) -> bool:\n    if cache is None:\n        cache = {}\n    cache_key = id(dependant)\n    cached = cache.get(cache_key)\n    if cached is not None and cached[0] is dependant:\n        return cached[1]\n    if dependant.own_oauth_scopes:\n        result = True\n    elif dependant.security_scopes_param_name is not None:\n        result = True\n    elif _is_security_scheme(dependant=dependant):\n        result = True\n    else:\n        result = any(\n            _uses_scopes(dependant=sub_dep, cache=cache)\n            for sub_dep in dependant.dependencies\n        )\n    cache[cache_key] = (dependant, result)\n    return result\n\n\ndef _is_security_scheme(*, dependant: Dependant) -> bool:\n    if dependant.call is None:\n        return False  # pragma: no cover\n    unwrapped = _unwrapped_call(dependant.call)\n    return isinstance(unwrapped, SecurityBase)\n\n\ndef _get_security_scheme(*, dependant: Dependant) -> SecurityBase:\n    # Mainly to get the type of SecurityBase, but it's the same dependant.call\n    unwrapped = _unwrapped_call(dependant.call)\n    assert isinstance(unwrapped, SecurityBase)\n    return unwrapped\n\n\ndef _get_security_dependencies(*, dependant: Dependant) -> list[Dependant]:\n    return [dep for dep in dependant.dependencies if _is_security_scheme(dependant=dep)]\n\n\n@lru_cache(maxsize=_CALLABLE_CACHE_SIZE)\ndef _is_gen_callable_cached(call_identity: _CallIdentity) -> bool:\n    call = call_identity.call\n    if inspect.isgeneratorfunction(_impartial(call)) or inspect.isgeneratorfunction(\n        _unwrapped_call(call)\n    ):\n        return True\n    if inspect.isclass(_unwrapped_call(call)):\n        return False\n    dunder_call = getattr(_impartial(call), \"__call__\", None)  # noqa: B004\n    if dunder_call is None:\n        return False  # pragma: no cover\n    if inspect.isgeneratorfunction(\n        _impartial(dunder_call)\n    ) or inspect.isgeneratorfunction(_unwrapped_call(dunder_call)):\n        return True\n    dunder_unwrapped_call = getattr(_unwrapped_call(call), \"__call__\", None)  # noqa: B004\n    if dunder_unwrapped_call is None:\n        return False  # pragma: no cover\n    return inspect.isgeneratorfunction(\n        _impartial(dunder_unwrapped_call)\n    ) or inspect.isgeneratorfunction(_unwrapped_call(dunder_unwrapped_call))\n\n\ndef _is_gen_callable(call: Callable[..., Any] | None) -> bool:\n    if call is None:\n        return False  # pragma: no cover\n    return _is_gen_callable_cached(_CallIdentity(call))\n\n\n@lru_cache(maxsize=_CALLABLE_CACHE_SIZE)\ndef _is_async_gen_callable_cached(call_identity: _CallIdentity) -> bool:\n    call = call_identity.call\n    if inspect.isasyncgenfunction(_impartial(call)) or inspect.isasyncgenfunction(\n        _unwrapped_call(call)\n    ):\n        return True\n    if inspect.isclass(_unwrapped_call(call)):\n        return False\n    dunder_call = getattr(_impartial(call), \"__call__\", None)  # noqa: B004\n    if dunder_call is None:\n        return False  # pragma: no cover\n    if inspect.isasyncgenfunction(\n        _impartial(dunder_call)\n    ) or inspect.isasyncgenfunction(_unwrapped_call(dunder_call)):\n        return True\n    dunder_unwrapped_call = getattr(_unwrapped_call(call), \"__call__\", None)  # noqa: B004\n    if dunder_unwrapped_call is None:\n        return False  # pragma: no cover\n    return inspect.isasyncgenfunction(\n        _impartial(dunder_unwrapped_call)\n    ) or inspect.isasyncgenfunction(_unwrapped_call(dunder_unwrapped_call))\n\n\ndef _is_async_gen_callable(call: Callable[..., Any] | None) -> bool:\n    if call is None:\n        return False  # pragma: no cover\n    return _is_async_gen_callable_cached(_CallIdentity(call))\n\n\n@lru_cache(maxsize=_CALLABLE_CACHE_SIZE)\ndef _is_coroutine_callable_cached(call_identity: _CallIdentity) -> bool:\n    call = call_identity.call\n    if inspect.isroutine(_impartial(call)) and iscoroutinefunction(_impartial(call)):\n        return True\n    if inspect.isroutine(_unwrapped_call(call)) and iscoroutinefunction(\n        _unwrapped_call(call)\n    ):\n        return True\n    if inspect.isclass(_unwrapped_call(call)):\n        return False\n    dunder_call = getattr(_impartial(call), \"__call__\", None)  # noqa: B004\n    if dunder_call is None:\n        return False  # pragma: no cover\n    if iscoroutinefunction(_impartial(dunder_call)) or iscoroutinefunction(\n        _unwrapped_call(dunder_call)\n    ):\n        return True\n    dunder_unwrapped_call = getattr(_unwrapped_call(call), \"__call__\", None)  # noqa: B004\n    if dunder_unwrapped_call is None:\n        return False  # pragma: no cover\n    return iscoroutinefunction(\n        _impartial(dunder_unwrapped_call)\n    ) or iscoroutinefunction(_unwrapped_call(dunder_unwrapped_call))\n\n\ndef _is_coroutine_callable(call: Callable[..., Any] | None) -> bool:\n    if call is None:\n        return False  # pragma: no cover\n    return _is_coroutine_callable_cached(_CallIdentity(call))\n\n\ndef _get_computed_scope(*, dependant: Dependant) -> str | None:\n    if dependant.scope:\n        return dependant.scope\n    if _is_gen_callable(dependant.call) or _is_async_gen_callable(dependant.call):\n        return \"request\"\n    return None\n",
    "run1_log": "recorded must-fail case fastapi/dependencies/models.py [77322b4d226e] for fastapi-16062 -> data/registry/cases/fastapi-16062/must-fail-77322b4d226e.json\nfastapi-16062 fails: guard edit fastapi/dependencies/models.py [77322b4d226e] adds no new match; recompiling with muse-spark-1.3\nPASS proof: base, guard-edit, head, rename-base, rename-head, variant-compliant, variant-violation hold; 0 FP on the default branch and release 0.140.0\nFAIL held-out same: 3/3 violations caught, 2/3 compliant allowed\nPASS held-out cross: 3/3 violations caught, 3/3 compliant allowed\nPASS fresh cross-model: 3/3 violations caught, 3/3 compliant allowed (/Users/vedant/.knack/cache/miss/registry-fastapi/16062/fresh-20261031T165308Z-a93196)\nkept the old fastapi-16062: 1 gate(s) failed\nexit=1\n",
    "run2_log": "recorded must-fail case fastapi/dependencies/models.py [77322b4d226e] for fastapi-16062 -> data/registry/cases/fastapi-16062/must-fail-77322b4d226e.json\nfastapi-16062 fails: guard edit fastapi/dependencies/models.py [77322b4d226e] adds no new match; recompiling with muse-spark-1.3\nPASS proof: base, guard-edit, head, rename-base, rename-head, variant-compliant, variant-violation hold; 0 FP on the default branch and release 0.140.0\nPASS held-out same: 2/3 violations caught, 3/3 compliant allowed\nFAIL held-out cross: 3/3 violations caught, 2/3 compliant allowed\nPASS fresh cross-model: 3/3 violations caught, 3/3 compliant allowed (/Users/vedant/.knack/cache/miss/registry-fastapi/16062/fresh-20261031T165722Z-70a92c)\ncandidate rule: /Users/vedant/.knack/cache/miss/registry-fastapi/16062/candidate-20261031T165737Z-de348c.yml\nkept the old fastapi-16062: 1 gate(s) failed\nexit=1\n",
    "bar2_log": "recorded must-fail case fastapi/dependencies/models.py [77322b4d226e] for fastapi-16062 -> data/registry/cases/fastapi-16062/must-fail-77322b4d226e.json\nfastapi-16062 fails: guard edit fastapi/dependencies/models.py [77322b4d226e] adds no new match; recompiling with muse-spark-1.3\nPASS cases: every must-fail edit denied, every must-pass edit allowed\nPASS proof: base, guard-edit, head, rename-base, rename-head, variant-compliant, variant-violation hold; 0 FP on the default branch and release 0.140.0\nPASS held-out same: 2/3 violations caught (old rule 2), 3/3 compliant allowed\nPASS held-out cross: 3/3 violations caught (old rule 3), 3/3 compliant allowed\nPASS fresh cross-model: 3/3 violations caught (old rule 3), 3/3 compliant allowed (/Users/vedant/.knack/cache/miss/registry-fastapi/16062/fresh-20261031T171443Z-983f2a)\ncandidate rule: /Users/vedant/.knack/cache/miss/registry-fastapi/16062/candidate-20261031T171504Z-43479c.yml\ninstalled fastapi-16062 -> data/registry/../rules/fastapi/16062.yml (2 attempt(s))\nexit=0\n",
    "tier": "warn",
    "cases": [
      "must-fail-77322b4d226e.json"
    ]
  }
};
