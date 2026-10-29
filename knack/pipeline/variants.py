import ast
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

from knack.pipeline.extract import strip_fences
from knack.pipeline.models import Decision
from knack.pipeline.ports import Spark

PER_KIND = 3
# Which model wrote each variant file, beside the files.
AUTHORS = "authors.json"
GENERATION_ATTEMPTS = 3
# Verifier side -> file prefix.
KINDS = {"variant-violation": "violation", "variant-compliant": "compliant"}
Sides = dict[str, dict[str, Path]]
PROMPT = """You write test cases for an engineering decision recorded in a pull request.
Write 3 Python modules that VIOLATE the decision by doing its rejected alternative, and 3 modules
that COMPLY with it by doing what the decision chose.
- A violation is code a reviewer applying this decision would reject; compliant code is code they would accept.
  Each module is code that could live in this repository (source or tests) and touches the API the decision is about.
- Import and use the real repository or library API the decision is about, from its real module (subclass it,
  edit it, call it). Never define stand-in, stub or look-alike versions of that API.
- Use new identifiers for everything else: invent your own function, class, variable and test names.
- Use a different structure in each module (loop vs comprehension, helper vs inline, method vs function, ...).
- Do not copy the PR's code or lightly edit it. The code below is context only.
- Each module must be valid Python on its own, under 40 lines.
Return ONLY JSON: {{"violations": ["<module>", "<module>", "<module>"], "compliant": ["<module>", "<module>", "<module>"]}}

DECISION:
{decision}

PR CODE BEFORE THE DECISION:
{before}

PR CODE AFTER THE DECISION:
{after}
"""


class Variants(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    violations: list[str]
    compliant: list[str]

    @field_validator("violations", "compliant")
    @classmethod
    def three_parsing_modules(cls, modules: list[str]) -> list[str]:
        if len(modules) != PER_KIND:
            raise ValueError(f"expected {PER_KIND} modules, got {len(modules)}")
        for source in modules:
            _require_python(source)
        return modules


def variant_prompt(decision: Decision, before: str, after: str) -> str:
    shown = decision.model_dump_json(indent=2)
    return PROMPT.format(decision=shown, before=before, after=after)


def parse_variants(answer: str) -> Variants:
    # Raises ValueError (pydantic's included) unless 3 parsing modules of each kind.
    return Variants.model_validate(json.loads(strip_fences(answer, "json")))


def generate_variants(
    spark: Spark, prompt: str, tries: int = GENERATION_ATTEMPTS
) -> Variants:
    # An unusable answer is asked again; the last error is raised once tries run out.
    try:
        return parse_variants(spark.ask(prompt))
    except ValueError as error:
        if tries <= 1:
            raise RuntimeError(f"no valid variants after retries: {error!r}") from error
    return generate_variants(spark, prompt, tries - 1)


def variant_files(out: Path, prompt: str, writer: Spark) -> Sides:
    # Cached per PR and writer, so every attempt is scored on the same variants.
    if set(variant_authors(out).values()) != {writer.model}:
        _write_variants(out, generate_variants(writer, prompt), writer.model)
    return {side: _saved(out, prefix) for side, prefix in KINDS.items()}


def variant_authors(out: Path) -> dict[str, str]:
    # Empty for a set saved before authors were recorded, so it is written again.
    path = out / AUTHORS
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _require_python(source: str) -> None:
    # SyntaxError is not a ValueError, so pydantic would not report it.
    try:
        ast.parse(source)
    except SyntaxError as error:
        raise ValueError(f"module does not parse: {error}") from error


def _saved(out: Path, prefix: str) -> dict[str, Path]:
    return {path.name: path for path in sorted(out.glob(f"{prefix}_*.py"))}


def _write_variants(out: Path, variants: Variants, author: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    named = _named_modules(variants)
    for name, source in named.items():
        (out / name).write_text(source, encoding="utf-8")
    authors = json.dumps({name: author for name in named}, indent=2)
    (out / AUTHORS).write_text(authors + "\n", encoding="utf-8")


def _named_modules(variants: Variants) -> dict[str, str]:
    kinds = {"violation": variants.violations, "compliant": variants.compliant}
    return {f"{k}_{i}.py": s for k, ms in kinds.items() for i, s in enumerate(ms, 1)}
