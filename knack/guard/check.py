import time
from collections import Counter
from pathlib import Path

from knack.contracts.models import Root, Verdict
from knack.guard.runner import RuleMatch, scan_file_with_rule
from knack.guard.verdict_builder import build_verdict

GUARD_ERROR_REASON = "guard-error"


def check_file(
    file_path: Path,
    rule_path: Path,
    rule_id: str,
    root: Root | None,
    log_path: Path,
    baseline: Path | None = None,
) -> Verdict:
    # With a baseline, only matches the baseline lacks count; without one, all do.
    started = time.perf_counter()
    try:
        matches = new_matches(file_path, rule_path, baseline)
        return build_verdict(rule_id, matches, root, _elapsed_ms(started))
    except Exception as error:
        # Fail open: a bug in the guard must never block an edit.
        return fail_open(error, log_path, started)


def fail_open(error: Exception, log_path: Path, started: float) -> Verdict:
    log_error_quietly(log_path, error)
    return _guard_error_verdict(error, started)


def new_matches(
    file_path: Path, rule_path: Path, baseline: Path | None
) -> list[RuleMatch]:
    # The baseline is scanned only when the file matches, so clean edits cost one scan.
    matches = scan_file_with_rule(file_path, rule_path)
    if not matches or baseline is None:
        return matches
    return only_new(matches, scan_file_with_rule(baseline, rule_path))


def only_new(proposed: list[RuleMatch], before: list[RuleMatch]) -> list[RuleMatch]:
    # Compared by match text, counted: a moved old match is old, a repeated one is new.
    left = Counter(match.matched_text for match in before)
    kept = list[RuleMatch]()
    for match in proposed:
        left[match.matched_text] -= 1
        if left[match.matched_text] < 0:
            kept.append(match)
    return kept


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000


def _guard_error_verdict(error: Exception, started: float) -> Verdict:
    reason = f"{GUARD_ERROR_REASON}: {type(error).__name__}"
    return Verdict(allowed=True, reason=reason, latency_ms=_elapsed_ms(started))


def log_error_quietly(log_path: Path, error: Exception) -> None:
    # Logging is best effort; a failed write must not break fail-open.
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"{type(error).__name__}: {error}\n")
    except Exception:
        pass
