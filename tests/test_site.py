import json
import os
import re
import struct
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parents[1]
SITE = REPO_ROOT / "site"
INDEX = SITE / "index.html"
README = REPO_ROOT / "README.md"
VENV_BIN = REPO_ROOT / ".venv" / "bin"
CONSOLE_STATIC = REPO_ROOT / "knack" / "console" / "static"
ONE_STORY = REPO_ROOT / "mockups" / "fixtures" / "one_story"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pages.yml"
HEADLINE = "Your AI agent never read the PR where you said no. Knack did."
CAPTURE = "block-0e7ab6083866-1080p.png"
PHONE_CAPTURE = "block-0e7ab6083866-390.png"
LATENCY = "mockups/fixtures/one_story/latency.json"
RECEIPTS = "knack receipts verify --path mockups/fixtures/one_story/receipts.jsonl"
GUARD_MS = f"jq .block.guard_ms {LATENCY}"
ROUND_TRIP = f"jq .wall_ms.block {LATENCY}"
# The page's figures: what each shows and the command that prints its source.
FIGURE = re.compile(r'<figure class="figure">(.*?)</figure>', re.S)
COPY = re.compile(r'data-copy-text="([^"]*)"')
ASSET = re.compile(r'(?:src|href)="([^"#:]+)"|url\("?([^")]+)"?\)')
PHONE_SOURCE = re.compile(r'<source media="\(max-width: 47.5rem\)" srcset="([^"]+)"')
CAPTION = re.compile(r"<figcaption>(.*?)</figcaption>", re.S)
GRID_75025 = re.compile(r"^\| apache/airflow #75025 \|.*block( \| PASS){8} \|", re.M)
EXTERNAL = re.compile(r'(?:src|href)="(https?://[^"]+)"')


def html() -> str:
    return INDEX.read_text(encoding="utf-8")


def unescaped(text: str) -> str:
    return text.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<")


def text_of(fragment: str) -> str:
    # What a reader sees: a line-break hint joins, every other tag parts words.
    joined = fragment.replace("<wbr>", "")
    return " ".join(unescaped(re.sub(r"<[^>]+>", " ", joined)).split())


def section(element_id: str) -> str:
    # The page's section with this id, up to its closing tag.
    start = html().index(f'id="{element_id}"')
    return html()[start : html().index("</section>", start)]


def readme_sh_after(heading: str) -> str:
    text = README.read_text(encoding="utf-8")
    start = text.index("```sh\n", text.index(f"\n{heading}\n")) + len("```sh\n")
    return text[start : text.index("\n```", start)]


def copies() -> list[str]:
    return [unescaped(found) for found in COPY.findall(html())]


def latency(path: str) -> float:
    # What `jq <path>` prints from the committed latency.json.
    value: Any = json.loads((REPO_ROOT / LATENCY).read_text(encoding="utf-8"))
    for key in path.strip(".").split("."):
        value = value[key]
    return float(value)


def figures() -> dict[str, str]:
    # Each figure's command, mapped to the figure's visible text.
    blocks = FIGURE.findall(html())
    return {unescaped(COPY.findall(b)[0]): text_of(b) for b in blocks}


def rulings() -> list[dict[str, Any]]:
    lines = (ONE_STORY / "rulings.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def png_size(path: Path) -> tuple[int, int]:
    width, height = struct.unpack(">II", path.read_bytes()[16:24])
    return width, height


def test_the_hero_is_the_headline_alone_then_the_block_capture() -> None:
    hero = section("hero")
    tags = re.findall(r"<(h1|h2|p|a|button|img|figure)\b", hero)
    assert tags[:3] == ["h1", "figure", "img"], tags
    assert text_of(re.search(r"<h1[^>]*>(.*?)</h1>", hero, re.S)[1]) == HEADLINE  # type: ignore[index]


def test_the_page_has_one_h1() -> None:
    assert html().count("<h1") == 1


def test_the_capture_is_the_one_story_block_page_at_1080p() -> None:
    assert f'src="{CAPTURE}"' in section("hero")
    assert png_size(SITE / CAPTURE) == (1920, 1080)


def test_a_phone_gets_the_block_page_as_served_at_390() -> None:
    # The console's own phone layout, at 2x, not the 1080p frame shrunk to 4 px type.
    source = PHONE_SOURCE.search(html())
    assert source and source[1] == PHONE_CAPTURE
    assert png_size(SITE / PHONE_CAPTURE)[0] == 780


def test_the_caption_sources_the_captures_own_figures() -> None:
    caption = text_of(CAPTION.findall(section("hero"))[0])
    grid = (REPO_ROOT / "bench" / "PROOF-GRID.md").read_text(encoding="utf-8")
    assert "bench/PROOF-GRID.md" in caption and "bash scripts/reproduce.sh" in caption
    assert GRID_75025.search(grid)


def test_the_capture_has_alt_text() -> None:
    [alt] = re.findall(r'<img[^>]*alt="([^"]+)"', section("hero"))
    assert "Blocked" in alt and "#75025" in alt


def test_every_local_asset_is_in_site() -> None:
    sources = [SITE / "index.html", *SITE.glob("*.css")]
    found = [a or b for s in sources for a, b in ASSET.findall(s.read_text())]
    missing = [
        f for f in found if not f.startswith("data:") and not (SITE / f).exists()
    ]
    assert found and not missing, missing


def test_nothing_external_loads_at_runtime() -> None:
    # Links to GitHub and the loopback console are anchors; nothing else leaves the page.
    loaded = re.findall(r"<(?:script|link|img|source|video)\b[^>]*>", html())
    assert not [tag for tag in loaded if EXTERNAL.search(tag)]
    assert "@import" not in "".join(p.read_text() for p in SITE.glob("*.css"))


def test_anchors_go_only_to_github_or_the_loopback_console() -> None:
    hosts = {
        re.sub(r"^https?://([^/]+).*", r"\1", url) for url in EXTERNAL.findall(html())
    }
    assert hosts <= {"github.com", "127.0.0.1:7655"}, hosts


def shared_with_console() -> list[str]:
    # The files site/ copies from the console's static folder, by the same path.
    fonts = sorted(p.name for p in (CONSOLE_STATIC / "fonts").iterdir())
    return ["tokens.css", *(f"fonts/{f}" for f in fonts)]


def same_as_console(name: str) -> bool:
    return (SITE / name).read_bytes() == (CONSOLE_STATIC / name).read_bytes()


def test_tokens_and_fonts_are_the_consoles_byte_for_byte() -> None:
    assert not [n for n in shared_with_console() if not same_as_console(n)]


def test_install_is_the_readmes_setup_block_with_copy() -> None:
    assert readme_sh_after("## Get it running") in copies()


def test_the_console_command_is_the_readmes_with_copy() -> None:
    assert readme_sh_after("## See it in the console") in copies()


def test_every_console_link_in_the_readme_is_on_the_page() -> None:
    from test_readme_console import console_links

    assert set(console_links()) <= set(re.findall(r'href="(http://127[^"]+)"', html()))


def test_the_repo_link_is_the_readmes_clone_url() -> None:
    [clone] = re.findall(
        r"^git clone (\S+)\.git$", README.read_text(encoding="utf-8"), re.M
    )
    assert html().count(f'href="{clone}"') >= 2


def test_every_copied_command_is_written_in_the_readme() -> None:
    readme = README.read_text(encoding="utf-8")
    assert copies() and not [c for c in copies() if c not in readme]


def test_the_figures_are_exactly_the_three_one_story_numbers() -> None:
    assert sorted(figures()) == sorted([GUARD_MS, ROUND_TRIP, RECEIPTS])


def test_the_guard_figure_is_what_its_command_prints_rounded() -> None:
    assert f"{latency('.block.guard_ms'):.1f} ms" in figures()[GUARD_MS]


def test_the_round_trip_figure_is_what_its_command_prints_rounded() -> None:
    assert f"{latency('.wall_ms.block'):.0f} ms" in figures()[ROUND_TRIP]


def test_the_receipts_figure_is_what_its_command_prints() -> None:
    argv = [str(VENV_BIN / "knack"), *RECEIPTS.split()[1:]]
    run = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True)
    printed = run.stdout.strip().split(": ", 1)[1]
    count, rest = printed.split(" receipts, ")
    assert run.returncode == 0 and f"{count} receipts" in figures()[RECEIPTS]
    assert rest in figures()[RECEIPTS]


def test_the_spike_states_both_rounded_timings() -> None:
    spike = (REPO_ROOT / "spikes" / "one_story_live.md").read_text(encoding="utf-8")
    assert f"{latency('.block.guard_ms'):.1f} ms (block)" in spike
    assert f"{latency('.wall_ms.block'):.0f} ms (block)" in spike


@pytest.mark.parametrize("decision", ["hold", "escalate"])
def test_every_model_that_ruled_is_named_with_its_host(decision: str) -> None:
    [ruling] = [r for r in rulings() if r["decision"] == decision]
    models = text_of(section("models"))
    assert all(m["model"] in models and m["host"] in models for m in ruling["models"])


def test_the_agent_is_named_as_the_rulings_record_it() -> None:
    assert {r["agent"] for r in rulings()} == {"muse-spark-1.3-contributor"}
    assert "muse-spark-1.3-contributor" in text_of(section("models"))


def test_the_demo_slot_is_labelled() -> None:
    assert "Demo video" in text_of(section("demo"))


def test_sources_cite_every_copied_command_and_the_capture() -> None:
    sources = (SITE / "SOURCES.md").read_text(encoding="utf-8")
    assert all(c.splitlines()[0] in sources for c in copies()) and CAPTURE in sources


def test_pages_workflow_publishes_site_on_push_to_main() -> None:
    flow = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"push:\s*\n\s*branches:\s*\[\s*main\s*\]", flow)
    assert re.search(
        r"upload-pages-artifact@\S+\s*\n\s*with:\s*\n\s*path:\s*site\b", flow
    )
    assert "actions/deploy-pages@" in flow and "pages: write" in flow


# The three promises: each proof is a run the repo keeps, shown as it was recorded.
PROMISES = {
    "stops": "spikes/one_story_live.md",
    "learns": "spikes/self_improving.md",
    "repairs": "spikes/self_repair_live.md",
}
SELF_REPAIR = REPO_ROOT / "mockups" / "fixtures" / "self_repair"
STEPS = "mockups/fixtures/self_repair/traces/steps/"
# The repair's logs: false-block, the confirm the gate rolled back, and the retry.
REPAIR_LOGS = {
    STEPS + "04_04_knack_false_block.txt",
    STEPS + "05_05_knack_confirm.txt",
    STEPS + "10_05b_knack_confirm_retry.txt",
}
LOG = re.compile(
    r'<pre class="log" data-source="([^"]+)"><code>(.*?)</code></pre>', re.S
)
ROOT_QUOTE = re.compile(
    r'<blockquote class="paper" data-root="([^"]+)">\s*<p>(.*?)</p>', re.S
)
STAMP = re.compile(r'<time datetime="([^"]+)">')
BLOB = "https://github.com/vedntzz/Knack/blob/main/"


def article(element_id: str) -> str:
    start = html().index(f'<article class="promise" id="{element_id}"')
    return html()[start : html().index("</article>", start)]


def run_times() -> set[str]:
    # Every receipt and ruling time in the one-story run, to the second, in UTC.
    lines = [
        *(ONE_STORY / "receipts.jsonl").read_text().splitlines(),
        *(ONE_STORY / "rulings.jsonl").read_text().splitlines(),
    ]
    return {json.loads(x)["time"][:19] + "Z" for x in lines}


@pytest.mark.parametrize("element_id,source", PROMISES.items())
def test_each_promise_links_the_run_that_shows_it(element_id: str, source: str) -> None:
    assert f'href="{BLOB}{source}"' in article(element_id)
    assert (REPO_ROOT / source).exists()


def test_every_log_line_shown_is_verbatim_in_its_run() -> None:
    logs = LOG.findall(section("promises"))
    assert {s for s, _ in logs} == {PROMISES["learns"], *REPAIR_LOGS}
    for source, body in logs:
        recorded = (REPO_ROOT / source).read_text(encoding="utf-8")
        assert not [x for x in unescaped(body).splitlines() if x not in recorded]


def test_every_quote_on_paper_is_its_roots_quote_verbatim() -> None:
    quotes = ROOT_QUOTE.findall(section("promises"))
    assert len(quotes) == 1
    for root, shown in quotes:
        quote = json.loads((REPO_ROOT / root).read_text())["quote"].replace("`", "")
        assert unescaped(re.sub(r"<[^>]+>", "", shown)) == f"“{quote}”"


def test_the_uphold_on_paper_is_the_persons_reason_verbatim() -> None:
    story = (ONE_STORY / "story.json").read_text(encoding="utf-8")
    [reason] = re.findall(
        r'<blockquote class="paper said">\s*<p>(.*?)</p>', html(), re.S
    )
    assert text_of(reason) and json.dumps(text_of(reason))[1:-1] in story


def test_every_time_in_the_story_is_a_time_the_run_recorded() -> None:
    shown = STAMP.findall(article("stops"))
    assert len(shown) == 5 and set(shown) <= run_times()


DECIDED = re.compile(
    r'<p class="decided" data-root="([^"]+)">Decision, (\w+): (.*?)</p>', re.S
)


def test_each_learned_rule_states_its_roots_decision_and_label() -> None:
    found = DECIDED.findall(section("promises"))
    assert len(found) == 2
    for root, label, decision in found:
        data = json.loads((REPO_ROOT / root).read_text())
        assert (label, text_of(decision)) == (data["status"], data["decision"])


def test_each_proof_says_what_it_does_not_prove() -> None:
    assert "Inferred" in text_of(article("learns"))
    assert "Knack’s author" in text_of(article("stops"))
    limit = text_of(re.findall(r'<p class="limit">(.*?)</p>', article("repairs"))[0])
    assert "Started by a person" in limit and "only with fake models" in limit


def self_repair_jsonl(name: str) -> list[dict[str, Any]]:
    lines = (SELF_REPAIR / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def candidate_time() -> str:
    # The passing candidate's file name carries the second it was written, in UTC.
    names = " ".join(os.listdir(SELF_REPAIR / "rule"))
    [s] = re.findall(r"candidate-(\d{8}T\d{6})Z", names)
    return f"{s[:4]}-{s[4:6]}-{s[6:11]}:{s[11:13]}:{s[13:]}Z"


def self_repair_times() -> set[str]:
    # Receipt and correction times, and the passing candidate's own stamp, in UTC.
    receipts = {r["time"][:19] + "Z" for r in self_repair_jsonl("receipts.jsonl")}
    confirms = {c["at"][:19] + "Z" for c in self_repair_jsonl("corrections.jsonl")}
    return receipts | confirms | {candidate_time()}


def test_every_time_in_the_repair_is_a_time_the_run_recorded() -> None:
    # The rolled-back confirm left no line, so its time is a gap, not a guess.
    shown = STAMP.findall(article("repairs"))
    assert len(shown) == 5 and set(shown) <= self_repair_times()
    assert '<span class="gap">not recorded</span>' in article("repairs")


def receipt(prefix: str) -> dict[str, Any]:
    [found] = [
        r for r in self_repair_jsonl("receipts.jsonl") if r["hash"].startswith(prefix)
    ]
    return found


@pytest.mark.parametrize(
    "prefix,decision,file",
    [
        ("b27a4e112756", "allow", "public/dags.py"),
        ("f679bf658d9f", "deny", "public/dag_sort_keys.py"),
        ("66a1c247a7e3", "deny", "public/dags.py"),
    ],
)
def test_each_repair_receipt_shown_is_the_runs(
    prefix: str, decision: str, file: str
) -> None:
    found = receipt(prefix)
    assert f"<code>{prefix}</code>" in article("repairs")
    assert found["decision"] == decision and found["file"].endswith(file)


CODE_ON_PAPER = re.compile(
    r'<figure class="paper[^"]*"[^>]*>\s*<pre><code>(.*?)</code></pre>', re.S
)


def test_the_false_alarm_on_paper_is_compliant_3_verbatim() -> None:
    case = json.loads(
        (SELF_REPAIR / "cases" / "must-pass-6633cbc47011.json").read_text()
    )
    [shown] = CODE_ON_PAPER.findall(article("repairs"))
    assert unescaped(shown) == case["after"].rstrip("\n")
    assert case["source"] == f"receipt {receipt('f679bf658d9f')['hash']}"


def rule_branches(version: str) -> list[Any]:
    return yaml.safe_load((SELF_REPAIR / "rule" / f"{version}.yml").read_text())[
        "rule"
    ]["any"]


def test_the_repair_counts_are_the_rule_diff() -> None:
    v1, v2 = rule_branches("v1"), rule_branches("v2")
    kept, dropped = sum(b in v2 for b in v1), sum(b not in v2 for b in v1)
    added = sum(b not in v1 for b in v2)
    assert f"dropped {dropped}, kept {kept}, added {added}" in text_of(
        article("repairs")
    )


def test_the_pin_shown_is_the_second_confirms() -> None:
    [confirm] = self_repair_jsonl("corrections.jsonl")
    after = json.loads((SELF_REPAIR / "rule" / "root_after.json").read_text())
    assert confirm["after"]["rule_sha"] == after["rule_sha"]
    assert f"<code>{after['rule_sha'][:12]}</code>" in article("repairs")
