"""
PubChem Scraper
===============
Downloads PubChem compound data using flat files from their FTP server.
Targets only compounds with exact mass in metabolomics range (50-2000 Da).

Strategy:
  1. Download CID-Mass flat file (~2GB) — has CID, formula, exact mass, SMILES
  2. Filter to 50-2000 Da range
  3. Download CID-InChIKey flat file (~500MB) — has CID -> InChIKey mapping
  4. Join and insert into compounds.db

This gives ~5M compounds without hitting rate limits.
Resumable — skips CIDs already in DB.

Run on server:
    python scripts/scrape_pubchem.py
    python scripts/scrape_pubchem.py --limit 10000   # test run
"""

import sqlite3
import requests
import gzip
import os
import time
import argparse
from pathlib import Path

DB_FILE      = "database/compounds.db"
DATA_DIR     = Path("data/raw/pubchem")
MASS_URL     = "https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/CID-Mass.gz"
SMILES_URL   = "https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/CID-SMILES.gz"
TITLE_URL    = "https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/CID-Title.gz"
MASS_FILE    = DATA_DIR / "CID-Mass.gz"
SMILES_FILE  = DATA_DIR / "CID-SMILES.gz"
TITLE_FILE   = DATA_DIR / "CID-Title.gz"

MIN_MASS = 50.0
MAX_MASS = 2000.0
CHUNK    = 10_000


def download_file(url, dest):
    """Download with progress — skips if already downloaded."""
    if dest.exists():
        print(f"  Already downloaded: {dest.name} ({dest.stat().st_size / 1e9:.2f} GB)")
        return
    print(f"  Downloading {url} ...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    total    = int(resp.headers.get('content-length', 0))
    written  = 0
    with open(dest, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            written += len(chunk)
            if total:
                print(f"\r  {written/1e9:.2f} / {total/1e9:.2f} GB", end='', flush=True)
    print(f"\n  Done: {dest.name}")


def get_existing_cids(conn):
    """Return set of CIDs already in DB for PubChem source."""
    rows = conn.execute(
        "SELECT source_id FROM compounds WHERE source_database='PubChem'"
    ).fetchall()
    return {r[0] for r in rows}


def load_flat_map(filepath, label, limit=None):
    """
    Load a CID -> value flat file (tab-separated: CID\tvalue).
    Returns dict: {cid_str: value}
    """
    print(f"Loading {label} map...")
    result = {}
    count  = 0
    with gzip.open(filepath, 'rt', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 2:
                result[parts[0]] = parts[1]
                count += 1
                if limit and count >= limit:
                    break
    print(f"  Loaded {len(result):,} {label} entries")
    return result


def parse_and_insert(conn, smiles_map, title_map, existing_cids, limit=None):
    """
    Parse CID-Mass file, filter by mass range, insert into DB.
    CID-Mass format: CID\tformula\texact_mass (tab-separated)
    """
    cursor   = conn.cursor()
    inserted = 0
    skipped  = 0
    out_of_range = 0
    batch    = []

    print("Parsing CID-Mass file and inserting...")

    with gzip.open(MASS_FILE, 'rt', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) < 3:
                continue

            cid     = parts[0].strip()
            formula = parts[1].strip() if parts[1].strip() else None
            try:
                mass = float(parts[2].strip())
            except ValueError:
                continue

            if mass < MIN_MASS or mass > MAX_MASS:
                out_of_range += 1
                continue

            if cid in existing_cids:
                skipped += 1
                continue

            name         = title_map.get(cid)
            smiles       = smiles_map.get(cid)
            formula_norm = formula.strip().upper().replace(' ', '') if formula else None

            batch.append((
                'PubChem', cid, name,
                formula, mass, None, None, formula_norm, smiles
            ))
            existing_cids.add(cid)

            if len(batch) >= CHUNK:
                _flush(cursor, batch)
                conn.commit()
                inserted += len(batch)
                batch = []
                print(f"  Inserted {inserted:,} compounds...", end='\r')

            if limit and (inserted + len(batch)) >= limit:
                break

    if batch:
        _flush(cursor, batch)
        conn.commit()
        inserted += len(batch)

    print(f"\n  Done — inserted: {inserted:,}  skipped: {skipped:,}  "
          f"out of range: {out_of_range:,}")
    return inserted


def _flush(cursor, batch):
    cursor.executemany('''
        INSERT OR IGNORE INTO compounds
            (source_database, source_id, name, formula, exact_mass,
             cas, inchikey, formula_normalized, smiles)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', batch)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None,
                        help='Max compounds to insert (for testing)')
    parser.add_argument('--skip-download', action='store_true',
                        help='Skip download step (files already present)')
    args = parser.parse_args()

    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")

    # Check smiles column exists
    cols = [r[1] for r in conn.execute("PRAGMA table_info(compounds)").fetchall()]
    if 'smiles' not in cols:
        print("ERROR: smiles column missing. Run migrate_add_smiles.py first.")
        conn.close()
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not args.skip_download:
        print("Step 1/3 — Downloading flat files (CID-Mass ~1.3GB, CID-SMILES ~1.4GB, CID-Title ~1.7GB)")
        download_file(MASS_URL,   MASS_FILE)
        download_file(SMILES_URL, SMILES_FILE)
        download_file(TITLE_URL,  TITLE_FILE)
    else:
        print("Step 1/3 — Skipping download")

    print("\nStep 2/3 — Loading SMILES and Title maps")
    smiles_map = load_flat_map(SMILES_FILE, "SMILES",
                               limit=args.limit * 3 if args.limit else None)
    title_map  = load_flat_map(TITLE_FILE,  "Title",
                               limit=args.limit * 3 if args.limit else None)

    print("\nStep 3/3 — Parsing mass file and inserting")
    existing_cids = get_existing_cids(conn)
    print(f"  Already in DB: {len(existing_cids):,} PubChem compounds")

    start    = time.time()
    inserted = parse_and_insert(conn, smiles_map, title_map, existing_cids,
                                limit=args.limit)
    elapsed  = time.time() - start

    total = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    print(f"\nPubChem import complete in {elapsed:.0f}s")
    print(f"  Inserted:    {inserted:,}")
    print(f"  DB total:    {total:,}")

    conn.close()


if __name__ == "__main__":
    main()