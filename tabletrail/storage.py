"""Disk-backed exact counts, so distinct values do not accumulate in RAM."""

import json
from pathlib import Path
import sqlite3
import tempfile


class Counts:
    def __enter__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="tabletrail-")
        self.db = sqlite3.connect(Path(self.directory.name) / "counts.sqlite")
        self.db.execute("PRAGMA cache_size = -4096")
        self.db.execute("""CREATE TABLE counts (
            scope TEXT, value TEXT, first_record INTEGER, n INTEGER,
            PRIMARY KEY(scope, value)) WITHOUT ROWID""")
        return self

    def add(self, scope: str, value, record: int) -> int | None:
        encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
        old = self.db.execute("SELECT first_record FROM counts WHERE scope=? AND value=?",
                              (scope, encoded)).fetchone()
        if old:
            self.db.execute("UPDATE counts SET n=n+1 WHERE scope=? AND value=?", (scope, encoded))
            return old[0]
        self.db.execute("INSERT INTO counts VALUES (?, ?, ?, 1)", (scope, encoded, record))
        return None

    def summary(self, scope: str) -> tuple[int, list[dict]]:
        total = self.db.execute("SELECT COUNT(*) FROM counts WHERE scope=?", (scope,)).fetchone()[0]
        top = self.db.execute(
            "SELECT value, n FROM counts WHERE scope=? ORDER BY n DESC, value ASC LIMIT 5",
            (scope,)).fetchall()
        return total, [{"value": json.loads(v), "count": n} for v, n in top]

    def __exit__(self, *args):
        self.db.close()
        self.directory.cleanup()
