import argparse
import time
from pathlib import Path

from knack.contracts.models import Root, Verdict
from knack.guard.check import check_file, fail_open

GUARD_LOG = Path(".knack/guard_errors.log")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    verdict = _guard_check(args.file, args.rule, args.root)
    print(verdict.model_dump_json() if args.json else verdict.reason)
    return 0 if verdict.allowed else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knack")
    guard = parser.add_subparsers(dest="command", required=True).add_parser("guard")
    check = guard.add_subparsers(dest="action", required=True).add_parser("check")
    _add_check_arguments(check)
    return parser


def _add_check_arguments(check: argparse.ArgumentParser) -> None:
    check.add_argument("file", type=Path)
    check.add_argument("--rule", type=Path, required=True)
    check.add_argument("--root", type=Path, required=True)
    check.add_argument("--json", action="store_true")


def _guard_check(file_path: Path, rule_path: Path, root_path: Path) -> Verdict:
    started = time.perf_counter()
    try:
        root = Root.model_validate_json(root_path.read_text(encoding="utf-8"))
    except Exception as error:
        # A bad root file is our failure, so it fails open like any guard error.
        return fail_open(error, GUARD_LOG, started)
    return check_file(file_path, rule_path, rule_path.stem, root, GUARD_LOG)
