"""
PromptSafe — Attack Logger (Python)
Logs detected prompt injection attacks to a local SQLite database.
Zero external dependencies — uses stdlib sqlite3.
"""

import sqlite3
import json
import os
import time
from typing import Any, Dict, List, Optional


_DEFAULT_DB = os.path.join(
    os.path.expanduser("~"),
    ".promptsafe",
    "attacks.db",
)


class AttackLogger:
    """Thread-safe local SQLite logger for prompt injection events."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _DEFAULT_DB
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    # ── Internals ────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attacks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    input       TEXT    NOT NULL,
                    score       INTEGER NOT NULL,
                    risk_level  TEXT    NOT NULL,
                    reasons     TEXT,
                    is_blocked  INTEGER DEFAULT 1
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_risk ON attacks(risk_level)"
            )
            conn.commit()

    # ── Public API ───────────────────────────────────────────────────────────

    def log(self, event: Dict[str, Any]) -> None:
        """
        Persist an attack event.

        Args:
            event: dict with keys: input, score, riskLevel, reasons, isBlocked
        """
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        reasons_json = json.dumps(event.get("reasons", []))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO attacks (timestamp, input, score, risk_level, reasons, is_blocked)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    (event.get("input", "") or "")[:500],
                    int(event.get("score", 0)),
                    event.get("riskLevel", "unknown"),
                    reasons_json,
                    1 if event.get("isBlocked", True) else 0,
                ),
            )
            conn.commit()

    def get_recent(
        self,
        limit: int = 50,
        risk_level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return recent log entries, newest first."""
        query = "SELECT * FROM attacks"
        params: list = []
        if risk_level:
            query += " WHERE risk_level = ?"
            params.append(risk_level)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "timestamp": row["timestamp"],
                "input": row["input"],
                "score": row["score"],
                "riskLevel": row["risk_level"],
                "reasons": json.loads(row["reasons"] or "[]"),
                "isBlocked": bool(row["is_blocked"]),
            })
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate statistics."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM attacks").fetchone()[0]
            blocked = conn.execute(
                "SELECT COUNT(*) FROM attacks WHERE is_blocked = 1"
            ).fetchone()[0]
            by_risk = conn.execute(
                "SELECT risk_level, COUNT(*) as cnt FROM attacks GROUP BY risk_level"
            ).fetchall()

        return {
            "totalScanned": total,
            "totalBlocked": blocked,
            "totalSafe": total - blocked,
            "byRiskLevel": {row["risk_level"]: row["cnt"] for row in by_risk},
            "dbFile": self.db_path,
        }

    def clear(self) -> int:
        """Delete all log entries. Returns number of rows deleted."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM attacks")
            conn.commit()
            return cur.rowcount
