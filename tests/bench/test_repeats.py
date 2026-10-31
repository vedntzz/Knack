import subprocess
from pathlib import Path

import pytest
from knack import cli
from knack.bench.repeats import Hunt, hunt_registry, is_bot, repeats_markdown

FIXTURES = Path(__file__).parent / "fixtures" / "repeats"
REGISTRY = FIXTURES / "registry.json"
HUMAN = ("Ada Human", "ada@example.com")
BOT = ("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com")


def git(repo: Path, *args: str, author: tuple[str, str] = HUMAN) -> str:
    name, email = author
    who = ["-c", f"user.name={name}", "-c", f"user.email={email}"]
    done = subprocess.run(
        ["git", "-C", str(repo), *who, *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def commit(
    repo: Path,
    files: dict[str, str],
    message: str,
    author: tuple[str, str] = HUMAN,
    date: str = "2026-01-01T00:00:00+00:00",
) -> str:
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    unsigned = ["-c", "commit.gpgsign=false", "commit", "-q", f"--date={date}"]
    git(repo, *unsigned, "-m", message, author=author)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def history(tmp_path: Path) -> dict[str, str]:
    # One file, the decision (#7), then: a move, a bot repeat, a new-file repeat,
    # a duplicated old line, a rename, and a commit touching only a non-Python file.
    repo = tmp_path / "demo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    shas: dict[str, str] = {"repo": str(repo)}
    old = "x = eval(a)\ny = 1\n"
    shas["before"] = commit(repo, {"app.py": old}, "Start")
    shas["pre"] = commit(repo, {"app.py": old + "z = eval(p)\n"}, "Pre-decision eval")
    shas["decision"] = commit(
        repo,
        {"app.py": "x = eval(a)\ny = 1\nz = 2\n"},
        "Parse settings instead of eval (#7)",
        date="2026-02-01T00:00:00+00:00",
    )
    shas["move"] = commit(repo, {"app.py": "y = 1\nz = 2\nx = eval(a)\n"}, "Move")
    shas["bot"] = commit(
        repo,
        {"app.py": "y = 1\nz = 2\nx = eval(a)\nw = eval(b)\n"},
        "Bump",
        author=BOT,
        date="2026-03-01T00:00:00+00:00",
    )
    shas["new_file"] = commit(repo, {"pkg/new.py": "v = eval(c)\n"}, "New module")
    shas["dup"] = commit(
        repo,
        {"app.py": "y = 1\nz = 2\nx = eval(a)\nw = eval(b)\nx = eval(a)\n"},
        "Duplicate",
    )
    git(repo, "mv", "pkg/new.py", "pkg/renamed.py")
    shas["rename"] = commit(repo, {}, "Rename")
    shas["docs"] = commit(repo, {"README.md": "eval(d)\n"}, "Docs")
    return shas


def hunted(history: dict[str, str]) -> list[Hunt]:
    return hunt_registry(REGISTRY, Path(history["repo"]))


def test_finds_the_decision_merge_by_its_pr_number(history: dict[str, str]) -> None:
    hunt = hunted(history)[0]
    assert (hunt.pr, hunt.merge) == (7, history["decision"])
    assert hunt.merge_date.startswith("2026-02-01")
    assert hunt.decision == "Parse settings with ast.literal_eval, never eval"


def test_scans_every_commit_after_the_merge(history: dict[str, str]) -> None:
    assert hunted(history)[0].scanned == 6


def test_repeats_are_only_new_matches_on_added_lines(history: dict[str, str]) -> None:
    # The pre-decision eval, the move, the rename and the Markdown file never count.
    found = [
        (r.commit, r.file, r.line, r.matched_text) for r in hunted(history)[0].repeats
    ]
    assert found == [
        (history["bot"], "app.py", 4, "eval(b)"),
        (history["new_file"], "pkg/new.py", 1, "eval(c)"),
        (history["dup"], "app.py", 5, "eval(a)"),
    ]


def test_authors_are_labelled_human_or_bot(history: dict[str, str]) -> None:
    repeats = hunted(history)[0].repeats
    assert [(r.author, r.bot) for r in repeats] == [
        ("dependabot[bot]", True),
        ("Ada Human", False),
        ("Ada Human", False),
    ]
    assert repeats[0].date.startswith("2026-03-01")


def test_a_decision_with_no_merge_commit_is_reported_not_guessed(
    history: dict[str, str],
) -> None:
    hunt = hunted(history)[1]
    assert (hunt.pr, hunt.merge, hunt.scanned, hunt.repeats) == (9, None, 0, [])


@pytest.mark.parametrize(
    ("name", "email", "bot"),
    [
        (
            "github-actions[bot]",
            "41898282+github-actions[bot]@users.noreply.github.com",
            True,
        ),
        (
            "pre-commit-ci[bot]",
            "66853113+pre-commit-ci[bot]@users.noreply.github.com",
            True,
        ),
        ("Ada Human", "ada@example.com", False),
        ("Abbot Smith", "abbot@example.com", False),
    ],
)
def test_bot_is_the_github_bot_suffix(name: str, email: str, bot: bool) -> None:
    assert is_bot(name, email) is bot


def test_markdown_lists_each_repeat_under_its_decision(
    history: dict[str, str],
) -> None:
    text = repeats_markdown(hunted(history))
    assert "## demo/demo #7: Parse settings with ast.literal_eval, never eval" in text
    assert f"| `{history['bot'][:10]}` | dependabot[bot] | bot | 2026-03-01 |" in text
    assert "`app.py:4` `eval(b)`" in text
    assert "## demo/demo #9: Never exec generated code" in text
    assert "No merge commit for #9 on the scanned branch." in text


def test_markdown_says_so_when_nothing_repeated(tmp_path: Path) -> None:
    repo = tmp_path / "clean"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    commit(repo, {"app.py": "x = 1\n"}, "Parse settings instead of eval (#7)")
    commit(repo, {"app.py": "x = 2\n"}, "Tidy")
    text = repeats_markdown(hunt_registry(REGISTRY, repo))
    assert "1 commit(s) scanned after it. No repeats." in text


def test_cli_writes_the_report(history: dict[str, str], tmp_path: Path) -> None:
    out = tmp_path / "REPEATS.md"
    argv = ["bench", "repeats", "--target", str(REGISTRY), history["repo"]]
    assert cli.main([*argv, "--out", str(out)]) == 0
    assert "| dependabot[bot] | bot |" in out.read_text(encoding="utf-8")
