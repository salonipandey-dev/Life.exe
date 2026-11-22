"""Run the server: ``python -m lifeexe`` (reads LIFEEXE_* environment variables)."""

from __future__ import annotations

import os

import uvicorn

from lifeexe.main import create_app


def main() -> None:
    host = os.getenv("LIFEEXE_HOST", "127.0.0.1")
    port = int(os.getenv("LIFEEXE_PORT", "8000"))
    # One worker: the in-process rate limiter and SQLite writer lock assume a
    # single process (see docs/adr/ADR-003 and the technical-debt register).
    uvicorn.run(create_app(), host=host, port=port, workers=1, access_log=False, proxy_headers=True)


if __name__ == "__main__":
    main()
