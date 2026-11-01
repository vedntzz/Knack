from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from knack.console.verdict import RegistryFor

ReceiptKind = Literal["warn", "block", "argue", "held", "learn"]


class CommitEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["commit"] = "commit"
    sha: str
    author: str
    # The first line of the commit message.
    message: str
    # Committer time, as git prints it.
    time: str


class PullEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["pr"] = "pr"
    number: int
    title: str
    state: Literal["open", "merged"]
    # When it merged; when it was opened, while it is still open.
    time: str


class ReceiptEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["receipt"] = "receipt"
    kind: ReceiptKind
    time: str
    root_id: str | None
    # decided_by of the cited root; None with no root or no readable registry.
    decider: str | None
    # The receipt's own hash; the deny's for held and argue; None for a warn.
    receipt_hash: str | None


Event = Annotated[CommitEvent | PullEvent | ReceiptEvent, Field(discriminator="type")]


class Seat(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # A Confirmed root, read from the registry the console reads.
    root_id: str
    decided_by: str
    confirmed_by: str | None
    # The PR its source_url cites; None when it cites no GitHub PR.
    pr: int | None
    merged_at: str | None


class DayFeed(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # None outside git or without an origin remote.
    repo: str | None
    branch: str | None
    # The local calendar day the events fall on, YYYY-MM-DD.
    date: str
    # Every type of event, oldest first.
    events: list[Event]
    # Why no PRs could be read; None when GitHub answered.
    pulls_error: str | None
    # The repo's Confirmed roots, in root id order.
    seats: list[Seat]
    # Why the registry could not be read, so seats and deciders are empty.
    registry_error: str | None


class BranchPulls(Protocol):
    def branch_pulls(self, repo: str, branch: str) -> list[dict[str, Any]]:
        # GitHub's REST pull objects from the branch and into it.
        ...


@dataclass(frozen=True)
class Day:
    # Everything the feed reads; the CLI and the console build it the same way.
    clone: Path
    clock: Callable[[], datetime]
    receipts: Path
    warns: Path
    rulings: Path
    # None when there is no GitHub token.
    pulls: BranchPulls | None
    registry_for: RegistryFor
