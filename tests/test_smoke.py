import importlib


def test_import_knack() -> None:
    module = importlib.import_module("knack")
    assert module.__name__ == "knack"
