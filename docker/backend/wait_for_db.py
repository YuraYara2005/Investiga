"""
wait_for_db.py – Pure-stdlib TCP connectivity probe for PostgreSQL.

Reads DATABASE__URL from the environment, extracts host and port, then polls
until a TCP connection is accepted or the timeout expires.

Exit codes:
    0 – connection accepted
    1 – timeout or configuration error
"""

from __future__ import annotations

import os
import re
import socket
import sys
import time

# ---------------------------------------------------------------------------- #
# Configuration
# ---------------------------------------------------------------------------- #
TIMEOUT_SECONDS = int(os.environ.get("DB_WAIT_TIMEOUT", "60"))
POLL_INTERVAL = float(os.environ.get("DB_WAIT_INTERVAL", "2"))

# ---------------------------------------------------------------------------- #
# Parse host / port from DATABASE__URL
# Expected format (asyncpg): postgresql+asyncpg://user:pass@host:port/dbname
# ---------------------------------------------------------------------------- #
db_url = os.environ.get("DATABASE__URL", "")

# Accept both postgresql and postgresql+asyncpg schemes
_match = re.search(
    r"@(?P<host>[^:/]+)(?::(?P<port>\d+))?/",
    db_url,
)

if not _match:
    # Fall back to individual env vars or sane defaults
    DB_HOST = os.environ.get("POSTGRES_HOST", "postgres")
    DB_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
else:
    DB_HOST = _match.group("host")
    DB_PORT = int(_match.group("port") or "5432")


def _probe(host: str, port: int) -> bool:
    """Attempt a single TCP connection. Returns True on success."""
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def main() -> int:
    print(
        f"[wait_for_db] Probing PostgreSQL at {DB_HOST}:{DB_PORT} "
        f"(timeout={TIMEOUT_SECONDS}s, interval={POLL_INTERVAL}s)",
        flush=True,
    )

    deadline = time.monotonic() + TIMEOUT_SECONDS
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        if _probe(DB_HOST, DB_PORT):
            print(
                f"[wait_for_db] Connection accepted on attempt #{attempt}.",
                flush=True,
            )
            return 0

        remaining = int(deadline - time.monotonic())
        print(
            f"[wait_for_db] Attempt #{attempt}: PostgreSQL not ready yet "
            f"({remaining}s remaining) …",
            flush=True,
        )
        time.sleep(POLL_INTERVAL)

    print(
        f"[wait_for_db] ERROR: PostgreSQL at {DB_HOST}:{DB_PORT} "
        f"did not accept connections within {TIMEOUT_SECONDS}s.",
        file=sys.stderr,
        flush=True,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
