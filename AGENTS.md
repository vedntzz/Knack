# Knack
Knack blocks AI coding agents from edits that contradict a team's recorded
decisions, and cites who decided, why, and the verbatim source.

## Hard rules
- NEVER run git add/commit/push. Print the commands; Vedant commits.
- Strict TDD: write tests, show them failing, then implement.
- Verdict path: plain code. No model, no network, never crashes.
  On internal error: log to .knack/guard_errors.log, return allowed=True,
  reason "guard-error". Never block on our own bug.
- Guard blocks ONLY on Confirmed roots. Inferred/Unknown never block.
- Honest labels: Confirmed / Inferred / Unknown, plus a seeded flag.
- No chat/Q&A surface, ever.

## Style
- One-line comments only. Names explain the function without opening it.
- No function over 20 lines. Simplest pattern that works.

## Stack
Python 3.11+, pydantic v2, pytest, stdlib ast (index), ast-grep 0.51.0 (pinned).

## Gotchas (proven, do not re-prove)
- ast-grep `inside` defaults to stopBy: neighbor and silently matches
  nothing. Use `stopBy: end`. Regression: violating.py → exactly 2 errors.
- Muse Code deny = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
  "permissionDecision": "deny", "permissionDecisionReason": "..."}}, exit 0.
  Bare JSON does NOT block. Exit 2 + stderr = fallback. Crash = fail open.

## Tonight
contracts → guard replay → index → roots. Walk API is Tuesday.