from pathlib import Path

TARGET = "pkg/worker.py"
BASE = "import time\n\n\nasync def poll(client):\n    return await client.get()\n"
HEAD = (
    "import asyncio\n\n\nasync def poll(client):\n"
    "    await asyncio.sleep(1)\n    return await client.get()\n"
)
REJECTED = (
    "import time\n\n\nasync def poll(client):\n"
    "    time.sleep(1)\n    return await client.get()\n"
)


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root
