"""Run knack's CI guard: python scripts/ci_guard.py --base <sha> [--head <sha>]."""

import sys

from knack.ci_guard import main

if __name__ == "__main__":
    sys.exit(main())
