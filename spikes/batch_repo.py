# Per-repo locations for the batch spikes: every repo's outputs live under spikes/batch/<owner-name>/.
import argparse, os, re
from dataclasses import dataclass
from pathlib import Path

import requests

DEFAULT_REPO = "apache/airflow"
BATCH_ROOT = Path(__file__).parent / "batch"
REPO_PATTERN = re.compile(r"[\w.-]+/[\w.-]+")


def owner_name(value):
    # argparse type: anything but exactly owner/name exits with a usage error
    if not REPO_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(f"expected owner/name, got {value!r}")
    return value


def repo_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--repo", type=owner_name, default=DEFAULT_REPO, help="GitHub owner/name")
    return parser


def default_branch(batch):
    # the clone branch when --ref is not given: whatever the repo calls its default (main, master, ...)
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.get(batch.api, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json()["default_branch"]


@dataclass(frozen=True)
class Batch:
    repo: str
    root: Path = BATCH_ROOT

    @property
    def slug(self):
        return self.repo.replace("/", "-")

    @property
    def dir(self):
        return self.root / self.slug

    @property
    def api(self):
        return f"https://api.github.com/repos/{self.repo}"

    @property
    def clone_url(self):
        return f"https://github.com/{self.repo}.git"

    @property
    def prs(self):
        return self.dir / "prs.json"

    @property
    def decisions(self):
        return self.dir / "decisions.jsonl"

    @property
    def rules(self):
        return self.dir / "rules"

    @property
    def src(self):
        return self.dir / "src"
