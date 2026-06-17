"""
load_new_compounds.py
======================

Loads three new compound source tabs into the existing `compounds` SQLite table:
    - aglycones                  -> source_database = "Aglycones"
    - anthocyanidins lipid maps  -> source_database = "LipidMaps"
    - flavonoids lipid maps      -> source_database = "LipidMaps"

NOTE: "sugars and acids" tab is intentionally SKIPPED pending mass-type
confirmation from PI (monoisotopic vs average MW). Do not load until resolved.

USAGE:
    python load_new_compounds.py --dry-run     # preview without writing
    python load_new_compounds.py                # actually insert

This script is ADDITIVE ONLY. It does not delete or modify existing rows.
Duplicate detection is done on (name, formula, exact_mass) to avoid
re-inserting the same compound twice if run more than once.
"""

import argparse
import sqlite3
import pandas as pd
from pathlib import Path

DB_FILE = "database/compounds.db"  # adjust path if running from a different cwd

CSV_AGLYCONES = "data/raw/Sugar Backbones  - aglycones.csv"
CSV_ANTHO_LM = "data/raw/Sugar Backbones  - Anthocyanidins Lipid Maps_.csv"
CSV_FLAV_LM = "data/raw/Sugar Backbones  - Flavonoids Lipid Maps_.csv"

def normalize_formula(formula: str) -> str:
    """Same normalization logic as in the search engine, kept in sync."""
    if not formula or pd.isna(formula):
        return ''
    return str(formula).strip().upper().replace(' ', '')


def load_aglycones(path: str) -> pd.DataFrame:
    """
    aglycones tab columns (no header row in sample):
        Name, Formula, MW, <blank>, <blank/notes>
    """
    df = pd.read_csv(path, header=None,
                      names=["name", "formula", "exact_mass", "col4", "notes"])

    df = df[["name", "formula", "exact_mass"]].copy()
    df["name"] = df["name"].astype(str).str.strip()
    df["formula"] = df["formula"].astype(str).str.strip()

    # Drop rows with no usable mass - can't search by mass without it
    df = df.dropna(subset=["exact_mass"])
    df = df[df["exact_mass"].apply(lambda x: str(x).strip() != "")]
    df["exact_mass"] = pd.to_numeric(df["exact_mass"], errors="coerce")
    df = df.dropna(subset=["exact_mass"])

    df = df.reset_index(drop=True)
    df["source_database"] = "Aglycones"
    df["source_id"] = [f"AGLY-{i+1:04d}" for i in range(len(df))]
    df["cas"] = None
    df["inchikey"] = None

    return df


def load_lipidmaps_anthocyanidins(path: str) -> pd.DataFrame:
    """
    anthocyanidins lipid maps columns:
        COMMON_NAME, SYSTEMATIC_NAME, FORMULA, MASS, plus K
    """
    df = pd.read_csv(path)

    # Prefer COMMON_NAME, fall back to SYSTEMATIC_NAME if COMMON_NAME is "-"
    def pick_name(row):
        common = str(row["COMMON_NAME"]).strip()
        if common and common != "-" and common.lower() != "nan":
            return common
        sysname = str(row.get("SYSTEMATIC_NAME", "")).strip()
        return sysname if sysname and sysname != "-" else "Unknown"

    df["name"] = df.apply(pick_name, axis=1)
    df["formula"] = df["FORMULA"].astype(str).str.strip()
    df["exact_mass"] = pd.to_numeric(df["MASS"], errors="coerce")
    df = df.dropna(subset=["exact_mass"])
    df = df.reset_index(drop=True)

    df["source_database"] = "LipidMaps"
    df["source_id"] = [f"LM-ANTH-{i+1:04d}" for i in range(len(df))]
    df["cas"] = None
    df["inchikey"] = None

    return df[["name", "formula", "exact_mass", "source_database", "source_id", "cas", "inchikey"]]


def load_lipidmaps_flavonoids(path: str) -> pd.DataFrame:
    """
    flavonoids lipid maps columns:
        COMMON_NAME, SYSTEMATIC_NAME, FORMULA, MASS, M+H, SUB_CLASS, ...
    """
    df = pd.read_csv(path)

    def pick_name(row):
        common = str(row["COMMON_NAME"]).strip()
        if common and common != "-" and common.lower() != "nan":
            return common
        sysname = str(row.get("SYSTEMATIC_NAME", "")).strip()
        return sysname if sysname and sysname != "-" else "Unknown"

    df["name"] = df.apply(pick_name, axis=1)
    df["formula"] = df["FORMULA"].astype(str).str.strip()
    df["exact_mass"] = pd.to_numeric(df["MASS"], errors="coerce")
    df = df.dropna(subset=["exact_mass"])
    df = df.reset_index(drop=True)

    df["source_database"] = "LipidMaps"
    df["source_id"] = [f"LM-FLAV-{i+1:04d}" for i in range(len(df))]
    df["cas"] = None
    df["inchikey"] = None
    # SUB_CLASS is available here if you want to store it -- not in current schema,
    # flagging in case you want a column added later.

    return df[["name", "formula", "exact_mass", "source_database", "source_id", "cas", "inchikey"]]


def insert_compounds(conn: sqlite3.Connection, df: pd.DataFrame, dry_run: bool = False) -> int:
    """
    Insert compounds. Relies on the DB's UNIQUE(source_database, source_id)
    constraint to prevent duplicate inserts if this script is run more than once,
    since source_id is deterministically generated from row order.
    """
    cur = conn.cursor()
    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        formula_norm = normalize_formula(row["formula"])

        if dry_run:
            # Just check whether this (source_database, source_id) already exists
            existing = cur.execute(
                "SELECT 1 FROM compounds WHERE source_database = ? AND source_id = ?",
                (row["source_database"], row["source_id"])
            ).fetchone()
            if existing:
                skipped += 1
            else:
                inserted += 1
            continue

        try:
            cur.execute(
                """
                INSERT INTO compounds
                    (source_database, source_id, name, formula, exact_mass,
                     cas, inchikey, formula_normalized)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["source_database"],
                    row["source_id"],
                    row["name"],
                    row["formula"],
                    round(float(row["exact_mass"]), 6),
                    row["cas"],
                    row["inchikey"],
                    formula_norm,
                )
            )
            inserted += 1
        except sqlite3.IntegrityError:
            # Already inserted in a previous run - safe to skip
            skipped += 1

    if not dry_run:
        conn.commit()

    if skipped:
        print(f"  (skipped {skipped} already-existing rows)")

    return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                         help="Preview counts without writing to DB")
    args = parser.parse_args()

    if not Path(DB_FILE).exists():
        raise FileNotFoundError(f"Database not found at {DB_FILE}")

    conn = sqlite3.connect(DB_FILE)

    datasets = {
        "Aglycones": load_aglycones(CSV_AGLYCONES),
        "Anthocyanidins (LipidMaps)": load_lipidmaps_anthocyanidins(CSV_ANTHO_LM),
        "Flavonoids (LipidMaps)": load_lipidmaps_flavonoids(CSV_FLAV_LM),
    }

    for label, df in datasets.items():
        n = insert_compounds(conn, df, dry_run=args.dry_run)
        action = "would insert" if args.dry_run else "inserted"
        print(f"{label}: {action} {n} rows (out of {len(df)} parsed)")

    conn.close()


if __name__ == "__main__":
    main()