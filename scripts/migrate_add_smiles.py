"""
Migration: add smiles column
=============================
Safe to run on existing compounds.db — checks if already migrated.

Run once before adding LOTUS data:
    python scripts/migrate_add_smiles.py
"""

import sqlite3

DB_FILE = "database/compounds.db"


def migrate():
    conn = sqlite3.connect(DB_FILE)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(compounds)").fetchall()]

    if 'smiles' in cols:
        print("Already migrated — smiles column exists.")
        conn.close()
        return

    print("Adding smiles column...")
    conn.execute("ALTER TABLE compounds ADD COLUMN smiles TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_smiles ON compounds(smiles)")
    conn.commit()

    print("Done. smiles column added and indexed.")
    conn.close()


if __name__ == "__main__":
    migrate()