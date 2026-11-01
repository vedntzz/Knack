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
from knack.dispute.latest import disputed, Disputed, NothingToDispute, ruling_text
from knack.dispute.rulings import append_ruling, RulingRecord, rulings_path
from knack.dispute.second import Second, second_opinion, spark_escalated
from knack.guard.check import check_file, fail_open
from knack.guard.pr_comment import comment_on_block
from knack.index.build import build_index
from knack.miss.cases import CaseKind
from knack.miss.loop import (
    default_heldout,
    default_work,
    Loop,
    LoopOutcome,
    outcome_lines,
    record_and_recompile,
    UnknownRule,
)
from knack.miss.sources import MissSourceError, Places, resolve_source
from knack.pipeline.clients import (
    adversary_client,
    DEFAULT_EXTRACTOR,
    EXTRACTORS,
    github_client,
    live_clients,
    MissingCredentials,
    partner_client,
)
from knack.pipeline.github import GitHubApi
from knack.pipeline.init import OtherRepoRegistry, run_init
from knack.pipeline.ports import GitHub, Spark
from knack.pipeline.reprove import default_variants, Reprove, reprove_registry
from knack.receipts.chain import ChainReport, receipts_path, verify_chain
from knack.receipts.edits import edits_dir
from knack.roots.backfill import backfill_merged_at, missing_merged_at
from knack.roots.correct import (
    confirm_root,
    CorrectionError,
    reject_root,
    reviewer_name,
)
from knack.roots.corrections import Correction, corrections_path
from knack.roots.gate import Apply, Gate, gated, Outcome, regressed_line
from knack.roots.merge import import_lines, import_registry, RegistryImportError
from knack.roots.resolve import resolve_deny, Resolved, ResolveError
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
NO_SECOND_HELP = (
    "no second model: by default Spark Open judges merges when BASETEN_API_KEY is set"
)
ADVERSARY_HELP = (
    "model that writes variants; defaults to the other extractor if its key is set"
)
MISS_HELP = "a receipt hash of the allow, a bench run id, or an edit JSON file"
FALSE_BLOCK_HELP = "the receipt hash of the deny (or an edit JSON file)"
HELDOUT_HELP = "folder of <pr>/same and <pr>/cross held-out sets; defaults to ../heldout/<registry name>"
LOOP_REGISTRY_HELP = "defaults to the home registry of the clone you are in"
WORK_HELP = "defaults to ~/.knack/cache/miss/<registry>"
RECEIPTS_HELP = "defaults to ~/.knack/verdicts.jsonl"
RUNS_HELP = "bench run files; defaults to bench/runs*.jsonl"
KEPT = "the old rule is kept"
RESOLVE_REGISTRY_HELP = "defaults to the home registry of the receipt's repo"
NO_WRITER = (
    "the fresh cross-model set needs a second model: set its key or pass --adversary"
)
# A bad source, rule, registry, file or key: operator error, exit 2.
LOOP_ERRORS = (
    MissSourceError,
    UnknownRule,
    NoCloneRegistry,
    MissingCredentials,
    FileNotFoundError,
)
# No token, no registry, a bad root file or GitHub unreachable: a message, exit 2.
BACKFILL_ERRORS = (
    NoCloneRegistry,
    MissingCredentials,
    RootStoreError,
    ValidationError,
    OSError,
)
# No token, no registry, or a registry that does not parse: a message, exit 2.
REPROVE_ERRORS = (
    NoCloneRegistry,
    MissingCredentials,
    ValidationError,
    FileNotFoundError,
)
VARIANTS_HELP = (
    "folder of <pr>/ training variant sets; defaults to ../variants/<registry name>"
)
# github, compiler, corroborating partner, variant writer.
Extractors = tuple[GitHubApi, Spark, Spark | None, Spark | None]


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return _handlers()[args.command](args)


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
    adders |= {"argue": _add_argue_arguments, "console": _add_console_arguments}
    adders |= {"miss": _add_miss_arguments, "false-block": _add_false_block_arguments}
    adders |= {"backfill-merged": _add_backfill_arguments}
    return adders | {
        "receipts": _add_receipts_arguments,
        "resolve": _add_resolve_arguments,
        "reprove": _add_reprove_arguments,
    }


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
    second = watch.add_mutually_exclusive_group()
    second.add_argument("--corroborate", action="store_true", help=CORROBORATE_HELP)
    second.add_argument("--no-corroborate", action="store_true", help=NO_SECOND_HELP)


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
    second = (args.corroborate, not args.no_corroborate)
    return install_watch(Path.cwd(), args.registry, args.muse_settings, *second)


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
    print(
        f"{done.root_id}: {done.before.status} -> {done.after.status}{_pin_note(done)}{undone}"
    )
    for root in outcome.lost:
        print(regressed_line(root))
    return 1 if outcome.rolled_back else 0


def _add_resolve_arguments(resolve: argparse.ArgumentParser) -> None:
    resolve.description = (
        "settle a deny after ESCALATE: allow that edit, or retire the decision"
    )
    resolve.add_argument("receipt", help="the hash of the deny receipt")
    resolve.add_argument("action", choices=["allow", "retire"])
    resolve.add_argument("--reason", required=True)
    resolve.add_argument("--by", help="who resolved; defaults to git user.name")
    resolve.add_argument("--registry", type=Path, help=RESOLVE_REGISTRY_HELP)


def _resolve_command(args: argparse.Namespace) -> int:
    # A bad hash, reason, registry or root is operator error: exit 2, nothing written.
    named = (receipts_path(), args.receipt, args.action, args.reason, _by(args))
    try:
        done = resolve_deny(*named, corrections_path(), args.registry)
    except (ResolveError, RootStoreError, ValidationError, OSError) as error:
        return _loop_refused("resolve", str(error), 2)
    print("\n".join([_resolved_line(done), *_promoted_lines(done)]))
    return 0


def _by(args: argparse.Namespace) -> str:
    return args.by or reviewer_name(Path.cwd())


def _promoted_lines(done: Resolved) -> list[str]:
    # The case is proven by every later recompile of the rule; nothing recompiles now.
    if done.promoted is None:
        return []
    return [
        f"provisional case is now must-pass for {done.receipt.rule_id}: {done.promoted}"
    ]


def _resolved_line(done: Resolved) -> str:
    resolution, receipt = done.receipt.resolution, done.receipt
    assert resolution is not None
    verb = "allowed" if resolution.action == "allow" else "retired"
    cited = f"{receipt.rule_id}, {done.correction.root_id}"
    return f"{resolution.of[:12]}: {verb} by {resolution.by} ({cited}): {resolution.reason}"


def _pin_note(correction: Correction) -> str:
    sha = correction.after.rule_sha
    return (
        f", pinned to rule {sha[:12]}" if correction.action == "confirm" and sha else ""
    )


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


def _add_backfill_arguments(backfill: argparse.ArgumentParser) -> None:
    backfill.description = "store each root's PR merge time, read from the GitHub API"
    backfill.add_argument("--registry", type=Path, help=LOOP_REGISTRY_HELP)


def _backfill_command(args: argparse.Namespace) -> int:
    try:
        roots_dir = _registry_roots(args.registry)
        filled = backfill_merged_at(roots_dir, github_client().merged_at)
    except BACKFILL_ERRORS as error:
        return _loop_refused("backfill-merged", str(error), 2)
    print("\n".join(_backfill_lines(roots_dir, filled)))
    return 0


def _registry_roots(registry: Path | None) -> Path:
    return load_registry(registry or required_clone_registry(Path.cwd())).roots_dir


def _backfill_lines(roots_dir: Path, filled: list[str]) -> list[str]:
    merged = {root.id: root.merged_at for root in load_roots(roots_dir)}
    lines = [f"{root_id}: merged {merged[root_id]}" for root_id in filled]
    left = len(missing_merged_at(roots_dir))
    return lines + [f"{len(filled)} roots backfilled, {left} without a merged PR"]


def _add_reprove_arguments(reprove: argparse.ArgumentParser) -> None:
    reprove.description = "run every proof gate again on each installed rule, without recompiling, and store the result as its proof"
    reprove.add_argument("--registry", type=Path, help=LOOP_REGISTRY_HELP)
    reprove.add_argument("--variants", type=Path, help=VARIANTS_HELP)
    reprove.add_argument("--heldout", type=Path, help=HELDOUT_HELP)
    reprove.add_argument("--work", type=Path, help=WORK_HELP)


def _reprove_command(args: argparse.Namespace) -> int:
    # Every rule reproved 0; a rule or the checkout could not be reproved 1; operator error 2.
    try:
        missed = reprove_registry(_reprove_run(args))
    except REPROVE_ERRORS as error:
        return _loop_refused("reprove", str(error), 2)
    except Exception as error:
        return _loop_refused("reprove", f"{type(error).__name__}: {error}", 1)
    return 1 if missed else 0


def _reprove_run(args: argparse.Namespace) -> Reprove:
    # The token first, so a missing one costs nothing.
    github = github_client()
    registry = args.registry or required_clone_registry(Path.cwd())
    variants = args.variants or default_variants(registry)
    places = (variants, _heldout(args, registry), _work(args, registry))
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return Reprove(github, registry, *places, print, stamp)


def _add_console_arguments(console: argparse.ArgumentParser) -> None:
    console.description = (
        "serve GET /verdict/<receipt-hash> and its /rulings as JSON on loopback"
    )


def _console_command(args: argparse.Namespace) -> int:
    # FastAPI loads only here, never on the hook or other commands' path.
    from knack.console import app

    app.serve()
    return 0


def _add_argue_arguments(argue: argparse.ArgumentParser) -> None:
    argue.add_argument("objection", help="why the latest deny in this clone is wrong")


def _argue_command(args: argparse.Namespace) -> int:
    # Hold and escalate both exit 0; nothing to dispute is operator error, exit 2.
    try:
        done = disputed(args.objection, Path.cwd(), receipts_path(), ask_spark)
    except (NothingToDispute, OSError, ValidationError) as error:
        return _argue_failed(error)
    print(ruling_text(done.record))
    return _recorded_then_second(args.objection, done)


def _recorded_then_second(objection: str, done: Disputed) -> int:
    # The ruling is recorded first; the second opinion never changes the exit.
    code = _record_ruling(done.record)
    _second_opinion_quietly(objection, done)
    return code


def _second_opinion_quietly(objection: str, done: Disputed) -> None:
    # Never changes argue's exit: the ruling stands whatever Spark Open says.
    if not spark_escalated(done):
        return
    try:
        second_opinion(objection, done, _second_ports(done.registry))
    except Exception as error:
        print(f"knack argue: no second opinion: {error}", file=sys.stderr)


def _second_ports(registry: Path) -> Second:
    # Only Spark Open is asked: an objection never builds the compiler or the miss loop.
    return Second(partner_client(DEFAULT_EXTRACTOR), _receipt_places(), registry, print)


def _receipt_places() -> Places:
    # Only receipts and their edit snapshots are read for an argue case.
    receipts = receipts_path()
    return Places(receipts, edits_dir(receipts), [], Path("bench/tickets.jsonl"))


def _record_ruling(ruling: RulingRecord) -> int:
    # The ruling is printed first, so an unwritable log never hides it.
    try:
        append_ruling(rulings_path(), ruling)
    except OSError as error:
        return _argue_failed(error)
    return 0


def _argue_failed(error: Exception) -> int:
    print(f"knack argue: {error}", file=sys.stderr)
    return 2


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


def _add_miss_arguments(miss: argparse.ArgumentParser) -> None:
    miss.description = (
        "record an edit the guard should have denied, then recompile its rule"
    )
    miss.add_argument("source", help=MISS_HELP)
    _add_loop_arguments(miss)


def _add_false_block_arguments(false_block: argparse.ArgumentParser) -> None:
    false_block.description = (
        "record an edit the guard should have allowed, then recompile its rule"
    )
    false_block.add_argument("source", help=FALSE_BLOCK_HELP)
    _add_loop_arguments(false_block)


def _add_loop_arguments(loop: argparse.ArgumentParser) -> None:
    loop.add_argument("--registry", type=Path, help=LOOP_REGISTRY_HELP)
    loop.add_argument("--heldout", type=Path, help=HELDOUT_HELP)
    loop.add_argument("--work", type=Path, help=WORK_HELP)
    _add_source_arguments(loop)
    _add_loop_model_arguments(loop)


def _add_loop_model_arguments(loop: argparse.ArgumentParser) -> None:
    # The compiler, and the other model that writes variants and the fresh set.
    choices, default = list(EXTRACTORS), DEFAULT_EXTRACTOR
    loop.add_argument("--extractor", choices=choices, default=default)
    loop.add_argument("--adversary", choices=choices, help=ADVERSARY_HELP)


def _miss_command(args: argparse.Namespace) -> int:
    return _miss_loop("miss", "must-fail", args)


def _false_block_command(args: argparse.Namespace) -> int:
    return _miss_loop("false-block", "must-pass", args)


def _miss_loop(name: str, kind: CaseKind, args: argparse.Namespace) -> int:
    # Installed or nothing to do 0; old rule kept 1; operator error 2.
    try:
        return _loop_report(_recompiled_for(kind, args))
    except LOOP_ERRORS as error:
        return _loop_refused(name, str(error), 2)
    except Exception as error:
        return _loop_refused(name, f"{type(error).__name__}: {error}; {KEPT}", 1)


def _recompiled_for(kind: CaseKind, args: argparse.Namespace) -> LoopOutcome:
    # Clients first, so a missing key costs nothing and records nothing.
    github, compiler, writer = _loop_clients(args)
    registry = args.registry or required_clone_registry(Path.cwd())
    cases = resolve_source(args.source, kind, _places(args), github)
    places = (registry, _heldout(args, registry), _work(args, registry))
    return record_and_recompile(Loop(github, compiler, writer, *places, print), cases)


def _loop_clients(args: argparse.Namespace) -> tuple[GitHub, Spark, Spark]:
    # The fresh cross-model set needs a writer other than the compiler.
    github, compiler = live_clients(args.extractor)
    writer = adversary_client(args.extractor, args.adversary)
    if writer is None or writer.model == compiler.model:
        raise MissingCredentials(NO_WRITER)
    return github, compiler, writer


def _places(args: argparse.Namespace) -> Places:
    receipts = args.receipts or receipts_path()
    runs = args.runs or sorted(Path("bench").glob("runs*.jsonl"))
    return Places(receipts, edits_dir(receipts), runs, args.tickets)


def _heldout(args: argparse.Namespace, registry: Path) -> Path:
    return args.heldout or default_heldout(registry)


def _work(args: argparse.Namespace, registry: Path) -> Path:
    return args.work or default_work(registry)


def _handlers() -> dict[str, Callable[[argparse.Namespace], int]]:
    handlers = {"guard": _guard_command, "walk": _walk_command}
    handlers |= {"init": _init_command, "watch": _watch_command}
    handlers |= {"confirm": _confirm_command, "reject": _reject_command}
    handlers |= {"import": _import_command, "bench": _bench_command}
    handlers |= {"argue": _argue_command, "console": _console_command}
    handlers |= {"miss": _miss_command, "false-block": _false_block_command}
    handlers |= {"backfill-merged": _backfill_command, "reprove": _reprove_command}
    return handlers | {"receipts": _receipts_command, "resolve": _resolve_command}


def _add_source_arguments(loop: argparse.ArgumentParser) -> None:
    # Where receipt hashes and bench run ids are looked up.
    loop.add_argument("--receipts", type=Path, help=RECEIPTS_HELP)
    loop.add_argument("--runs", type=Path, nargs="+", help=RUNS_HELP)
    loop.add_argument("--tickets", type=Path, default=Path("bench/tickets.jsonl"))


def _loop_report(outcome: LoopOutcome) -> int:
    print("\n".join(outcome_lines(outcome)))
    return 0 if outcome.installed or not outcome.recompiled else 1


def _loop_refused(name: str, reason: str, code: int) -> int:
    print(f"knack {name}: {reason}", file=sys.stderr)
    return code
