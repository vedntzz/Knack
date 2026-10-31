import re
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from knack.guard.check import only_new
from knack.guard.runner import GuardRunnerError, RuleMatch, scan_file_with_rule
from knack.roots.store import load_roots
from knack.walk.registry import load_registry, RegistryEntry

PR_NUMBER = re.compile(r"/pull/(\d+)")
HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
# Each commit's header in git log; a record separator never starts a patch line.
COMMIT_MARK = "\x1e"
LOG_FORMAT = f"{COMMIT_MARK}%H%x00%an%x00%ae%x00%aI"
GIT_TIMEOUT_SECONDS = 600
LANGUAGE_PATHSPECS = {"python": ["*.py", "*.pyi"]}
SHORT_SHA = 10
MAX_CELL_TEXT = 120
SUMMARY_HEADER = (
    "| Repo | Decision | Merged | Commits scanned | Repeat commits | Human | Bot |"
)
REPEAT_HEADER = "| Commit | Author | Who | Date | Matched lines |"


@dataclass(frozen=True)
class Repeat:
    commit: str
    author: str
    email: str
    bot: bool
    date: str
    file: str
    line: int
    matched_text: str


@dataclass(frozen=True)
class Hunt:
    repo: str
    pr: int
    decision: str
    rule: Path
    head: str
    merge: str | None = None
    merge_date: str = ""
    scanned: int = 0
    repeats: list[Repeat] = field(default_factory=list[Repeat])
    # Files ast-grep could not scan (a timeout, say), as commit:path.
    errors: list[str] = field(default_factory=list[str])


@dataclass(frozen=True)
class Author:
    commit: str
    name: str
    email: str
    date: str


@dataclass(frozen=True)
class FileChange:
    author: Author
    old_path: str | None
    new_path: str
    added: frozenset[int]


def is_bot(name: str, email: str) -> bool:
    # GitHub App accounts carry the [bot] suffix in both name and noreply email.
    return "[bot]" in name.lower() or "[bot]" in email.lower()


def hunt_registry(registry_path: Path, clone: Path) -> list[Hunt]:
    # One hunt per registry rule, over the first-parent history of clone's HEAD.
    registry = load_registry(registry_path)
    roots = {root.id: root for root in load_roots(registry.roots_dir)}
    head = _git(clone, "rev-parse", "HEAD").strip()
    hunts = list[Hunt]()
    for entry in registry.rules:
        root = roots[entry.root_ids[0]]
        pr = int(_pr_number(str(root.source_url)))
        start = Hunt(registry.repo, pr, root.decision, entry.rule, head)
        hunts.append(hunt_rule(clone, entry, start))
    return hunts


def _pr_number(url: str) -> str:
    found = PR_NUMBER.search(url)
    if found is None:
        raise ValueError(f"no PR number in {url}")
    return found.group(1)


def hunt_rule(clone: Path, entry: RegistryEntry, hunt: Hunt) -> Hunt:
    merge = merge_commit(clone, hunt.pr, hunt.head)
    if merge is None:
        return hunt
    merge_date = _git(clone, "log", "-1", "--format=%aI", merge).strip()
    span = f"{merge}..{hunt.head}"
    scanned = int(_git(clone, "rev-list", "--first-parent", "--count", span))
    repeats, errors = _repeats(clone, entry.rule, span)
    return Hunt(
        hunt.repo, hunt.pr, hunt.decision, hunt.rule, hunt.head,
        merge, merge_date, scanned, repeats, errors,
    )  # fmt: skip


def merge_commit(clone: Path, pr: int, head: str) -> str | None:
    # The oldest first-parent commit whose subject closes with (#pr), the squash
    # convention, or a "Merge pull request #pr" commit; a revert names it mid-line.
    log = _git(clone, "log", "--first-parent", "--format=%H%x00%s", head)
    for line in reversed(log.split("\n")):
        sha, _, subject = line.partition("\x00")
        if subject.endswith(f"(#{pr})") or subject.startswith(
            f"Merge pull request #{pr} "
        ):
            return sha
    return None


def _repeats(clone: Path, rule: Path, span: str) -> tuple[list[Repeat], list[str]]:
    repeats, errors = list[Repeat](), list[str]()
    with tempfile.TemporaryDirectory() as scratch:
        for change in file_changes(clone, span, _pathspecs(rule)):
            try:
                found = new_on_added_lines(clone, change, rule, Path(scratch))
            except GuardRunnerError:
                errors.append(f"{change.author.commit[:SHORT_SHA]}:{change.new_path}")
                continue
            repeats.extend(_repeat(change, match) for match in found)
    return repeats, errors


def _pathspecs(rule: Path) -> list[str]:
    # Only files in the rule's language; an unknown language means every file.
    found = re.search(r"^language:\s*(\S+)", rule.read_text(encoding="utf-8"), re.M)
    return LANGUAGE_PATHSPECS.get(found.group(1).lower(), []) if found else []


def file_changes(clone: Path, span: str, pathspecs: list[str]) -> list[FileChange]:
    # Oldest first; each merge is diffed against its first parent, renames followed.
    log = _git(
        clone, "-c", "core.quotePath=false", "log", "--first-parent", "--reverse",
        "--diff-merges=first-parent", "-M", "-U0", "--no-color", "--no-ext-diff",
        f"--format={LOG_FORMAT}", "-p", span, "--", *pathspecs,
    )  # fmt: skip
    # Not splitlines(): it also breaks on the record separator COMMIT_MARK.
    return _parse_log(log.split("\n"))


def _parse_log(lines: list[str]) -> list[FileChange]:
    changes = list[FileChange]()
    author: Author | None = None
    old: str | None = None
    new: str | None = None
    added = set[int]()
    pending = 0
    for line in lines:
        if pending:
            # Hunk body: count down its lines so none is read as a header;
            # "\ No newline at end of file" is not one of them.
            pending -= not line.startswith("\\")
            continue
        if line.startswith(COMMIT_MARK) or line.startswith("diff --git "):
            _close(changes, author, old, new, added)
            old, new, added = None, None, set[int]()
            if line.startswith(COMMIT_MARK):
                author = Author(*line[1:].split("\x00"))
        elif line.startswith("--- "):
            old = _diff_path(line[4:], "a/")
        elif line.startswith("+++ "):
            new = _diff_path(line[4:], "b/")
        elif hunk := HUNK.match(line):
            removed, start, count = hunk.groups()
            count_new = 1 if count is None else int(count)
            added |= set(range(int(start), int(start) + count_new))
            pending = (1 if removed is None else int(removed)) + count_new
    _close(changes, author, old, new, added)
    return changes


def _close(
    changes: list[FileChange],
    author: Author | None,
    old: str | None,
    new: str | None,
    added: set[int],
) -> None:
    # Deleted files and pure renames add no lines, so they cannot repeat.
    if author is not None and new is not None and added:
        changes.append(FileChange(author, old, new, frozenset(added)))


def _diff_path(raw: str, prefix: str) -> str | None:
    path = raw.rstrip("\t").strip('"')
    if path == "/dev/null":
        return None
    return path.removeprefix(prefix)


def new_on_added_lines(
    clone: Path, change: FileChange, rule: Path, scratch: Path
) -> list[RuleMatch]:
    # The guard's only-new comparison decides how many of each match text are new;
    # the diff decides which of them this commit wrote.
    commit = change.author.commit
    after = _scan_blob(clone, f"{commit}:{change.new_path}", rule, scratch)
    on_added = [match for match in after if _touches(match, change.added)]
    if not on_added:
        return []
    before = (
        _scan_blob(clone, f"{commit}^:{change.old_path}", rule, scratch)
        if change.old_path
        else []
    )
    left = Counter(match.matched_text for match in only_new(after, before))
    kept = list[RuleMatch]()
    for match in on_added:
        if left[match.matched_text] > 0:
            left[match.matched_text] -= 1
            kept.append(match)
    return kept


def _touches(match: RuleMatch, added: frozenset[int]) -> bool:
    span = range(match.line, match.line + match.matched_text.count("\n") + 1)
    return not added.isdisjoint(span)


def _scan_blob(clone: Path, spec: str, rule: Path, scratch: Path) -> list[RuleMatch]:
    # ast-grep scans files, so the blob is written out under its own file name.
    path = scratch / Path(spec.partition(":")[2]).name
    path.write_bytes(_git_bytes(clone, "show", spec))
    try:
        return scan_file_with_rule(path, rule)
    finally:
        path.unlink()


def _repeat(change: FileChange, match: RuleMatch) -> Repeat:
    who = change.author
    return Repeat(
        who.commit, who.name, who.email, is_bot(who.name, who.email), who.date,
        change.new_path, match.line, match.matched_text,
    )  # fmt: skip


def _git(clone: Path, *args: str) -> str:
    return _git_bytes(clone, *args).decode("utf-8", errors="replace")


def _git_bytes(clone: Path, *args: str) -> bytes:
    done = subprocess.run(
        ["git", "-C", str(clone), *args],
        capture_output=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=True,
    )
    return done.stdout


def repeats_markdown(hunts: list[Hunt]) -> str:
    intro = (
        "For each rule in a registry: every first-parent commit on the clone's "
        "default branch after the decision's PR merged. A repeat is a rule match "
        "on a line the commit added that the file did not already have (the "
        "guard's only-new comparison). Bots are GitHub `[bot]` accounts."
    )
    summary = [SUMMARY_HEADER, _divider(SUMMARY_HEADER), *map(_summary_row, hunts)]
    body = [line for hunt in hunts for line in _section(hunt)]
    return "\n".join(["# Repeats after each decision", "", intro, "", *summary, *body])


def _summary_row(hunt: Hunt) -> str:
    if hunt.merge is None:
        return _row([hunt.repo, f"#{hunt.pr}", "not found", "0", "0", "0", "0"])
    commits = _by_commit(hunt.repeats)
    bots = sum(group[0].bot for group in commits)
    cells = [hunt.repo, f"#{hunt.pr}", hunt.merge_date[:10], str(hunt.scanned)]
    return _row([*cells, str(len(commits)), str(len(commits) - bots), str(bots)])


def _section(hunt: Hunt) -> list[str]:
    heading = ["", f"## {hunt.repo} #{hunt.pr}: {hunt.decision}", ""]
    if hunt.merge is None:
        return [*heading, f"No merge commit for #{hunt.pr} on the scanned branch."]
    where = (
        f"Rule `{hunt.rule.name}`; merged in `{hunt.merge[:SHORT_SHA]}` on "
        f"{hunt.merge_date[:10]}; scanned to `{hunt.head[:SHORT_SHA]}`; "
        f"{hunt.scanned} commit(s) scanned after it."
    )
    errors = [f"Not scanned (ast-grep failed): {', '.join(hunt.errors)}."] * bool(
        hunt.errors
    )
    if not hunt.repeats:
        return [*heading, f"{where} No repeats.", *errors]
    rows = [_repeat_row(group) for group in _by_commit(hunt.repeats)]
    return [*heading, where, *errors, "", REPEAT_HEADER, _divider(REPEAT_HEADER), *rows]


def _by_commit(repeats: list[Repeat]) -> list[list[Repeat]]:
    groups: dict[str, list[Repeat]] = {}
    for repeat in repeats:
        groups.setdefault(repeat.commit, []).append(repeat)
    return list(groups.values())


def _repeat_row(group: list[Repeat]) -> str:
    first = group[0]
    matched = "<br>".join(f"`{r.file}:{r.line}` {_code(r.matched_text)}" for r in group)
    who = "bot" if first.bot else "human"
    commit = f"`{first.commit[:SHORT_SHA]}`"
    return _row([commit, first.author, who, first.date[:10], matched])


def _code(text: str) -> str:
    # The match's first line, shortened, as inline code safe inside a table cell.
    lines = text.splitlines() or [""]
    line = lines[0].strip()
    more = len(lines) > 1 or len(line) > MAX_CELL_TEXT
    shown = line[:MAX_CELL_TEXT].replace("|", "\\|").replace("`", "'")
    return f"`{shown}`" + (" …" if more else "")


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _divider(header: str) -> str:
    return "|" + "---|" * (header.count("|") - 1)
