from pathlib import Path

import pytest
from conftest import clean_tree, FakeGitHub, FakeSpark, STRUCTURAL
from knack import cli
from knack.contracts.models import Root
from knack.pipeline import spark_open
from knack.pipeline.clients import live_clients, MissingCredentials, partner_client
from knack.pipeline.spark import SparkApi
from knack.pipeline.spark_open import SparkOpenApi
from knack.walk.registry import load_registry, Registry


class FakeSparkOpen(FakeSpark):
    model = spark_open.MODEL


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    # Records the extractor asked for; spark-open answers under its own model id.
    asked: list[str] = []

    def clients(extractor: str) -> tuple[FakeGitHub, FakeSpark]:
        asked.append(extractor)
        spark = FakeSparkOpen if extractor == "spark-open" else FakeSpark
        return FakeGitHub(clean_tree(tmp_path)), spark([STRUCTURAL])

    monkeypatch.setattr(cli, "live_clients", clients)
    return asked


@pytest.mark.usefixtures("fakes")
def test_init_prints_the_staged_log_and_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "reg"
    assert cli.main(["init", "--repo", "acme/widgets", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "[1/5] select" in printed and f"{out / 'registry.json'}" in printed
    assert load_registry(out / "registry.json").repo == "acme/widgets"


@pytest.mark.usefixtures("fakes")
def test_init_defaults_to_the_home_registry_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert cli.main(["init", "--repo", "Acme/Widgets", "--prs", "1"]) == 0
    expected = tmp_path / "home" / ".knack" / "registries" / "acme-widgets"
    assert (expected / "registry.json").exists()


@pytest.mark.usefixtures("fakes")
def test_prs_flag_caps_the_selection(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    cli.main(
        ["init", "--repo", "acme/widgets", "--prs", "1", "--out", str(tmp_path / "r")]
    )
    assert "1 PRs read, 1 kept" in capsys.readouterr().out


@pytest.mark.parametrize("repo", ["acme", "acme/widgets/extra", "a b/c"])
def test_repo_must_be_owner_slash_name(repo: str) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["init", "--repo", repo])
    assert raised.value.code == 2


def test_live_clients_need_both_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("MODEL_API_KEY", "k")
    with pytest.raises(MissingCredentials, match="GITHUB_TOKEN"):
        live_clients()


def test_missing_credentials_exit_2_with_a_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    assert cli.main(["init", "--repo", "acme/widgets"]) == 2
    assert "MODEL_API_KEY" in capsys.readouterr().err


def test_init_extracts_with_spark_by_default(fakes: list[str], tmp_path: Path) -> None:
    assert (
        cli.main(["init", "--repo", "acme/widgets", "--out", str(tmp_path / "r")]) == 0
    )
    assert fakes == ["spark"]


def test_spark_open_roots_record_the_spark_open_model(
    fakes: list[str], tmp_path: Path
) -> None:
    args = ["init", "--repo", "acme/widgets", "--out", str(tmp_path / "r")]
    assert cli.main([*args, "--extractor", "spark-open"]) == 0
    roots = (tmp_path / "r" / "roots").glob("*.json")
    models = {
        tuple(Root.model_validate_json(path.read_text()).models) for path in roots
    }
    assert fakes == ["spark-open"] and models == {(spark_open.MODEL,)}


def test_an_unknown_extractor_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["init", "--repo", "acme/widgets", "--extractor", "gpt"])
    assert raised.value.code == 2


def test_live_clients_default_to_spark(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("MODEL_API_KEY", "k")
    assert isinstance(live_clients()[1], SparkApi)


def test_spark_open_clients_use_the_baseten_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("BASETEN_API_KEY", "b")
    spark = live_clients("spark-open")[1]
    assert (
        isinstance(spark, SparkOpenApi) and spark.headers["Authorization"] == "Bearer b"
    )


def test_spark_open_without_the_baseten_key_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    args = ["init", "--repo", "acme/widgets", "--extractor", "spark-open"]
    assert cli.main(args) == 2
    assert "BASETEN_API_KEY" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("extractor", "partner"), [("spark", SparkOpenApi), ("spark-open", SparkApi)]
)
def test_the_partner_of_each_extractor_is_the_other_one(
    monkeypatch: pytest.MonkeyPatch, extractor: str, partner: type
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "k")
    monkeypatch.setenv("BASETEN_API_KEY", "b")
    assert isinstance(partner_client(extractor), partner)


def test_init_corroborate_reads_every_pr_with_the_partner_too(
    fakes: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    partners: list[str] = []

    def partner(extractor: str) -> FakeSparkOpen:
        partners.append(extractor)
        return FakeSparkOpen([STRUCTURAL])

    monkeypatch.setattr(cli, "partner_client", partner)
    args = ["init", "--repo", "acme/widgets", "--out", str(tmp_path / "r")]
    assert cli.main([*args, "--corroborate"]) == 0
    roots = [
        Root.model_validate_json(p.read_text())
        for p in (tmp_path / "r" / "roots").glob("*.json")
    ]
    assert (fakes, partners) == (["spark"], ["spark"])
    assert [(r.status, r.models) for r in roots] == [
        ("Corroborated", ["fake-spark", spark_open.MODEL])
    ]


def test_corroborate_without_the_partner_key_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("MODEL_API_KEY", "k")
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    assert cli.main(["init", "--repo", "acme/widgets", "--corroborate"]) == 2
    assert "BASETEN_API_KEY" in capsys.readouterr().err


def registry_of(out: Path, repo: str) -> Path:
    # An existing registry at --out, already guarding repo.
    out.mkdir(parents=True)
    registry = Registry(repo=repo, roots_dir=Path("roots"), rules=[])
    (out / "registry.json").write_text(registry.model_dump_json())
    return out / "registry.json"


@pytest.mark.usefixtures("fakes")
def test_init_refuses_an_out_registry_of_another_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = registry_of(tmp_path / "reg", "acme/gadgets")
    before = path.read_text()
    argv = ["init", "--repo", "acme/widgets", "--out", str(tmp_path / "reg")]
    assert cli.main(argv) == 2
    printed = capsys.readouterr()
    assert "acme/gadgets" in printed.err and "[1/5] select" not in printed.out
    assert path.read_text() == before


@pytest.mark.usefixtures("fakes")
def test_init_merges_into_its_own_repo_whatever_the_case(tmp_path: Path) -> None:
    registry_of(tmp_path / "reg", "Acme/Widgets")
    argv = ["init", "--repo", "acme/widgets", "--out", str(tmp_path / "reg")]
    assert cli.main(argv) == 0
