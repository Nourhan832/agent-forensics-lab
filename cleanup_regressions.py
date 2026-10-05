"""Explicit legacy maintenance helper. Importing never changes storage."""

def main():
    import argparse
    import sqlite3
    from datetime import datetime, timezone
    from pathlib import Path


    # ---------------------------------------------------------
    # PATHS
    # ---------------------------------------------------------

    PROJECT_ROOT = Path(__file__).resolve().parent

    DB_PATH = PROJECT_ROOT / "agent_forensics.db"

    BACKUP_PATH = PROJECT_ROOT / ("agent_forensics_backup_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".db")


    # ---------------------------------------------------------
    # SAFETY CHECK
    # ---------------------------------------------------------

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )


    # ---------------------------------------------------------
    # BACKUP DATABASE FIRST
    # ---------------------------------------------------------

    parser = argparse.ArgumentParser(description="Legacy cleanup of IDs 1 and 2 only; defaults to dry run.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print("Dry run: would back up storage and remove legacy IDs 1 and 2. AFL-3 and AFL-4 are retained.")
        return
    with sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True) as source:
        with sqlite3.connect(BACKUP_PATH) as target:
            source.backup(target)

    print(
        f"Backup created: {BACKUP_PATH}"
    )


    # ---------------------------------------------------------
    # CONNECT
    # ---------------------------------------------------------

    connection = sqlite3.connect(
        DB_PATH
    )

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()


    # ---------------------------------------------------------
    # SHOW CURRENT REGRESSIONS
    # ---------------------------------------------------------

    cursor.execute(
        """
        SELECT
            id,
            category,
            failure_class,
            minimal_trigger,
            status
        FROM regressions
        ORDER BY id
        """
    )

    before_rows = cursor.fetchall()


    print("\nBefore cleanup:\n")

    for row in before_rows:

        print(
            f"AFL-{row['id']} | "
            f"{row['failure_class']} | "
            f"{row['minimal_trigger']} | "
            f"{row['status']}"
        )


    # ---------------------------------------------------------
    # KEEP AFL-3
    # DELETE AFL-1 AND AFL-2
    # ---------------------------------------------------------

    cursor.execute(
        """
        DELETE FROM regressions
        WHERE id IN (?, ?)
        """,
        (
            1,
            2,
        ),
    )


    connection.commit()


    # ---------------------------------------------------------
    # SHOW RESULT
    # ---------------------------------------------------------

    cursor.execute(
        """
        SELECT
            id,
            category,
            failure_class,
            minimal_trigger,
            status
        FROM regressions
        ORDER BY id
        """
    )

    after_rows = cursor.fetchall()


    print("\nAfter cleanup:\n")

    for row in after_rows:

        print(
            f"AFL-{row['id']} | "
            f"{row['failure_class']} | "
            f"{row['minimal_trigger']} | "
            f"{row['status']}"
        )


    print(
        f"\nDeleted {len(before_rows) - len(after_rows)} regression record(s)."
    )


    print(
        "\nLegacy IDs 1 and 2 removed; all other cases retained."
    )


    connection.close()

if __name__ == "__main__":
    main()
