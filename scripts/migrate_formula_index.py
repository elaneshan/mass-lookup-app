"""
Migration: add formula_normalized column
=========================================

Adds a pre-normalized formula column so formula search can use an index.
Safe to run on existing compounds.db — checks if already migrated.

Run once:
    python scripts/migrate_formula_index.py

Takes about 30-60 seconds for 494k compounds.
"""

import sqlite3
import time

DB_FILE = "database/compounds.db"


def migrate():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")

    # Check if already migrated
    cols = [r[1] for r in conn.execute("PRAGMA table_info(compounds)").fetchall()]
    if 'formula_normalized' in cols:
        print("✓ Already migrated — formula_normalized column exists")
        count = conn.execute(
            "SELECT COUNT(*) FROM compounds WHERE formula_normalized IS NOT NULL"
        ).fetchone()[0]
        print(f"  {count:,} rows have normalized formula")
        conn.close()
        return

    print("Adding formula_normalized column...")
    start = time.time()

    # Add column
    conn.execute("ALTER TABLE compounds ADD COLUMN formula_normalized TEXT")

    # Populate — SQLite doesn't have REGEXP so we do it in Python in chunks
    CHUNK = 50_000
    total = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    updated = 0

    cursor = conn.cursor()
    offset = 0

    while True:
        rows = conn.execute(
            "SELECT id, formula FROM compounds LIMIT ? OFFSET ?",
            [CHUNK, offset]
        ).fetchall()

        if not rows:
            break

        batch = []
        for row_id, formula in rows:
            if formula:
                normalized = formula.strip().upper().replace(' ', '')
            else:
                normalized = None
            batch.append((normalized, row_id))

        cursor.executemany(
            "UPDATE compounds SET formula_normalized = ? WHERE id = ?",
            batch
        )
        conn.commit()

        updated += len(rows)
        offset  += CHUNK
        pct = updated / total * 100
        print(f"  {updated:,} / {total:,}  ({pct:.0f}%)")

    # Create index on normalized column
    print("Creating index on formula_normalized...")
    conn.execute("DROP INDEX IF EXISTS idx_formula_normalized")
    conn.execute("CREATE INDEX idx_formula_normalized ON compounds(formula_normalized)")
    conn.commit()

    elapsed = time.time() - start
    print(f"\n✅ Migration complete in {elapsed:.1f}s")
    print(f"   Updated: {updated:,} rows")
    print(f"   Index:   idx_formula_normalized")
    print(f"\nNow run: python tests/diagnose_performance.py")

    conn.close()


if __name__ == "__main__":
    migrate()