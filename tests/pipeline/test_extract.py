from pathlib import Path

import pytest
from conftest import (
    clean_tree,
    FakeGitHub,
    FakeSpark,
    QUOTE,
    REPO,
    REVIEW,
    STRUCTURAL,
    summary,
)
from knack.pipeline.extract import (
    extract_all,
    mark_verbatim,
    parse_decisions,
    PROMPT,
    thread_text,
)
from knack.pipeline.models import Alternative, Decision, Post, PullRequest
from knack.pipeline.select import select_prs


def pull(number: int, title: str) -> PullRequest:
    fields = summary(number, title).model_dump()
    return PullRequest(**fields, base_sha="b", head_sha="h", python_files=["a.py"])


def decision(quote: str) -> Decision:
    alternative = Alternative(alternative="a", why_rejected="w", quote=quote)
    return Decision(decision="d", rejected_alternatives=[alternative])


def test_thread_text_holds_title_author_body_and_every_post() -> None:
    posts = [Post(heading="Review by bo (APPROVED)", body="ship it")]
    text = thread_text(pull(1, "T"), posts)
    assert text.startswith("Title: T\nAuthor: maria\n")
    assert "Review by bo (APPROVED): ship it" in text


def test_parse_decisions_accepts_fenced_json() -> None:
    answer = '```json\n{"decisions": [{"decision": "d", "why": "w"}]}\n```'
    assert parse_decisions(answer) == [Decision(decision="d", why="w")]


@pytest.mark.parametrize("answer", ["not json", '{"other": []}', "[]"])
def test_parse_decisions_rejects_answers_without_decisions(answer: str) -> None:
    with pytest.raises(ValueError):
        parse_decisions(answer)


def test_mark_verbatim_flags_only_quotes_found_in_the_thread() -> None:
    marked = mark_verbatim([decision("in here"), decision("elsewhere")], "in here!")
    flags = [a.verbatim for d in marked for a in d.rejected_alternatives]
    assert flags == [True, False]


def test_empty_quote_is_never_verbatim() -> None:
    marked = mark_verbatim([decision("")], "anything")
    assert marked[0].rejected_alternatives[0].verbatim is False


def run_extract(tmp_path: Path) -> tuple[FakeSpark, list[int], list[int]]:
    github, spark = FakeGitHub(clean_tree(tmp_path)), FakeSpark([STRUCTURAL])
    stage = extract_all(github, spark, REPO, select_prs(github, REPO, 50).prs)
    return spark, [e.number for e in stage.extractions], stage.failed


def test_extract_all_reads_each_thread_once_and_skips_babble(tmp_path: Path) -> None:
    spark, done, failed = run_extract(tmp_path)
    assert done == [9, 4, 3] and failed == [2]
    assert len(spark.prompts) == 4 and REVIEW in spark.prompts[0]


def test_extraction_keeps_pr_title_and_marks_the_real_quote(tmp_path: Path) -> None:
    github, spark = FakeGitHub(clean_tree(tmp_path)), FakeSpark([STRUCTURAL])
    prs = select_prs(github, REPO, 1).prs
    extraction = extract_all(github, spark, REPO, prs).extractions[0]
    alternative = extraction.decisions[0].rejected_alternatives[0]
    assert extraction.title == "Read blobs one at a time"
    assert alternative.quote == QUOTE and alternative.verbatim


def test_extract_all_reports_each_pr_in_order_as_it_finishes(tmp_path: Path) -> None:
    github, spark = FakeGitHub(clean_tree(tmp_path)), FakeSpark([STRUCTURAL])
    seen = list[tuple[int, bool]]()
    prs = select_prs(github, REPO, 50).prs
    extract_all(github, spark, REPO, prs, lambda n, e: seen.append((n, e is None)))
    assert seen == [(9, False), (4, False), (3, False), (2, True)]


def test_few_shot_block_sits_between_the_rules_and_the_pr_text(
    tmp_path: Path,
) -> None:
    github, spark = FakeGitHub(clean_tree(tmp_path)), FakeSpark([STRUCTURAL])
    prs = select_prs(github, REPO, 1).prs
    extract_all(github, spark, REPO, prs, few_shot="PAST CORRECTIONS\n\n")
    prompt = spark.prompts[0]
    assert prompt.index("Do not guess.") < prompt.index("PAST CORRECTIONS")
    assert prompt.index("PAST CORRECTIONS") < prompt.index("PR TEXT:\nTitle: ")


def test_without_corrections_the_prompt_is_unchanged(tmp_path: Path) -> None:
    github, spark = FakeGitHub(clean_tree(tmp_path)), FakeSpark([STRUCTURAL])
    extract_all(github, spark, REPO, select_prs(github, REPO, 1).prs)
    assert spark.prompts[0].startswith(PROMPT + "Title: ")
