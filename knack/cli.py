import argparse
import os
import re
import sys
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path

from pydantic import ValidationError

from knack.bench.doctor import live_doctor
from knack.bench.reclassify import reclassify
from knack.bench.repeats import hunt_registry, repeats_markdown
from knack.bench.report import bench_report, ReportError
from knack.bench.run import RunRecord
from knack.bench.sandbox import default_cache
from knack.contracts.models import Root, Verdict
from knack.dispute.argue import ask_spark
from knack.dispute.latest import dispute, NothingToDispute, ruling_text
from knack.guard.check import check_file, fail_open
from knack.guard.pr_comment import comment_on_block
from knack.index.build import build_index
from knack.pipeline.clients import (
    adversary_client,
    DEFAULT_EXTRACTOR,
    EXTRACTORS,
    live_clients,
    MissingCredentials,
    partner_client,
)
from knack.pipeline.github import GitHubApi
from knack.pipeline.init import OtherRepoRegistry, run_init
from knack.pipeline.ports import Spark
from knack.receipts.chain import ChainReport, receipts_path, verify_chain
from knack.roots.correct import (
    confirm_root,
    CorrectionError,
    reject_root,
    reviewer_name,
)
from knack.roots.corrections import corrections_path
from knack.roots.gate import Apply, Gate, gated, Outcome, regressed_line
from knack.roots.merge import import_lines, import_registry, RegistryImportError
from knack.roots.store import load_roots, RootStoreError
from knack.walk.registry import (
    home_registry_dir,
    load_registry,
    NoCloneRegistry,
    Registry,
    required_clone_registry,
)
from knack.walk.text import format_walk
from knack.walk.walk import walk
from knack.watch.install import WatchInstallError
from knack.watch.setup import install_watch

GUARD_LOG = Path(".knack/guard_errors.log")
REPO_PATTERN = re.compile(r"[\w.-]+/[\w.-]+")
DEFAULT_PRS = 50
OLD_REF_HELP = "release tag rules must not flag; defaults to the previous minor release"
NO_GATE_HELP = "skip re-extracting every PR with a Confirmed root after the correction"
CORROBORATE_HELP = "a second extractor (Spark <-> Spark Open) reads every PR too"
ADVERSARY_HELP = (
    "model that writes variants; defaults to the other extractor if its key is set"
)
# github, compiler, corroborating partner, variant writer.
Extractors = tuple[GitHubApi, Spark, Spark | None, Spark | None]


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    handlers = {"guard": _guard_command, "walk": _walk_command}
    handlers |= {"init": _init_command, "watch": _watch_command}
    handlers |= {"confirm": _confirm_command, "reject": _reject_command}
    handlers |= {"import": _import_command, "bench": _bench_command}
    handlers |= {"argue": _argue_command}
    return (handlers | {"receipts": _receipts_command})[args.command](args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knack")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, add in _command_adders().items():
        add(commands.add_parser(name))
    return parser


def _command_adders() -> dict[str, Callable[[argparse.ArgumentParser], None]]:
    adders = {"guard": _add_guard_arguments, "walk": _add_walk_arguments}
    adders |= {"init": _add_init_arguments, "watch": _add_watch_arguments}
    adders |= {"confirm": _add_correct_arguments, "import": _add_import_arguments}
    adders |= {"reject": _add_reject_arguments, "bench": _add_bench_arguments}
    adders |= {"argue": _add_argue_arguments}
    return adders | {"receipts": _add_receipts_arguments}


def _add_guard_arguments(guard: argparse.ArgumentParser) -> None:
    actions = guard.add_subparsers(dest="action", required=True)
    _add_check_arguments(actions.add_parser("check"))
    _add_comment_arguments(actions.add_parser("comment"))


def _add_check_arguments(check: argparse.ArgumentParser) -> None:
    check.add_argument("file", type=Path)
    check.add_argument("--rule", type=Path, required=True)
    check.add_argument("--root", type=Path, required=True)
    check.add_argument("--json", action="store_true")


def _add_comment_arguments(comment: argparse.ArgumentParser) -> None:
    comment.add_argument("file", type=Path)
    comment.add_argument("--rule", type=Path, required=True)
    comment.add_argument("--root", type=Path, required=True)


def _add_walk_arguments(walk_parser: argparse.ArgumentParser) -> None:
    walk_parser.add_argument("ticket")
    walk_parser.add_argument("--repo", type=Path, required=True)
    help = "defaults to the home registry of the --repo clone"
    walk_parser.add_argument("--registry", type=Path, help=help)
    walk_parser.add_argument("--roots", type=Path)
    walk_parser.add_argument("--json", action="store_true")


def _add_init_arguments(init: argparse.ArgumentParser) -> None:
    init.add_argument("--repo", type=_owner_name, required=True)
    init.add_argument("--prs", type=int, default=DEFAULT_PRS)
    init.add_argument("--out", type=Path)
    _add_model_arguments(init)
    init.add_argument("--old-ref", help=OLD_REF_HELP)


def _add_model_arguments(init: argparse.ArgumentParser) -> None:
    # Which model extracts and compiles, which corroborates, which writes variants.
    choices, default = list(EXTRACTORS), DEFAULT_EXTRACTOR
    init.add_argument("--extractor", choices=choices, default=default)
    init.add_argument("--corroborate", action="store_true", help=CORROBORATE_HELP)
    init.add_argument("--adversary", choices=choices, help=ADVERSARY_HELP)


def _owner_name(value: str) -> str:
    # Anything but exactly owner/name is a usage error, exit 2.
    if not REPO_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(f"expected owner/name, got {value!r}")
    return value


def _init_command(args: argparse.Namespace) -> int:
    clients = _clients_or_explain(args)
    if clients is None:
        return 2
    github, spark, second, adversary = clients
    out, ref = args.out or home_registry_dir(args.repo), args.old_ref
    init = partial(run_init, args.repo, args.prs, out, github, spark, old_ref=ref)
    return _run_or_explain(partial(init, second=second, adversary=adversary))


def _run_or_explain(init: Callable[[], Path]) -> int:
    # An --out registry of another repo is operator error: a message and exit 2.
    try:
        init()
    except OtherRepoRegistry as error:
        print(f"knack init: {error}", file=sys.stderr)
        return 2
    return 0


def _clients_or_explain(args: argparse.Namespace) -> Extractors | None:
    # Missing tokens are operator error: a message and exit 2, no traceback.
    try:
        github, spark = live_clients(args.extractor)
        second = partner_client(args.extractor) if args.corroborate else None
        return github, spark, second, adversary_client(args.extractor, args.adversary)
    except MissingCredentials as error:
        print(f"knack init: {error}", file=sys.stderr)
        return None


def _add_watch_arguments(watch: argparse.ArgumentParser) -> None:
    muse = Path.home() / ".config" / "muse" / "settings.json"
    watch.add_argument("--registry", type=Path)
    watch.add_argument("--muse-settings", type=Path, default=muse)
    watch.add_argument("--corroborate", action="store_true", help=CORROBORATE_HELP)


def _watch_command(args: argparse.Namespace) -> int:
    # Install problems (no registry, someone else's hook) exit 2 with a reason.
    try:
        lines = _install_watch(args)
    except WatchInstallError as error:
        print(f"knack watch: {error}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


def _install_watch(args: argparse.Namespace) -> list[str]:
    settings, corroborate = args.muse_settings, args.corroborate
    return install_watch(Path.cwd(), args.registry, settings, corroborate)


def _add_correct_arguments(correct: argparse.ArgumentParser) -> None:
    correct.add_argument("root_id")
    help = "defaults to the home registry of the clone you are in"
    correct.add_argument("--registry", type=Path, help=help)
    correct.add_argument("--by", help="who decided; defaults to git user.name")
    correct.add_argument("--no-gate", action="store_true", help=NO_GATE_HELP)


def _add_reject_arguments(reject: argparse.ArgumentParser) -> None:
    _add_correct_arguments(reject)
    reject.add_argument("--reason", required=True)


def _confirm_command(args: argparse.Namespace) -> int:
    by, log = args.by or reviewer_name(Path.cwd()), corrections_path()
    apply = partial(confirm_root, root_id=args.root_id, by=by, log=log)
    return _correct("confirm", args, apply)


def _reject_command(args: argparse.Namespace) -> int:
    by, log = args.by or reviewer_name(Path.cwd()), corrections_path()
    apply = partial(
        reject_root, root_id=args.root_id, reason=args.reason, by=by, log=log
    )
    return _correct("reject", args, apply)


def _correct(name: str, args: argparse.Namespace, apply: Apply) -> int:
    # A bad id, registry, clone, root state or key is operator error: exit 2.
    try:
        outcome = _gated_correction(args, apply)
    except (CorrectionError, NoCloneRegistry, RootStoreError) as error:
        print(f"knack {name}: {error}", file=sys.stderr)
        return 2
    return _correction_report(outcome)


def _gated_correction(args: argparse.Namespace, apply: Apply) -> Outcome:
    # Clients come first, so a missing key leaves the root untouched.
    gate = None if args.no_gate else _gate()
    registry = args.registry or required_clone_registry(Path.cwd())
    return gated(registry, apply, gate, corrections_path())


def _gate() -> Gate:
    try:
        return Gate(*live_clients(), log=print)
    except MissingCredentials as error:
        raise CorrectionError(
            f"{error}; the gate needs it, or pass --no-gate"
        ) from error


def _correction_report(outcome: Outcome) -> int:
    # A rolled-back correction exits 1 and names every Confirmed root it lost.
    done, undone = outcome.correction, " rolled back" if outcome.rolled_back else ""
    print(f"{done.root_id}: {done.before.status} -> {done.after.status}{undone}")
    for root in outcome.lost:
        print(regressed_line(root))
    return 1 if outcome.rolled_back else 0


def _add_bench_arguments(bench: argparse.ArgumentParser) -> None:
    actions = bench.add_subparsers(dest="action", required=True)
    _add_report_arguments(actions.add_parser("report"))
    reclassify = actions.add_parser("reclassify")
    reclassify.add_argument("--runs", type=Path, required=True)
    reclassify.add_argument("--out", type=Path, required=True)
    _add_doctor_arguments(actions.add_parser("doctor"))
    _add_repeats_arguments(actions.add_parser("repeats"))


def _add_repeats_arguments(repeats: argparse.ArgumentParser) -> None:
    # One --target per repo: its registry file and a clone with full history.
    repeats.add_argument(
        "--target",
        action="append",
        required=True,
        nargs=2,
        metavar=("REGISTRY", "CLONE"),
        type=Path,
    )
    repeats.add_argument("--out", type=Path, default=Path("bench/REPEATS.md"))


def _add_doctor_arguments(doctor: argparse.ArgumentParser) -> None:
    doctor.add_argument("--tickets", type=Path, default=Path("bench/tickets.jsonl"))
    doctor.add_argument("--cache", type=Path, default=default_cache())


def _add_report_arguments(report: argparse.ArgumentParser) -> None:
    report.add_argument("--runs", type=Path, default=Path("bench/runs.jsonl"))
    report.add_argument("--exclude-ticket", default=None)


def _bench_command(args: argparse.Namespace) -> int:
    if args.action == "doctor":
        return 0 if live_doctor(args.tickets, args.cache) else 1
    if args.action == "reclassify":
        return _bench_reclassify(args.runs, args.out)
    if args.action == "repeats":
        return _bench_repeats(args.target, args.out)
    return _bench_report(args.runs, args.exclude_ticket)


def _bench_reclassify(runs: Path, out: Path) -> int:
    # Never overwrites: an existing --out or a bad runs file is operator error, exit 2.
    try:
        records = _new_reclassified(runs, out)
    except (ReportError, FileExistsError) as error:
        print(f"knack bench reclassify: {error}", file=sys.stderr)
        return 2
    print(f"reclassified {len(records)} run(s) -> {out}")
    return 0


def _bench_repeats(targets: list[list[Path]], out: Path) -> int:
    hunts = [
        hunt for registry, clone in targets for hunt in hunt_registry(registry, clone)
    ]
    out.write_text(repeats_markdown(hunts) + "\n", encoding="utf-8")
    print(
        f"{len(hunts)} decision(s), {sum(len(h.repeats) for h in hunts)} repeat match(es) -> {out}"
    )
    return 0


def _new_reclassified(runs: Path, out: Path) -> list[RunRecord]:
    if out.exists():
        raise FileExistsError(f"{out} exists")
    return reclassify(runs, out)


def _bench_report(runs: Path, exclude: str | None) -> int:
    # A bad runs file or an unknown excluded ticket is operator error: exit 2.
    try:
        text = bench_report(runs, exclude)
    except ReportError as error:
        print(f"knack bench report: {error}", file=sys.stderr)
        return 2
    print(text)
    return 0


def _add_receipts_arguments(receipts: argparse.ArgumentParser) -> None:
    actions = receipts.add_subparsers(dest="action", required=True)
    verify = actions.add_parser("verify")
    verify.add_argument("--path", type=Path, help="defaults to ~/.knack/verdicts.jsonl")


def _receipts_command(args: argparse.Namespace) -> int:
    # Intact 0, broken 1; an unreadable file is operator error, exit 2.
    path = args.path or receipts_path()
    report = _verified_or_explain(path)
    if report is None:
        return 2
    print(_chain_line(path, report.receipts, report.broken_line, report.problem))
    return 0 if report.broken_line is None else 1


def _verified_or_explain(path: Path) -> ChainReport | None:
    try:
        return verify_chain(path)
    except (OSError, UnicodeDecodeError) as error:
        print(f"knack receipts: {error}", file=sys.stderr)
        return None


def _chain_line(path: Path, count: int, broken: int | None, problem: str | None) -> str:
    noun = "receipt" if count == 1 else "receipts"
    if broken is None:
        return f"{path}: {count} {noun}, chain intact"
    return f"{path}: chain broken at line {broken}: {problem} ({count} {noun} before it verify)"


def _add_argue_arguments(argue: argparse.ArgumentParser) -> None:
    argue.add_argument("objection", help="why the latest deny in this clone is wrong")


def _argue_command(args: argparse.Namespace) -> int:
    # Hold and escalate both exit 0; nothing to dispute is operator error, exit 2.
    try:
        ruling = dispute(args.objection, Path.cwd(), receipts_path(), ask_spark)
    except (NothingToDispute, OSError, ValidationError) as error:
        print(f"knack argue: {error}", file=sys.stderr)
        return 2
    print(ruling_text(ruling))
    return 0


def _add_import_arguments(import_parser: argparse.ArgumentParser) -> None:
    help = "merged into the home registry of the repo it guards"
    import_parser.add_argument("--registry", type=Path, required=True, help=help)


def _import_command(args: argparse.Namespace) -> int:
    # A missing, unreadable or self import is operator error: a message and exit 2.
    try:
        done = import_registry(args.registry)
    except (RegistryImportError, RootStoreError, ValidationError) as error:
        print(f"knack import: {error}", file=sys.stderr)
        return 2
    print("\n".join(import_lines(done)))
    return 0


def _walk_command(args: argparse.Namespace) -> int:
    # --roots overrides the roots_dir the registry names.
    registry = _walk_registry(args.registry, args.repo)
    if registry is None:
        return 2
    roots = load_roots(args.roots or registry.roots_dir)
    response = walk(args.ticket, build_index(args.repo), registry.rules, roots)
    print(response.model_dump_json(indent=2) if args.json else format_walk(response))
    return 0


def _walk_registry(path: Path | None, repo: Path) -> Registry | None:
    # No clone, or no knack init for it, is operator error: a message and exit 2.
    try:
        return load_registry(path or required_clone_registry(repo))
    except (NoCloneRegistry, FileNotFoundError) as error:
        print(f"knack walk: {error}", file=sys.stderr)
        return None


def _guard_command(args: argparse.Namespace) -> int:
    if args.action == "comment":
        return _guard_comment(args)
    verdict = _guard_check(args.file, args.rule, args.root)
    print(verdict.model_dump_json() if args.json else verdict.reason)
    return 0 if verdict.allowed else 1


def _guard_comment(args: argparse.Namespace) -> int:
    # Best effort: any failure is reported and exits 0, so it never fails CI.
    paths = (args.file, args.rule, args.root)
    try:
        posted = comment_on_block(*paths, os.environ, GUARD_LOG)
        print(f"knack guard comment: {posted} posted on {args.file}")
    except Exception as error:
        print(f"knack guard comment: {type(error).__name__}: {error}", file=sys.stderr)
    return 0


def _guard_check(file_path: Path, rule_path: Path, root_path: Path) -> Verdict:
    started = time.perf_counter()
    try:
        root = Root.model_validate_json(root_path.read_text(encoding="utf-8"))
    except Exception as error:
        # A bad root file is our failure, so it fails open like any guard error.
        return fail_open(error, GUARD_LOG, started)
    return check_file(file_path, rule_path, rule_path.stem, root, GUARD_LOG)
