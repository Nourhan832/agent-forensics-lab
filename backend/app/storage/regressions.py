import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager


DATABASE_PATH = Path(os.getenv("AFL_DATABASE_PATH") or (
    Path(__file__).resolve().parents[3]
    / "agent_forensics.db"
))


@contextmanager
def get_connection():
    connection = sqlite3.connect(
        DATABASE_PATH, timeout=15
    )

    connection.row_factory = sqlite3.Row

    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_regression_storage():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS regressions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                failure_class TEXT NOT NULL,
                original_trigger TEXT,
                minimal_trigger TEXT NOT NULL,
                guardrail TEXT NOT NULL,
                status TEXT NOT NULL,
                mitigation_verified INTEGER NOT NULL DEFAULT 0,
                before_violations TEXT NOT NULL,
                after_violations TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        columns = {row[1] for row in connection.execute("PRAGMA table_info(regressions)")}
        if "scenario" not in columns:
            connection.execute("ALTER TABLE regressions ADD COLUMN scenario TEXT NOT NULL DEFAULT '{}'")
        connection.commit()
        connection.execute("""
            CREATE TABLE IF NOT EXISTS replay_runs (
                id TEXT PRIMARY KEY,
                regression_id INTEGER,
                category TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def save_regression_case(
    category: str,
    failure_class: str,
    original_trigger: str,
    minimal_trigger: str,
    guardrail: str,
    status: str,
    mitigation_verified: bool,
    before_violations: list,
    after_violations: list,
    scenario: dict | None = None,
) -> dict:

    scenario_json = json.dumps(scenario or {}, sort_keys=True, separators=(",", ":"))
    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    before_json = json.dumps(
        before_violations
    )

    after_json = json.dumps(
        after_violations
    )

    with get_connection() as connection:
        # Serialize concurrent saves without changing or deduplicating existing rows.
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            """SELECT * FROM regressions WHERE category = ? AND failure_class = ?
               AND minimal_trigger = ? AND guardrail = ? AND scenario = ? ORDER BY id LIMIT 1""",
            (category, failure_class, minimal_trigger.strip(), guardrail, scenario_json),
        ).fetchone()
        if existing is not None:
            return serialize_row(existing)
        cursor = connection.execute(
            """
            INSERT INTO regressions (
                category,
                failure_class,
                original_trigger,
                minimal_trigger,
                guardrail,
                status,
                mitigation_verified,
                before_violations,
                after_violations,
                created_at, scenario
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                category,
                failure_class,
                original_trigger,
                minimal_trigger.strip(),
                guardrail,
                status,
                int(mitigation_verified),
                before_json,
                after_json,
                created_at, scenario_json,
            ),
        )

        connection.commit()

        regression_id = cursor.lastrowid

    return get_regression_case(
        regression_id
    )


def get_regression_case(
    regression_id: int,
) -> dict | None:

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM regressions
            WHERE id = ?
            """,
            (regression_id,),
        ).fetchone()

    if row is None:
        return None

    return serialize_row(row)


def list_regression_cases() -> list:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM regressions
            ORDER BY id DESC
            """
        ).fetchall()

    return [
        serialize_row(row)
        for row in rows
    ]


def serialize_row(
    row: sqlite3.Row,
) -> dict:

    return {
        "id": row["id"],
        "category": row["category"],
        "failure_class": row["failure_class"],
        "original_trigger": row["original_trigger"],
        "minimal_trigger": row["minimal_trigger"],
        "guardrail": row["guardrail"],
        "status": row["status"],
        "mitigation_verified": bool(
            row["mitigation_verified"]
        ),
        "before_violations": json.loads(
            row["before_violations"]
        ),
        "after_violations": json.loads(
            row["after_violations"]
        ),
        "scenario": json.loads(row["scenario"]),
        "created_at": row["created_at"],
    }


def save_replay_run(run_id: str, category: str, payload: dict, regression_id=None):
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO replay_runs VALUES (?, ?, ?, ?, ?)",
            (run_id, regression_id, category, json.dumps(payload),
             datetime.now(timezone.utc).isoformat()),
        )


def get_replay_run(run_id: str):
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM replay_runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "category": row["category"],
            "regression_id": row["regression_id"], "payload": json.loads(row["payload"]),
            "created_at": row["created_at"]}


def list_replay_runs(regression_id: int):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id FROM replay_runs WHERE regression_id = ? ORDER BY created_at DESC LIMIT 20",
            (regression_id,),
        ).fetchall()
    return [get_replay_run(row["id"]) for row in rows]
