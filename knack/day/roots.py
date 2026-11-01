from pathlib import Path

from knack.console.verdict import registry_at
from knack.contracts.models import Root
from knack.roots.store import load_roots, RootStoreError

# The registry's roots, and why they could not be read; read as the console reads them.
ReadRoots = tuple[list[Root], str | None]


def registry_roots(path: Path | None) -> ReadRoots:
    registry, error = registry_at(path)
    if registry is None:
        return [], error
    try:
        return load_roots(registry.roots_dir), None
    except (RootStoreError, OSError) as error:
        return [], str(error).splitlines()[0]
