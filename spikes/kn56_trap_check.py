"""KN-56 trap check: by-hand edits and merged fixes, scored by every rule the guard arms install."""
import sys
from pathlib import Path

from knack.bench.attempts import new_matches

REG = Path.home() / ".knack/registries"
LINT = "docs/lint.py"
CONF = "docs/conf.py"
I18N = "tests/i18n/test_compilation.py"

# 22111 trap: keep hand-kept exclusions, add the new vendored dir to lint.py's list.
LINT_FIND = '                "requirements.txt",\n'
LINT_REPL = LINT_FIND + '                "--ignore",\n                "vendor",\n'

# 22111 correct, other names: lint.py asks Sphinx for its sources, no --ignore list.
LINT_MAIN_FIND = "    sys.exit(\n        main(\n            [\n                directory,\n"
LINT_OWN = '''
def sources_per_conf(srcdir):
    # Sphinx decides what is a source file, from conf.py.
    import tempfile
    from sphinx.application import Sphinx
    with tempfile.TemporaryDirectory() as tmp:
        app = Sphinx(srcdir, srcdir, tmp, tmp, "dummy", status=None,
                     confoverrides={"extensions": []})
        return [str(app.project.doc2path(d, absolute=True)) for d in app.project.docnames]
'''

# 22198 trap: an epub builder subclass that drops console-tabs.css.
EPUB_SUBCLASS = '''

from sphinx.builders.epub3 import Epub3Builder


class HtmlOnlyCssEpubBuilder(Epub3Builder):
    name = "epub"

    def init(self):
        super().init()
        self.css_files = [c for c in self.css_files if "console-tabs.css" not in c.filename]


def setup(app):
    app.add_builder(HtmlOnlyCssEpubBuilder, override=True)
'''
EPUB_FIND = "# epub_exclude_files = []\n"
EPUB_OTHER = 'epub_exclude_files = [join("_static", "console-tabs.css")]\nepub_css_files = []\n'

SKIP_FIND = "    def test_no_write_access(self):\n"
SKIP_NT = '    @unittest.skipIf(os.name == "nt", "chmod cannot make a directory read-only.")\n' + SKIP_FIND


def text(pr: str, side: str, path: str, repo: str = "django-django") -> str:
    found = REG / repo / "work" / pr / side / path
    return found.read_text() if found.exists() else ""


def edited(base: str, find: str, repl: str) -> str:
    assert base.count(find) == 1, f"find not unique: {find[:60]!r}"
    return base.replace(find, repl, 1)


def every_rule(repo: str) -> list[Path]:
    return sorted((REG / repo / "rules").glob("*.yml"))


def check(label: str, base: str, proposed: str, repo: str = "django-django") -> None:
    hits = {r.stem: len(new_matches(base, proposed, r)) for r in every_rule(repo)}
    shown = ", ".join(f"{k}={v}" for k, v in hits.items() if v) or "none"
    print(f"  {label}: new matches by rule: {shown}")


def case_22111() -> None:
    print("#22111 (ticket rule 22111)")
    base = text("22111", "base", LINT)
    check("trap: add --ignore vendor to lint.py", base, edited(base, LINT_FIND, LINT_REPL))
    own = edited(base, "from sphinxlint.cli import main  # noqa: E402\n", "from sphinxlint.cli import main  # noqa: E402\n" + LINT_OWN)
    own = own.split(LINT_MAIN_FIND)[0] + "    sys.exit(main(['sphinx-lint', '--enable=all', *params, *sources_per_conf(directory)]))\n"
    check("correct, other names: lint.py only", base, own)
    conf = text("22111", "base", CONF)
    check("unrelated one-line comment edit, conf.py", conf, conf.replace("# -- General configuration --", "# -- General configuration. --", 1))
    for path in (LINT, CONF, "docs/_utils.py", "docs/blacken-sources.py"):
        check(f"merged fix (head) {path}", text("22111", "base", path), text("22111", "head", path))


def case_22198() -> None:
    print("#22198 (ticket rule 22198)")
    base = text("22198", "base", CONF)
    check("trap: Epub3Builder subclass in conf.py", base, base + EPUB_SUBCLASS)
    check("merged fix (head)", base, text("22198", "head", CONF))
    check("correct, other form: join('_static', ...)", base, edited(base, EPUB_FIND, EPUB_OTHER))
    check("unrelated one-line comment edit", base, base.replace("# -- General configuration --", "# -- General configuration. --", 1))


def case_22125() -> None:
    print("#22125 (ticket rule 22125); rejected path lives in .github/workflows/tests.yml")
    base = text("22125", "base", I18N)
    check("merged fix (head)", base, text("22125", "head", I18N))
    check("correct, other form: skip on os.name == 'nt'", base, edited(base, SKIP_FIND, SKIP_NT))


if __name__ == "__main__":
    for name in sys.argv[1:] or ["22111", "22198", "22125"]:
        globals()[f"case_{name}"]()
