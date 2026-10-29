import argparse
import re
import sys
import time
from pathlib import Path

from knack.contracts.models import Root, Verdict
from knack.guard.check import check_file, fail_open
from knack.index.build import build_index
from knack.pipeline.clients import live_clients, MissingCredentials
from knack.pipeline.init import run_init
from knack.roots.store import load_roots
from knack.walk.registry import load_registry
from knack.walk.text import format_walk
from knack.walk.walk import walk

GUARD_LOG = Path(".knack/guard_errors.log")
REPO_PATTERN = re.compile(r"[\w.-]+/[\w.-]+")
DEFAULT_PRS = 50


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    handlers = {"guard": _guard_command, "walk": _walk_command, "init": _init_command}
    return handlers[args.command](args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knack")
    commands = parser.add_subparsers(dest="command", required=True)
    guard = commands.add_parser("guard").add_subparsers(dest="action", required=True)
    _add_check_arguments(guard.add_parser("check"))
    _add_walk_arguments(commands.add_parser("walk"))
    _add_init_arguments(commands.add_parser("init"))
    return parser


def _add_check_arguments(check: argparse.ArgumentParser) -> None:
    check.add_argument("file", type=Path)
    check.add_argument("--rule", type=Path, required=True)
    check.add_argument("--root", type=Path, required=True)
    check.add_argument("--json", action="store_true")


def _add_walk_arguments(walk_parser: argparse.ArgumentParser) -> None:
    walk_parser.add_argument("ticket")
    walk_parser.add_argument("--repo", type=Path, required=True)
    walk_parser.add_argument("--registry", type=Path, required=True)
    walk_parser.add_argument("--roots", type=Path)
    walk_parser.add_argument("--json", action="store_true")


def _add_init_arguments(init: argparse.ArgumentParser) -> None:
    init.add_argument("--repo", type=_owner_name, required=True)
    init.add_argument("--prs", type=int, default=DEFAULT_PRS)
    init.add_argument("--out", type=Path)


def _owner_name(value: str) -> str:
    # Anything but exactly owner/name is a usage error, exit 2.
    if not REPO_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(f"expected owner/name, got {value!r}")
    return value


def _init_command(args: argparse.Namespace) -> int:
    # Missing tokens are operator error: a message and exit 2, no traceback.
    try:
        github, spark = live_clients()
    except MissingCredentials as error:
        print(f"knack init: {error}", file=sys.stderr)
        return 2
    run_init(args.repo, args.prs, args.out or _home_registry(args.repo), github, spark)
    return 0


def _home_registry(repo: str) -> Path:
    return Path.home() / ".knack" / "registries" / repo.replace("/", "-").lower()


def _walk_command(args: argparse.Namespace) -> int:
    # --roots overrides the roots_dir the registry names.
    registry = load_registry(args.registry)
    roots = load_roots(args.roots or registry.roots_dir)
    response = walk(args.ticket, build_index(args.repo), registry.rules, roots)
    print(response.model_dump_json(indent=2) if args.json else format_walk(response))
    return 0


def _guard_command(args: argparse.Namespace) -> int:
    verdict = _guard_check(args.file, args.rule, args.root)
    print(verdict.model_dump_json() if args.json else verdict.reason)
    return 0 if verdict.allowed else 1


def _guard_check(file_path: Path, rule_path: Path, root_path: Path) -> Verdict:
    started = time.perf_counter()
    try:
        root = Root.model_validate_json(root_path.read_text(encoding="utf-8"))
    except Exception as error:
        # A bad root file is our failure, so it fails open like any guard error.
        return fail_open(error, GUARD_LOG, started)
    return check_file(file_path, rule_path, rule_path.stem, root, GUARD_LOG)
