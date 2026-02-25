"""
KEGG Compound Scraper
=====================

Downloads all KEGG compounds with molecular formula + exact mass
and inserts them into compounds.db.

KEGG has no bulk download — this uses their REST API:
    https://rest.kegg.jp/list/compound       → all compound IDs + names
    https://rest.kegg.jp/get/{id}            → full record per compound

⚠  RUN THIS ON THE SERVER — it makes ~18,000+ API calls.
   On a good connection it takes 2–4 hours.
   It is fully resumable — already-inserted compounds are skipped.

Usage:
    python scripts/scrape_kegg.py                  # full run
    python scripts/scrape_kegg.py --limit 500      # test run (first 500 compounds)
    python scripts/scrape_kegg.py --resume         # skip IDs already in DB
    python scripts/scrape_kegg.py --delay 0.2      # slower (be polite to KEGG)

KEGG Terms: non-commercial academic use only.
"""

import sqlite3
import requests
import time
import re
import os
import argparse
from pathlib import Path

DB_FILE    = "database/compounds.db"
KEGG_BASE  = "https://rest.kegg.jp"

# Mass formula: calculate from formula using monoisotopic masses
MONO_MASSES = {
    'H': 1.0078250319, 'C': 12.0000000,    'N': 14.0030740052,
    'O': 15.9949146221,'S': 31.97207069,   'P': 30.97376151,
    'F': 18.99840322,  'Cl': 34.96885271,  'Br': 78.9183376,
    'I': 126.904468,   'Na': 22.98977,     'K': 38.963707,
    'Ca': 39.962591,   'Mg': 23.985042,    'Fe': 55.934939,
    'Zn': 63.929142,   'Cu': 62.929599,    'Mn': 54.938045,
    'Se': 79.916521,   'Co': 58.933195,    'Si': 27.976927,
    'B':  11.009305,   'As': 74.921596,    'Li': 7.016003,
}

FORMULA_RE = re.compile(r'([A-Z][a-z]?)(\d*)')


def formula_to_mass(formula):
    """Calculate monoisotopic mass from molecular formula string."""
    if not formula:
        return None
    total = 0.0
    for element, count_str in FORMULA_RE.findall(formula):
        count = int(count_str) if count_str else 1
        mass  = MONO_MASSES.get(element)
        if mass is None:
            return None   # unknown element → can't calculate
        total += mass * count
    return round(total, 6) if total > 0 else None


def ensure_kegg_column(conn):
    """Add inchikey column if DB was built without it (backward compat)."""
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE compounds ADD COLUMN inchikey TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists


def get_existing_kegg_ids(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT source_id FROM compounds WHERE source_database='KEGG'")
    return {row[0] for row in cursor.fetchall()}


def fetch_compound_list():
    """Fetch all KEGG compound IDs and names."""
    print("📡 Fetching KEGG compound list...")
    resp = requests.get(f"{KEGG_BASE}/list/compound", timeout=30)
    resp.raise_for_status()

    compounds = []
    for line in resp.text.strip().splitlines():
        if '\t' in line:
            kegg_id, rest = line.split('\t', 1)
            name = rest.split(';')[0].strip()
            compounds.append((kegg_id.strip(), name))

    print(f"   Found {len(compounds):,} KEGG compounds")
    return compounds


def fetch_compound_detail(kegg_id, session):
    """Fetch full KEGG record for one compound. Returns (formula, mass, inchikey)."""
    resp = session.get(f"{KEGG_BASE}/get/{kegg_id}", timeout=15)
    if resp.status_code != 200:
        return None, None, None

    formula  = None
    mass     = None
    inchikey = None

    for line in resp.text.splitlines():
        if line.startswith('FORMULA'):
            formula = line.split(None, 1)[1].strip() if len(line.split(None, 1)) > 1 else None

        elif line.startswith('EXACT_MASS'):
            val = line.split(None, 1)[1].strip() if len(line.split(None, 1)) > 1 else ''
            try:
                mass = float(val)
            except ValueError:
                pass

        elif line.startswith('DBLINKS'):
            # InChIKey sometimes in DBLINKS
            pass

        elif '  InChIKey:' in line:
            inchikey = line.split('InChIKey:')[1].strip()

    # If KEGG didn't provide exact mass, calculate from formula
    if mass is None and formula:
        mass = formula_to_mass(formula)

    return formula, mass, inchikey


def insert_record(cursor, source, source_id, name, formula, mass, cas=None, inchikey=None):
    try:
        cursor.execute('''
            INSERT INTO compounds
                (source_database, source_id, name, formula, exact_mass, cas, inchikey)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (source, source_id, name, formula, mass, cas, inchikey))
        return True
    except sqlite3.IntegrityError:
        return False


def scrape_kegg(limit=None, delay=0.1, resume=True):
    if not Path(DB_FILE).exists():
        print(f"❌ Database not found: {DB_FILE}")
        print("   Run: python scripts/build_database_v5.py first")
        return

    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    ensure_kegg_column(conn)

    existing_ids = get_existing_kegg_ids(conn) if resume else set()
    if existing_ids:
        print(f"   Resuming — {len(existing_ids):,} KEGG compounds already in DB")

    all_compounds = fetch_compound_list()

    if limit:
        all_compounds = all_compounds[:limit]
        print(f"   Test mode — limited to first {limit:,} compounds")

    cursor   = conn.cursor()
    session  = requests.Session()
    session.headers['User-Agent'] = 'LC-MS-MassLookup/1.0 (academic use)'

    inserted  = 0
    skipped   = 0
    no_mass   = 0
    errors    = 0
    total     = len(all_compounds)
    commit_every = 100

    print(f"\n📖 Scraping {total:,} KEGG compounds (delay={delay}s between requests)...")
    print("   Safe to Ctrl+C — resume with --resume flag\n")

    for i, (kegg_id, name) in enumerate(all_compounds, 1):

        # Skip already-inserted
        if kegg_id in existing_ids:
            skipped += 1
            continue

        try:
            formula, mass, inchikey = fetch_compound_detail(kegg_id, session)
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"   ⚠  Error on {kegg_id}: {e}")
            time.sleep(delay * 5)   # back off on errors
            continue

        if mass is None:
            no_mass += 1
        else:
            if insert_record(cursor, "KEGG", kegg_id, name, formula, mass, None, inchikey):
                inserted += 1

        if i % commit_every == 0:
            conn.commit()

        if i % 500 == 0:
            pct = i / total * 100
            print(f"   [{pct:5.1f}%] {i:,}/{total:,} — inserted: {inserted:,} | "
                  f"no_mass: {no_mass:,} | errors: {errors:,}")

        time.sleep(delay)

    conn.commit()
    conn.close()

    print(f"\n✅ KEGG scrape complete")
    print(f"   Inserted:  {inserted:,}")
    print(f"   Skipped (already in DB): {skipped:,}")
    print(f"   No mass:   {no_mass:,}")
    print(f"   Errors:    {errors:,}")


def main():
    parser = argparse.ArgumentParser(description="Scrape KEGG compounds into compounds.db")
    parser.add_argument('--limit',  type=int,   default=None,
                        help='Limit to first N compounds (for testing)')
    parser.add_argument('--delay',  type=float, default=0.1,
                        help='Seconds between API calls (default: 0.1)')
    parser.add_argument('--resume', action='store_true', default=True,
                        help='Skip compounds already in DB (default: True)')
    parser.add_argument('--no-resume', dest='resume', action='store_false',
                        help='Re-fetch all compounds even if already in DB')
    args = parser.parse_args()

    print("=" * 60)
    print("KEGG Compound Scraper")
    print("⚠  Recommended: run on server with good internet")
    print("=" * 60)

    scrape_kegg(limit=args.limit, delay=args.delay, resume=args.resume)


if __name__ == "__main__":
    main()