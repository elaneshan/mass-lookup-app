"""
Performance Optimization Migration
====================================
Run once after PubChem import to speed up searches on the large database.

Adds:
  1. Partial index on exact_mass WHERE source_database = 'PubChem'
     - Makes PubChem mass search ~10x faster without affecting other sources
  2. Index on source_database column alone
     - Speeds up filtering when PubChem is toggled on/off
  3. ANALYZE — updates SQLite query planner statistics

Run on server:
    python scripts/optimize_db.py
"""

import sqlite3
import time

DB_FILE = "database/compounds.db"


def optimize():
    print(f"Opening {DB_FILE}...")
    conn = sqlite3.connect(DB_FILE)

    # Set high cache for this session
    conn.execute("PRAGMA cache_size = -131072")  # 128MB
    conn.execute("PRAGMA journal_mode = WAL")

    # Check current indexes
    existing = {r[1] for r in conn.execute("SELECT type, name FROM sqlite_master WHERE type='index'").fetchall()}
    print(f"Existing indexes: {len(existing)}")

    steps = [
        (
            "idx_source_database",
            "CREATE INDEX IF NOT EXISTS idx_source_database ON compounds(source_database)"
        ),
        (
            "idx_pubchem_mass",
            "CREATE INDEX IF NOT EXISTS idx_pubchem_mass ON compounds(exact_mass) WHERE source_database = 'PubChem'"
        ),
        (
            "idx_pubchem_formula",
            "CREATE INDEX IF NOT EXISTS idx_pubchem_formula ON compounds(formula_normalized) WHERE source_database = 'PubChem'"
        ),
    ]

    for name, sql in steps:
        if name in existing:
            print(f"  Already exists: {name}")
            continue
        print(f"  Building {name}...", end=" ", flush=True)
        start = time.time()
        conn.execute(sql)
        conn.commit()
        print(f"done ({time.time()-start:.1f}s)")

    print("  Running ANALYZE...", end=" ", flush=True)
    start = time.time()
    conn.execute("ANALYZE")
    conn.commit()
    print(f"done ({time.time()-start:.1f}s)")

    # Report DB stats
    total = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    by_source = conn.execute(
        "SELECT source_database, COUNT(*) FROM compounds GROUP BY source_database ORDER BY COUNT(*) DESC"
    ).fetchall()

    print(f"\nDatabase: {total:,} total compounds")
    for src, cnt in by_source:
        print(f"  {src or 'unknown':<15} {cnt:,}")

    conn.close()
    print("\nOptimization complete.")


if __name__ == "__main__":
    optimize()