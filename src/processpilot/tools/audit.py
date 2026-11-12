"""Append-only audit trail (POL-07 §1). Local SQLite for now."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

from processpilot import config

DB = config.ROOT / "data" / "audit.sqlite"


def _connect() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS audit (ts TEXT, invoice_id TEXT, event TEXT, detail TEXT)")
    return c


def log(invoice_id: str, event: str, detail: dict) -> None:
    with closing(_connect()) as c, c:
        c.execute("INSERT INTO audit VALUES (?, ?, ?, ?)",
                  (datetime.now(timezone.utc).isoformat(timespec="seconds"), invoice_id, event, json.dumps(detail)))


def recent(invoice_id: str, limit: int = 20) -> list[dict]:
    with closing(_connect()) as c:
            rows = c.execute("SELECT ts, event, detail FROM audit WHERE invoice_id = ? ORDER BY ts DESC, rowid DESC LIMIT ?",
                         (invoice_id, limit)).fetchall()
    return [{"ts": ts, "event": ev, "detail": d} for ts, ev, d in reversed(rows)]


def count_since(event: str, minutes: int) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="seconds")
    with closing(_connect()) as c:
        return c.execute("SELECT COUNT(*) FROM audit WHERE event = ? AND ts >= ?", (event, cutoff)).fetchone()[0]


if __name__ == "__main__":
    with closing(_connect()) as c:
        for row in c.execute("SELECT ts, invoice_id, event, detail FROM audit ORDER BY ts"):
            print(" | ".join(row))