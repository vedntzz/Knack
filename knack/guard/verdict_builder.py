from knack.contracts.models import MatchedCode, Root, Verdict
from knack.guard.runner import RuleMatch

NO_MATCH_REASON = "no rule matched"
STALE_PIN = "Confirmed root, rule changed since it was confirmed (knack confirm {root_id} re-pins)"
# Placeholders are Root field names plus alternative and matched.
DENY_TEMPLATE = (
    "Knack blocked this edit.\n"
    "Decision: {decision}\n"
    "Decided by: {decided_by}\n"
    "Why: {why}\n"
    "{alternative}"
    'Quote: "{quote}"\n'
    "Source: {source_url}\n"
    "{matched}"
)


def build_verdict(
    rule_id: str,
    matches: list[RuleMatch],
    root: Root | None,
    latency_ms: float,
    stale_pin: bool = False,
) -> Verdict:
    # A stale pin: the rule changed since a person confirmed it, so it only advises.
    if not matches:
        return Verdict(allowed=True, reason=NO_MATCH_REASON, latency_ms=latency_ms)
    if root is None or root.status != "Confirmed" or stale_pin:
        return _advisory_verdict(rule_id, matches, root, latency_ms)
    return _deny_verdict(rule_id, matches, root, latency_ms)


def _deny_verdict(
    rule_id: str, matches: list[RuleMatch], root: Root, latency_ms: float
) -> Verdict:
    return Verdict(
        allowed=False,
        reason=_deny_reason(root, matches),
        rule_id=rule_id,
        root_ids=[root.id],
        latency_ms=latency_ms,
        matched=_matched_code(matches),
    )


def _advisory_verdict(
    rule_id: str, matches: list[RuleMatch], root: Root | None, latency_ms: float
) -> Verdict:
    return Verdict(
        allowed=True,
        reason=_advisory_reason(matches, root),
        rule_id=rule_id,
        root_ids=[root.id] if root else [],
        latency_ms=latency_ms,
        matched=_matched_code(matches),
    )


def _advisory_reason(matches: list[RuleMatch], root: Root | None) -> str:
    # Only Confirmed roots block; anything weaker is surfaced but allowed.
    label = f"{root.status} root" if root else "no root on record"
    if root is not None and root.status == "Confirmed":
        label = STALE_PIN.format(root_id=root.id)
    return f"advisory: {label}, not blocking. {_matched_line(matches)}"


def _deny_reason(root: Root, matches: list[RuleMatch]) -> str:
    return DENY_TEMPLATE.format(
        **root.model_dump(),
        alternative=_rejected_alternative_line(root),
        matched=_matched_line(matches),
    )


def _rejected_alternative_line(root: Root) -> str:
    if root.rejected_alternative is None:
        return ""
    return f"Rejected alternative: {root.rejected_alternative}\n"


def _matched_line(matches: list[RuleMatch]) -> str:
    return "Matched: " + ", ".join(f"{m.matched_text} (line {m.line})" for m in matches)


def _matched_code(matches: list[RuleMatch]) -> list[MatchedCode]:
    return [MatchedCode(line=m.line, text=m.matched_text) for m in matches]
