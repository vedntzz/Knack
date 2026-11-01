"""Trap check: the rejected approach, applied by hand to the sandbox base file, must be a new match of the installed rule."""
import sys
from pathlib import Path

from knack.bench.attempts import new_matches
from knack.home import knack_home

KNACK = Path("/Users/vedant/Documents/knack")
BATCH = KNACK / "spikes/batch"
HOME = knack_home() / "registries"

PUB = "airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py"
UI = "airflow-core/src/airflow/api_fastapi/core_api/routes/ui/dags.py"
ROUTING = "fastapi/routing.py"
HOOK = "providers/common/ai/src/airflow/providers/common/ai/hooks/pydantic_ai.py"

UI_ALIAS_FIND = '                    "last_run_run_after": DagRun.run_after,\n'
UI_ALIAS_REPL = UI_ALIAS_FIND + '                    "state": DagRun.state,\n                    "start_date": DagRun.start_date,\n'
ALIAS_FIND = '{"last_run_state": DagRun.state, "last_run_start_date": DagRun.start_date},'
ALIAS_REPL = (
    '{\n                    "last_run_state": DagRun.state,\n'
    '                    "last_run_start_date": DagRun.start_date,\n'
    '                    "state": DagRun.state,\n'
    '                    "start_date": DagRun.start_date,\n                },'
)

SSE_FIND = (
    '                    media_type="text/event-stream",\n'
    "                    background=solved_result.background_tasks,\n"
)
SSE_REPL = (
    '                    media_type="text/event-stream",\n'
    "                    status_code=solved_result.response.status_code or status_code or 200,\n"
    "                    background=solved_result.background_tasks,\n"
)
JSONL_FIND = (
    '                    media_type="application/jsonl",\n'
    "                    background=solved_result.background_tasks,\n"
)
JSONL_REPL = (
    '                    media_type="application/jsonl",\n'
    "                    status_code=solved_result.response.status_code or status_code or 200,\n"
    "                    background=solved_result.background_tasks,\n"
)

TO_THREAD = '''
    async def get_conn_async(self) -> Model:
        """Build the model without blocking the event loop."""
        return await asyncio.to_thread(self.get_conn)

    def get_conn(self) -> Model:'''
SINGLE_WORKER = '''
    async def get_conn_async(self) -> Model:
        """Build the model on the hook's own single worker."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_HOOK_EXECUTOR, self.get_conn)

    def get_conn(self) -> Model:'''
EXECUTOR_LINE = (
    "\n_HOOK_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1)\n\n\nclass PydanticAIHook("
)


def edited(text: str, *pairs: tuple[str, str]) -> str:
    for find, repl in pairs:
        assert text.count(find) == 1, f"find not unique: {find[:60]!r}"
        text = text.replace(find, repl, 1)
    return text


def with_imports(text: str) -> str:
    # The by-hand async edits need asyncio / concurrent.futures imported.
    return text.replace("\nimport re\n", "\nimport asyncio\nimport concurrent.futures\nimport re\n", 1)


def check(label: str, base: str, proposed: str, rule: Path) -> None:
    found = new_matches(base, proposed, rule)
    print(f"  {label}: {len(found)} new match(es)")
    for m in found:
        print("    | " + m.splitlines()[0][:110] + (f"  (+{m.count(chr(10))} lines)" if "\n" in m else ""))


def case_75025() -> None:
    rule = HOME / "apache-airflow/rules/75025.yml"
    src = BATCH / "apache-airflow/src/75025"
    for path, pair in ((PUB, (ALIAS_FIND, ALIAS_REPL)), (UI, (UI_ALIAS_FIND, UI_ALIAS_REPL))):
        base = (src / "base" / path).read_text()
        print(f"#75025 {path.split('routes/')[1]} (rule {rule.name})")
        check("trap: alias state/start_date onto DagRun", base, edited(base, pair), rule)
        check("merged fix (head)", base, (src / "head" / path).read_text(), rule)


def case_15937() -> None:
    rule = HOME / "fastapi-fastapi/rules/15937.yml"
    src = BATCH / "fastapi-fastapi/src/15937"
    base = (src / "base" / ROUTING).read_text()
    print(f"#15937 {ROUTING} (rule {rule.name})")
    check("trap: status_code= inline in SSE + JSONL", base, edited(base, (SSE_FIND, SSE_REPL), (JSONL_FIND, JSONL_REPL)), rule)
    check("trap: SSE only", base, edited(base, (SSE_FIND, SSE_REPL)), rule)
    check("merged fix (head)", base, (src / "head" / ROUTING).read_text(), rule)


def case_74150() -> None:
    rule = HOME / "apache-airflow/rules/74150.yml"
    src = BATCH / "apache-airflow/src/74150"
    base = (src / "base" / HOOK).read_text()
    anchor = "\n    def get_conn(self) -> Model:"
    print(f"#74150 hooks/pydantic_ai.py (rule {rule.name})")
    check("trap: asyncio.to_thread(self.get_conn)", base, with_imports(edited(base, (anchor, TO_THREAD))), rule)
    single = with_imports(edited(base, (anchor, SINGLE_WORKER), ("\n\n\nclass PydanticAIHook(", EXECUTOR_LINE)))
    check("correct, other names: single-worker executor", base, single, rule)
    check("merged fix (head)", base, (src / "head" / HOOK).read_text(), rule)


if __name__ == "__main__":
    for name in sys.argv[1:] or ["75025", "15937", "74150"]:
        globals()[f"case_{name}"]()
