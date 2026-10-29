from types import ModuleType

import pytest
from conftest import SpikeLoader

CLONING_SPIKES = ["batch_compile", "batch_precision"]


class FakeResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = body

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, object]:
        return self.body


@pytest.fixture
def fake_api(load_spike: SpikeLoader, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    # every spike shares one requests module, so patching it fakes the API for all of them
    urls = list[str]()

    def get(url: str, **_: object) -> FakeResponse:
        urls.append(url)
        return FakeResponse(
            {"full_name": "fastapi/fastapi", "default_branch": "master"}
        )

    monkeypatch.setattr(load_spike("batch_repo").requests, "get", get)
    return urls


def test_default_branch_comes_from_the_repo_api(
    load_spike: SpikeLoader, fake_api: list[str]
) -> None:
    spike = load_spike("batch_repo")
    assert spike.default_branch(spike.Batch("fastapi/fastapi")) == "master"
    assert fake_api == ["https://api.github.com/repos/fastapi/fastapi"]


@pytest.mark.parametrize("script", CLONING_SPIKES)
def test_ref_defaults_to_unset(load_spike: SpikeLoader, script: str) -> None:
    assert load_spike(script).parse_args([]).ref is None


@pytest.mark.parametrize("script", CLONING_SPIKES)
def test_missing_ref_resolves_to_default_branch(
    load_spike: SpikeLoader, fake_api: list[str], script: str
) -> None:
    spike: ModuleType = load_spike(script)
    assert spike.resolve_ref(spike.Batch("fastapi/fastapi"), None) == "master"
    assert len(fake_api) == 1


@pytest.mark.parametrize("script", CLONING_SPIKES)
def test_explicit_ref_overrides_without_asking_the_api(
    load_spike: SpikeLoader, fake_api: list[str], script: str
) -> None:
    spike = load_spike(script)
    args = spike.parse_args(["--repo", "fastapi/fastapi", "--ref", "0.115.0"])
    assert spike.resolve_ref(spike.Batch(args.repo), args.ref) == "0.115.0"
    assert fake_api == []
