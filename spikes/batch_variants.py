# Variant check: Spark writes fresh violations and compliant versions of a decision, and the rule is scored on them.
import ast, json

from q3_extract import answer_json

PER_KIND = 3
GENERATION_ATTEMPTS = 3
# JSON key -> (verifier side, file prefix)
KINDS = {"violations": ("variant-violation", "violation"), "compliant": ("variant-compliant", "compliant")}
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


def variant_prompt(decision, before, after):
    return PROMPT.format(decision=json.dumps(decision, indent=2), before=before, after=after)


def checked_variants(data):
    # raises unless every kind has exactly 3 modules and each one parses
    for kind in KINDS:
        if len(data[kind]) != PER_KIND:
            raise ValueError(f"{kind}: expected {PER_KIND} modules, got {len(data[kind])}")
        for source in data[kind]:
            ast.parse(source)
    return data


def generate_variants(prompt, ask):
    last = None
    for _ in range(GENERATION_ATTEMPTS):
        try:
            return checked_variants(answer_json(ask(prompt)))
        except (ValueError, KeyError, TypeError, IndexError, SyntaxError) as error:
            last = error
    raise RuntimeError(f"no valid variants after {GENERATION_ATTEMPTS} tries: {last!r}")


def variant_files(out, prompt, ask):
    # generated once per PR and cached, so every compile attempt is scored on the same variants
    if not any(out.glob("violation_*.py")):
        write_variants(out, generate_variants(prompt, ask))
    return {side: {path.name: path for path in sorted(out.glob(f"{prefix}_*.py"))} for side, prefix in KINDS.values()}


def write_variants(out, data):
    out.mkdir(parents=True, exist_ok=True)
    for kind, (_, prefix) in KINDS.items():
        for i, source in enumerate(data[kind], 1):
            (out / f"{prefix}_{i}.py").write_text(source)
