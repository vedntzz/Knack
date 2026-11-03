import json
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from knack.console.app import create_app
from knack.day.feed import Day
from knack.receipts.chain import (
    append_receipt,
    load_receipts,
    Receipt,
    Resolution,
    resolution_receipt,
)
from test_verdict_page import visible

REPO_ROOT = Path(__file__).parents[2]
STATIC = REPO_ROOT / "knack" / "console" / "static"
TEMPLATES = REPO_ROOT / "knack" / "console" / "templates"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "console_75025"
DATA_REGISTRY = REPO_ROOT / "data" / "registry" / "airflow.json"
DATA_ROOTS = REPO_ROOT / "data" / "roots" / "airflow"
FASTAPI_REGISTRY = REPO_ROOT / "data" / "registry" / "fastapi.json"
FASTAPI_ROOTS = REPO_ROOT / "data" / "roots" / "fastapi"
# The fixture's deny landed at 02:06 UTC on Nov 2; the page is read later that day.
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
DENY = "08a2c39bcceddafae995781163b6e8ea17ab0f02c2cb4e48a65bf3cc3a097f3c"
HTML = {"accept": "text/html,application/xhtml+xml"}
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
POLL = 0.02


class DayConsole:
    # An apache/airflow clone, the airflow registry and roots, and the 75025 receipts.
    origin = "https://github.com/apache/airflow.git"
    data_registry, data_roots = DATA_REGISTRY, DATA_ROOTS

    def __init__(self, base: Path) -> None:
        shutil.copytree(FIXTURE, base / "knack")
        self.receipts = base / "knack" / "verdicts.jsonl"
        self.roots = base / "roots"
        shutil.copytree(self.data_roots, self.roots)
        self.registry: Path | None = base / "registry.json"
        body = json.loads(self.data_registry.read_text())
        body |= {"roots_dir": str(self.roots)}
        self.registry.write_text(json.dumps(body))
        self.clone = base / "airflow"
        self.init_clone()

    def init_clone(self) -> None:
        self.clone.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("remote", "add", "origin", self.origin)
        self.git("commit", "-q", "--allow-empty", "-m", "Sort runs by last_run_state")

    def git(self, *args: str) -> None:
        stamp = "2026-11-02T09:30:00+00:00"
        env = os.environ | {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
        who = ["-c", "user.name=Dana Lee", "-c", "user.email=dana@example.com"]
        git = ["git", "-C", str(self.clone), *who, "-c", "commit.gpgsign=false"]
        subprocess.run([*git, *args], env=env, check=True, capture_output=True)

    def deny(self) -> Receipt:
        return next(r for r in load_receipts(self.receipts) if r.hash == DENY)

    def resolve(self, action: str, at: str = "2026-11-02T03:00:00+00:00") -> Receipt:
        settled = {"of": DENY, "action": action, "by": "maria", "reason": "it stands"}
        fields = resolution_receipt(self.deny(), Resolution.model_validate(settled), at)
        return append_receipt(self.receipts, fields)

    def registry_for(self, repo: str) -> Path | None:
        return self.registry

    def day(self) -> Day:
        return Day(
            clone=self.clone,
            clock=lambda: NOW,
            receipts=self.receipts,
            warns=self.receipts.with_name("warns.jsonl"),
            rulings=self.receipts.with_name("rulings.jsonl"),
            pulls=None,
            registry_for=self.registry_for,
        )

    def client(self) -> TestClient:
        base = self.receipts.parent
        places = (self.receipts, base / "warns.jsonl", base / "rulings.jsonl")
        app = create_app(*places, self.registry_for, self.day(), poll_seconds=POLL)
        return TestClient(app)

    def page(self) -> str:
        response = self.client().get("/", headers=HTML)
        assert response.status_code == 200
        return response.text

    def graph(self) -> dict[str, Any]:
        response = self.client().get("/graph")
        assert response.status_code == 200
        return response.json()


class FastapiDayConsole(DayConsole):
    # The same console on a fastapi/fastapi clone with the fastapi registry and roots.
    origin = "https://github.com/fastapi/fastapi.git"
    data_registry, data_roots = FASTAPI_REGISTRY, FASTAPI_ROOTS


class KnackCloneDayConsole(DayConsole):
    # The airflow registry read from a clone of Knack itself, as KNACK_REGISTRY allows.
    origin = "https://github.com/vedntzz/Knack.git"


@pytest.fixture
def world(tmp_path: Path) -> DayConsole:
    return DayConsole(tmp_path)


@pytest.fixture
def fastapi_world(tmp_path: Path) -> DayConsole:
    return FastapiDayConsole(tmp_path)


def on(graph: dict[str, Any], date: str) -> dict[str, Any]:
    return next(day for day in graph["days"] if day["date"] == date)


def split(graph: dict[str, Any], date: str) -> tuple[int, int]:
    day = on(graph, date)
    return day["confirmed"], day["advisory"]


def cell(html: str, date: str) -> str:
    # A cell runs to the next cell or the end of its week.
    pattern = (
        rf'<span class="cell[^"]*" data-date="{date}".*?(?=<span class="cell|</div>)'
    )
    found = re.search(pattern, html)
    assert found, date
    return found.group(0)


def test_graph_counts_every_root_on_the_day_its_pr_merged(world: DayConsole) -> None:
    graph = world.graph()
    assert graph["repo"] == "apache/airflow" and graph["today"] == "2026-11-02"
    assert split(graph, "2026-10-19") == (1, 0)
    assert split(graph, "2026-10-27") == (0, 2)
    assert split(graph, "2026-10-28") == (4, 2)
    merged = sum(day["confirmed"] + day["advisory"] for day in graph["days"])
    assert merged == len(list(DATA_ROOTS.glob("*.json"))) == 9


def test_graph_spans_whole_weeks_ending_today(world: DayConsole) -> None:
    graph = world.graph()
    first = datetime.fromisoformat(graph["days"][0]["date"])
    assert first.weekday() == 6 and graph["days"][-1]["date"] == "2026-11-02"
    assert len(graph["days"]) == (graph["weeks"] - 1) * 7 + 2


def test_graph_names_the_prs_and_authors_of_each_day(world: DayConsole) -> None:
    oct19 = on(world.graph(), "2026-10-19")
    assert oct19["prs"] == ["#75025"] and oct19["authors"] == ["Pushkal Gupta"]


def test_confirmed_days_shade_a_step_above_inferred_only_days(
    world: DayConsole,
) -> None:
    graph = world.graph()
    steps = {
        d: on(graph, d)["step"] for d in ("2026-10-19", "2026-10-27", "2026-10-28")
    }
    # One meaning per step: advise only, one confirmed, confirmed among more.
    assert steps == {"2026-10-19": 2, "2026-10-27": 1, "2026-10-28": 3}
    assert on(graph, "2026-10-20")["step"] == 0
    assert {day["step"] for day in graph["days"]} <= {0, 1, 2, 3}


def test_graph_counts_blocks_from_the_full_history(world: DayConsole) -> None:
    graph = world.graph()
    assert on(graph, "2026-11-02")["blocks"] == 1
    assert sum(day["blocks"] for day in graph["days"]) == 1


def test_an_uphold_is_a_resolution_not_a_new_block(world: DayConsole) -> None:
    world.resolve("uphold")
    nov2 = on(world.graph(), "2026-11-02")
    assert nov2["blocks"] == 1 and nov2["resolutions"] == ["uphold"]


def test_headline_counts_every_root_and_splits_confirmed_from_advisory(
    world: DayConsole,
) -> None:
    text = visible(world.page())
    assert "apache/airflow remembers 9 decisions." in text
    assert "5 confirmed to block · 4 advise only" in text


def test_a_block_day_carries_the_red_dot(world: DayConsole) -> None:
    html = world.page()
    assert 'class="mark block"' in cell(html, "2026-11-02")
    assert "mark" not in cell(html, "2026-10-19")


def test_a_resolved_day_carries_the_paper_dot(world: DayConsole) -> None:
    world.resolve("allow")
    assert 'class="mark person"' in cell(world.page(), "2026-11-02")


def test_each_cell_says_date_count_pr_and_author(world: DayConsole) -> None:
    found = cell(world.page(), "2026-10-19")
    assert 'aria-label="Oct 19 2026 · 1 decision · #75025 · Pushkal Gupta"' in found


def test_an_uphold_is_labelled_uphold_never_learn(world: DayConsole) -> None:
    world.resolve("uphold")
    text = visible(world.page())
    assert "Upheld by maria" in text
    assert "learn" not in text.lower()


def test_allow_and_retire_are_labelled_by_their_kind(world: DayConsole) -> None:
    world.resolve("retire", at="2026-11-02T04:00:00+00:00")
    assert "Retired by maria" in visible(world.page())


def test_confirmed_decisions_read_as_plain_lines_with_who_and_when(
    world: DayConsole,
) -> None:
    text = visible(world.page())
    assert "the latest run is sorted only as last_run_state" in text
    for said in ("Pushkal Gupta", "#75025", "Oct 19 2026", "Vedant Srivastava"):
        assert said in text
    assert "Confirmer not recorded" not in text
    assert "#75774 · merged Oct 28 2026 · confirmed by Vedant Srivastava" in text
    assert "raising AirflowSensorTimeout past the deadline" in text
    assert (
        "dabla · #75271 · merged Oct 28 2026 · confirmed by Vedant Srivastava" in text
    )
    assert "ResumableJobMixin stand-in as bool | None" in text


def test_fastapi_confirmed_decisions_name_the_decider_and_the_confirmer(
    fastapi_world: DayConsole,
) -> None:
    text = visible(fastapi_world.page())
    confirmed = text.split("Confirmed decisions")[1].split("Today")[0]
    for line in (
        "tiangolo · #14884 · merged Feb 10 2026 · confirmed by Vedant Srivastava",
        "Zawwarsami16 · #15515 · merged Jul 28 2026 · confirmed by Vedant Srivastava",
    ):
        assert line in confirmed


def test_fastapi_headline_splits_its_two_confirmed_from_advisory(
    fastapi_world: DayConsole,
) -> None:
    text = visible(fastapi_world.page())
    assert "fastapi/fastapi remembers 13 decisions." in text
    assert "2 confirmed to block · 11 advise only" in text


def test_today_lists_the_clones_commits_and_says_why_prs_are_missing(
    world: DayConsole,
) -> None:
    text = visible(world.page())
    assert "Sort runs by last_run_state" in text
    assert "Pull requests not recorded: GITHUB_TOKEN is not set" in text
    assert "Blocked an edit against airflow-75025-1" in text


def test_today_shows_no_commits_from_a_clone_of_another_repo(tmp_path: Path) -> None:
    text = visible(KnackCloneDayConsole(tmp_path).page())
    assert "apache/airflow remembers" in text
    assert "Sort runs by last_run_state" not in text
    assert "Pull requests not recorded" not in text
    said = "Commits not recorded: this console runs in a clone of vedntzz/knack"
    assert said in text


def test_the_bar_names_no_branch_from_a_clone_of_another_repo(tmp_path: Path) -> None:
    html = KnackCloneDayConsole(tmp_path).page()
    assert "Branch not recorded" in visible(html) and "/ main" not in visible(html)


def test_75774_reads_once_with_both_rejected_alternatives(world: DayConsole) -> None:
    text = visible(world.page())
    confirmed = text.split("Confirmed decisions")[1].split("Today")[0]
    assert confirmed.count("#75774") == 1
    for offered in (
        "sliding re-defer timeout that put timeout=self.timeout",
        "TimeDeltaTrigger sleep defer with no deadline",
    ):
        assert offered in confirmed


def test_the_last_receipt_and_the_verify_command_each_copy(world: DayConsole) -> None:
    html = world.page()
    assert f'data-copy-text="{DENY}"' in html
    assert f'data-copy-text="knack receipts verify --path {world.receipts}"' in html
    assert "Rule airflow-75025 · decision confirmed" in visible(html)


def test_a_missing_registry_says_so_and_invents_nothing(world: DayConsole) -> None:
    world.registry = None
    text = visible(world.page())
    assert "Decisions not recorded" in text and "remembers" not in text
    assert sum(day["step"] for day in world.graph()["days"]) == 0


def test_no_receipts_reads_as_a_gap(world: DayConsole) -> None:
    world.receipts.write_text("")
    assert "Last receipt not recorded" in visible(world.page())


def test_the_home_page_still_listens_for_the_next_deny(world: DayConsole) -> None:
    html = world.page()
    assert 'data-events="/events"' in html and "/static/live.js" in html


def test_a_new_deny_is_announced_while_the_home_page_is_open(
    world: DayConsole,
) -> None:
    later = json.loads(world.receipts.read_text().splitlines()[-1]) | {"hash": "f" * 64}
    writer = threading.Thread(target=lambda: (time.sleep(0.2), append(world, later)))
    writer.start()
    with world.client().stream("GET", "/events") as response:
        lines = (line for line in response.iter_lines() if line.startswith("data: "))
        assert next(lines) == "data: " + "f" * 64
        writer.join()


def append(world: DayConsole, fields: dict[str, Any]) -> None:
    with world.receipts.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(fields) + "\n")


def test_without_a_day_the_home_page_still_waits(world: DayConsole) -> None:
    base = world.receipts.parent
    places = (world.receipts, base / "warns.jsonl", base / "rulings.jsonl")
    page = TestClient(create_app(*places, world.registry_for)).get("/", headers=HTML)
    assert "Waiting for the next block." in page.text


def test_no_stylesheet_holds_a_raw_hex() -> None:
    for sheet in STATIC.glob("*.css"):
        if sheet.name != "tokens.css":
            assert HEX.findall(sheet.read_text(encoding="utf-8")) == [], sheet.name


def test_the_day_page_has_its_own_stylesheet_template_and_router() -> None:
    assert (STATIC / "day.css").exists() and (STATIC / "day.js").exists()
    assert "<html" not in (TEMPLATES / "day.html").read_text(encoding="utf-8")
    router = (REPO_ROOT / "knack" / "console" / "pages" / "day.py").read_text()
    assert "APIRouter" in router and "def day_router" in router


def test_cells_fade_by_week_inside_600_ms_and_hold_still_when_reduced() -> None:
    script = (STATIC / "day.js").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in script
    assert 52 * constant(script, "STEP_MS") + constant(script, "FADE_MS") < 600


def constant(script: str, name: str) -> int:
    found = re.search(rf"{name} = (\d+)", script)
    assert found, name
    return int(found.group(1))


def test_the_bar_names_the_last_receipt_not_a_current_block(world: DayConsole) -> None:
    text = visible(world.page())
    assert "Last receipt: blocked" in text


def test_the_record_counts_events_not_the_decisions_again(world: DayConsole) -> None:
    world.resolve("uphold")
    assert "In 53 weeks: 1 block, 1 resolved by a person." in visible(world.page())
