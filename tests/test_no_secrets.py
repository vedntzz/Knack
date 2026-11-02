"""CI blocks any tracked file that holds an API key or token shape."""

import re
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

REPO = Path(__file__).resolve().parent.parent
SELF = "tests/test_no_secrets.py"
NAMES = r"\b(?:MODEL_API_KEY|META_API_KEY|BASETEN_API_KEY|GITHUB_TOKEN)"

# Group 1 of every pattern is the secret value itself.
PATTERNS: dict[str, re.Pattern[str]] = {
    "openai_style_sk": re.compile(r"\b(sk-(?:proj-|ant-)?[A-Za-z0-9_\-]{16,})"),
    "baseten_key": re.compile(r"\b([A-Za-z0-9]{8}\.[A-Za-z0-9]{32})\b"),
    "api_key_header": re.compile(r"Api-Key\s+([A-Za-z0-9._\-]{8,})"),
    "bearer_token": re.compile(r"\b[Bb]earer\s+([A-Za-z0-9._~+/\-]{8,}=*)"),
    "authorization_header": re.compile(
        r"Authorization['\"]?\s*[:=]\s*['\"]?(?:Bearer|Basic|token|Api-Key)\s+([^\s'\"]+)"
    ),
    "github_token": re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{30,})"),
    "github_pat": re.compile(r"\b(github_pat_[A-Za-z0-9_]{20,})"),
    "aws_access_key": re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b"),
    "aws_secret_key": re.compile(
        r"aws_secret_access_key['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+]{40})"
    ),
    "named_key_quoted": re.compile(
        NAMES + r"['\"]?\s*[:=]\s*['\"]([^'\"$\s][^'\"\s]*)['\"]"
    ),
    "named_key_assigned": re.compile(NAMES + r"\s*=\s*([^\s'\"$][^\s'\"]*)"),
    "private_key": re.compile(r"(-----BEGIN [A-Z ]*PRIVATE KEY-----)"),
    "huggingface_token": re.compile(r"\b(hf_[A-Za-z0-9]{30,})"),
}

# Known fake values, allowed only in the file that uses them.
PLACEHOLDERS: dict[str, frozenset[str]] = {
    "tests/bench/test_doctor.py": frozenset(
        {"sk-doctor-model-key", "ghp-doctor-test-token", "bt-doctor-open-key"}
    ),
    "tests/bench/test_run.py": frozenset({"sk-bench-test-key-0123456789"}),
    "tests/guard/test_pr_comment.py": frozenset({"t0ken"}),
    "tests/pipeline/test_spark_open.py": frozenset({"key"}),
    "tests/pipeline/test_watch_token.py": frozenset(
        {
            "fake-watch-file-token-7d1e",
            "fake-watch-file-model-5b2f",
            "fake-watch-file-open-8c4a",
        }
    ),
}
ALL_PLACEHOLDERS = frozenset(v for values in PLACEHOLDERS.values() for v in values)
# A shell variable ($NAME, ${NAME}) or command substitution ($(...)) is a reference.
SHELL_REFERENCE = re.compile(r"\$(?:[A-Za-z_]\w*|\{[A-Za-z_]\w*\}|\(.*)")


class Hit(NamedTuple):
    path: str
    line: int
    pattern: str
    value: str


def hits_in_text(path: str, text: str) -> list[Hit]:
    return [
        Hit(path, text.count("\n", 0, match.start()) + 1, name, match.group(1))
        for name, regex in PATTERNS.items()
        for match in regex.finditer(text)
    ]


def is_placeholder(hit: Hit) -> bool:
    if hit.path == SELF:
        return hit.value in ALL_PLACEHOLDERS
    return hit.value in PLACEHOLDERS.get(hit.path, frozenset())


def is_shell_reference(hit: Hit) -> bool:
    return SHELL_REFERENCE.fullmatch(hit.value) is not None


def leaks_in_text(path: str, text: str) -> list[Hit]:
    return [
        hit
        for hit in hits_in_text(path, text)
        if not is_placeholder(hit) and not is_shell_reference(hit)
    ]


def leaks_in_file(path: str) -> list[Hit]:
    text = (REPO / path).read_text(encoding="utf-8", errors="replace")
    return leaks_in_text(path, text)


def tracked_files() -> list[str]:
    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True, text=True
    )
    return [p for p in listing.stdout.split("\0") if p and (REPO / p).is_file()]


def describe(hit: Hit) -> str:
    preview = f"{hit.value[:4]}…[{len(hit.value)} chars]"
    return f"{hit.path}:{hit.line} {hit.pattern} {preview}"


# Planted secrets are built by concatenation so this file never matches itself.
PLANTED: dict[str, str] = {
    "openai_style_sk": "key = sk-" + "proj-" + "a1B2" * 6,
    "baseten_key": "abcd1234" + "." + "Z9y8" * 8,
    "api_key_header": "Api-Key " + "q" * 8 + "w" * 8,
    "bearer_token": "Bearer " + "eyJ" + "x" * 20,
    "authorization_header": '"Authorization": "' + "token " + "abc" + '"',
    "github_token": "gh" + "p_" + "A1" * 18,
    "github_pat": "github" + "_pat_" + "B2" * 15,
    "aws_access_key": "AK" + "IA" + "Q" * 16,
    "aws_secret_key": "aws_secret_access_key = " + "x/Y+" * 10,
    "named_key_quoted": '"MODEL_' + 'API_KEY": "' + "plain-value" + '"',
    "named_key_assigned": "BASETEN_" + "API_KEY=" + "plainvalue",
    "private_key": "-----BEGIN " + "RSA PRIVATE KEY-----",
    "huggingface_token": "hf" + "_" + "C3" * 16,
}

REFERENCES = [
    "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
    'GITHUB_TOKEN="$(gh auth token)"',
    "PASS GITHUB_TOKEN: authenticated as vedntzz",
    'KEYS = ("GITHUB_TOKEN", "MODEL_API_KEY", "BASETEN_API_KEY")',
    'curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com',
    "Authorization: Bearer $GITHUB_TOKEN",
    "${GITHUB_TOKEN}",
    "Authorization: Bearer ${GITHUB_TOKEN}",
    'curl -H "Authorization: Bearer $(cat "$KNACK_HOME/github_token")"',
]


@pytest.mark.parametrize("pattern", sorted(PLANTED))
def test_every_pattern_catches_its_planted_secret(pattern: str) -> None:
    found = {hit.pattern for hit in leaks_in_text("x.py", PLANTED[pattern])}
    assert pattern in found


@pytest.mark.parametrize("line", REFERENCES)
def test_a_reference_to_a_secret_is_not_a_leak(line: str) -> None:
    assert leaks_in_text("x.yml", line) == []


def test_a_real_token_behind_authorization_bearer_is_still_a_leak() -> None:
    line = "Authorization: Bearer " + "gh" + "p_" + "k7Qm2Xv9" * 5
    found = {hit.pattern for hit in leaks_in_text("x.sh", line)}
    assert "authorization_header" in found and "github_token" in found


def test_placeholder_is_allowed_only_in_the_file_that_uses_it() -> None:
    line = 'auth = "Bearer t0ken"' + '\n"GITHUB_TOKEN": "t0ken"'
    assert leaks_in_text("tests/guard/test_pr_comment.py", line) == []
    assert [h.value for h in leaks_in_text("knack/x.py", line)] == ["t0ken"]


def test_failure_message_never_prints_the_full_secret() -> None:
    secret = "gh" + "p_" + "Z" * 36
    [hit] = leaks_in_text("x.py", secret)
    assert secret not in describe(hit) and "x.py:1" in describe(hit)


def test_no_tracked_file_holds_a_secret() -> None:
    leaks = [hit for path in tracked_files() for hit in leaks_in_file(path)]
    assert leaks == [], "\n".join(describe(hit) for hit in leaks)
