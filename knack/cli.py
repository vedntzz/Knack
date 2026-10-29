import argparse
import re
import sys
import time
from pathlib import Path

from knack.contracts.models import Root, Verdict
from knack.guard.check import check_file, fail_open
from knack.index.build import build_index
from knack.pipeline.clients import live_clients, MissingCredentials
from knack.pipeline.github import GitHubApi
from knack.pipeline.init import run_init
from knack.pipeline.spark import SparkApi
from knack.roots.store import load_roots
from knack.walk.registry import home_registry_dir, load_registry
from knack.walk.text import format_walk
from knack.walk.walk import walk
from knack.watch.install import WatchInstallError
from knack.watch.setup import install_watch

GUARD_LOG = Path(".knack/guard_errors.log")
REPO_PATTERN = re.compile(r"[\w.-]+/[\w.-]+")
DEFAULT_PRS = 50


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    handlers = {"guard": _guard_command, "walk": _walk_command}
    handlers |= {"init": _init_command, "watch": _watch_command}
    return handlers[args.command](args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knack")
    commands = parser.add_subparsers(dest="command", required=True)
    adders = {"guard": _add_guard_arguments, "walk": _add_walk_arguments}
    adders |= {"init": _add_init_arguments, "watch": _add_watch_arguments}
    for name, add in adders.items():
        add(commands.add_parser(name))
    return parser


def _add_guard_arguments(guard: argparse.ArgumentParser) -> None:
    actions = guard.add_subparsers(dest="action", required=True)
    _add_check_arguments(actions.add_parser("check"))


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
    clients = _clients_or_explain()
    if clients is None:
        return 2
    run_init(args.repo, args.prs, args.out or home_registry_dir(args.repo), *clients)
    return 0


def _clients_or_explain() -> tuple[GitHubApi, SparkApi] | None:
    # Missing tokens are operator error: a message and exit 2, no traceback.
    try:
        return live_clients()
    except MissingCredentials as error:
        print(f"knack init: {error}", file=sys.stderr)
        return None


def _add_watch_arguments(watch: argparse.ArgumentParser) -> None:
    muse = Path.home() / ".config" / "muse" / "settings.json"
    watch.add_argument("--registry", type=Path)
    watch.add_argument("--muse-settings", type=Path, default=muse)


def _watch_command(args: argparse.Namespace) -> int:
    # Install problems (no registry, someone else's hook) exit 2 with a reason.
    try:
        lines = install_watch(Path.cwd(), args.registry, args.muse_settings)
    except WatchInstallError as error:
        print(f"knack watch: {error}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


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
