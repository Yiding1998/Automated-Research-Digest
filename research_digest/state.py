from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class SeenState:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True) if self.path.parent != Path(".") else None
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(
            """
            create table if not exists seen_items (
                fingerprint text primary key,
                first_seen text not null
            )
            """
        )
        self.conn.commit()

    def contains(self, fingerprint: str) -> bool:
        row = self.conn.execute(
            "select 1 from seen_items where fingerprint = ?",
            (fingerprint,),
        ).fetchone()
        return row is not None

    def mark_many(self, fingerprints: list[str]) -> None:
        now = datetime.now(UTC).isoformat()
        self.conn.executemany(
            "insert or ignore into seen_items (fingerprint, first_seen) values (?, ?)",
            [(fingerprint, now) for fingerprint in fingerprints],
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "SeenState":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
