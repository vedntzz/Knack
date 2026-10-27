import time
from pathlib import Path

from knack.contracts.models import Root, Verdict
from knack.guard.runner import scan_file_with_rule
from knack.guard.verdict_builder import build_verdict

GUARD_ERROR_REASON = "guard-error"


def check_file(
    file_path: Path, rule_path: Path, rule_id: str, root: Root | None, log_path: Path
) -> Verdict:
    started = time.perf_counter()
    try:
        return _scan_and_build(file_path, rule_path, rule_id, root, started)
    except Exception as error:
        # Fail open: a bug in the guard must never block an edit.
        return fail_open(error, log_path, started)


def fail_open(error: Exception, log_path: Path, started: float) -> Verdict:
    _log_error_quietly(log_path, error)
    return _guard_error_verdict(error, started)


def _scan_and_build(
    file_path: Path, rule_path: Path, rule_id: str, root: Root | None, started: float
) -> Verdict:
    matches = scan_file_with_rule(file_path, rule_path)
    return build_verdict(rule_id, matches, root, _elapsed_ms(started))


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000


def _guard_error_verdict(error: Exception, started: float) -> Verdict:
    reason = f"{GUARD_ERROR_REASON}: {type(error).__name__}"
    return Verdict(allowed=True, reason=reason, latency_ms=_elapsed_ms(started))


def _log_error_quietly(log_path: Path, error: Exception) -> None:
    # Logging is best effort; a failed write must not break fail-open.
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"{type(error).__name__}: {error}\n")
    except Exception:
        pass
