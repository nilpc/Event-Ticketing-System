"""FR-9, NFR-3: Entry point for background workers.

Usage:
    python -m services.workers sweeper
    python -m services.workers relay
    python -m services.workers admitter
"""

from __future__ import annotations

import asyncio
import sys

_WORKERS = {
    "sweeper": "services.workers.sweeper",
    "relay": "services.workers.relay",
    "admitter": "services.workers.admitter",
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in _WORKERS:
        names = ", ".join(sorted(_WORKERS))
        print(f"Usage: python -m services.workers <{names}>", file=sys.stderr)
        sys.exit(1)

    worker_name = sys.argv[1]
    module = __import__(_WORKERS[worker_name], fromlist=["run_" + worker_name])
    run_fn = getattr(module, "run_" + worker_name)
    asyncio.run(run_fn())


if __name__ == "__main__":
    main()
