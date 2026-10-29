import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast, TextIO

from knack.guard.check import log_error_quietly
from knack.hooks.scope import event_cwd, home_error_log
from knack.pipeline.clients import (
    corroborating_clients,
    live_clients,
    MissingCredentials,
)
from knack.watch.run import Clients, pending_root, run_pending

HOOK_MODULE = "knack.watch.hook"
WATCH_LOG = "watch.log"
# Muse Code tools that run commands; only these can move HEAD with a merge.
SHELL_TOOLS = frozenset({"shell", "bash", "bash_input", "code_exec"})


def main(argv: list[str] | None = None, stdin: TextIO = sys.stdin) -> int:
    # Always exit 0: a knack failure must never fail a merge or an agent's turn.
    args = _parser().parse_args(argv)
    try:
        _dispatch(args, stdin)
    except Exception as error:
        _report(error, loud=args.mode == "post-merge")
    return 0


def post_merge_argv(registry_path: Path, corroborate: bool = False) -> list[str]:
    python = [sys.executable, "-m", HOOK_MODULE]
    flag = ["--corroborate"] if corroborate else []
    return python + ["post-merge", "--registry", str(registry_path), *flag]


def spawn_background(argv: list[str], cwd: Path, log_path: Path) -> None:
    # Detached, so the agent's turn goes on; the progress log lands in log_path.
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=log, start_new_session=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"python -m {HOOK_MODULE}")
    parser.add_argument("mode", choices=["post-merge", "tool-batch"])
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--corroborate", action="store_true")
    return parser


def _dispatch(args: argparse.Namespace, stdin: TextIO) -> None:
    # post-merge runs here, in the terminal; tool-batch hands the run to the background.
    if args.mode == "post-merge":
        run_pending(Path.cwd(), args.registry, _clients(args.corroborate), _say)
        return
    _tool_batch(json.loads(stdin.read()), args.registry, args.corroborate)


def _clients(corroborate: bool) -> Clients:
    return corroborating_clients if corroborate else live_clients


def _tool_batch(
    event: dict[str, Any], registry_path: Path, corroborate: bool = False
) -> None:
    # Most batches are file edits or Muse's own bookkeeping: those return before git.
    if not ran_shell(event):
        return
    root = pending_root(event_cwd(event), registry_path)
    if root is not None:
        argv = post_merge_argv(registry_path, corroborate)
        spawn_background(argv, root, registry_path.parent / WATCH_LOG)


def ran_shell(event: dict[str, Any]) -> bool:
    calls = event.get("tool_calls")
    if not isinstance(calls, list):
        return False
    return any(_tool_name(call) in SHELL_TOOLS for call in cast(list[object], calls))


def _tool_name(call: object) -> object:
    # Anything but a {"tool_name": ...} object names no tool.
    if not isinstance(call, dict):
        return None
    return cast(dict[str, object], call).get("tool_name")


def _say(line: str) -> None:
    # Flushed per line, so a background run's log file fills as it goes.
    print(line, flush=True)


def _report(error: Exception, loud: bool) -> None:
    # Missing tokens are operator error; anything else is ours and is logged.
    if isinstance(error, MissingCredentials):
        print(f"knack watch: {error}", file=sys.stderr)
        return
    log_error_quietly(home_error_log(), error)
    if loud:
        print(f"knack watch error: {type(error).__name__}: {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
