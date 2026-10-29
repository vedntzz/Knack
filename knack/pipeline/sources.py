from pathlib import Path

from knack.pipeline.models import PullRequest
from knack.pipeline.ports import GitHub


def fetch_side(
    github: GitHub, repo: str, pr: PullRequest, side: str, work: Path
) -> dict[str, Path]:
    # The PR's Python files at base or head, under work/<side>/; missing files are left out.
    sha = pr.base_sha if side == "base" else pr.head_sha
    texts = {name: github.file_at(repo, sha, name) for name in pr.python_files}
    return {
        name: _saved(work / side / name, text)
        for name, text in texts.items()
        if text is not None
    }


def joined_source(files: dict[str, Path]) -> str:
    return "\n\n".join(
        f"# file: {name}\n{path.read_text(encoding='utf-8')}"
        for name, path in files.items()
    )


def _saved(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
