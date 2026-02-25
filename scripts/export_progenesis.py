"""
Progenesis QI Export
====================

Exports compounds from compounds.db into the format expected by
Progenesis QI for metabolomics compound identification.

Progenesis QI expects a CSV with these exact columns:
    Compound, Formula, Neutral mass (Da), Retention time (min),
    Adducts, Identifiers, Notes

Since our DB has no retention time (it's a mass-only DB), we leave
that column blank — Progenesis treats it as "match by mass only".

Usage:
    # Export all sources:
    python scripts/export_progenesis.py

    # Export specific sources:
    python scripts/export_progenesis.py --sources HMDB ChEBI LipidMaps

    # Export with mass range filter:
    python scripts/export_progenesis.py --min-mass 50 --max-mass 1500

    # Custom output path:
    python scripts/export_progenesis.py --output my_export.csv

Output: progenesis_export.csv  (or --output path)
"""

import sqlite3
import csv
import os
import argparse
from pathlib import Path

DB_FILE = "database/compounds.db"


def build_identifier_string(row):
    """
    Build the Identifiers field Progenesis expects.
    Format: 'HMDB:HMDB0000001; CAS:50-99-7; InChIKey:WQZGKKKJIJFFOK-GASJEMHNSA-N'
    """
    parts = []

    source = row['source_database']
    sid    = row['source_id']

    # Source-specific ID with prefix
    if source and sid:
        prefix_map = {
            'HMDB':      'HMDB',
            'ChEBI':     'ChEBI',
            'LipidMaps': 'LMID',
            'NPAtlas':   'NPA',
            'MoNA':      'MoNA',
        }
        prefix = prefix_map.get(source, source)
        parts.append(f"{prefix}:{sid}")

    if row['cas']:
        parts.append(f"CAS:{row['cas']}")

    if row['inchikey']:
        parts.append(f"InChIKey:{row['inchikey']}")

    return '; '.join(parts)


def build_notes_string(row):
    """Build Notes field with source database name."""
    return f"Source: {row['source_database']}"


def export_progenesis(
    output_path="progenesis_export.csv",
    sources=None,
    min_mass=None,
    max_mass=None,
    chunk_size=10_000
):
    if not Path(DB_FILE).exists():
        print(f"❌ Database not found: {DB_FILE}")
        print("   Run: python scripts/build_database_v5.py")
        return

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build query
    conditions = ["exact_mass IS NOT NULL", "name IS NOT NULL", "name != ''"]
    params = []

    if sources:
        placeholders = ','.join('?' * len(sources))
        conditions.append(f"source_database IN ({placeholders})")
        params.extend(sources)

    if min_mass is not None:
        conditions.append("exact_mass >= ?")
        params.append(min_mass)

    if max_mass is not None:
        conditions.append("exact_mass <= ?")
        params.append(max_mass)

    where_clause = " AND ".join(conditions)

    # Count first
    cursor.execute(f"SELECT COUNT(*) FROM compounds WHERE {where_clause}", params)
    total = cursor.fetchone()[0]
    print(f"📊 Exporting {total:,} compounds to Progenesis format...")

    if total == 0:
        print("⚠  No compounds match filter — nothing to export.")
        conn.close()
        return

    # Write CSV
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

    written = 0
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Progenesis QI expected header
        writer.writerow([
            'Compound',
            'Formula',
            'Neutral mass (Da)',
            'Retention time (min)',
            'Adducts',
            'Identifiers',
            'Notes',
        ])

        # Stream in chunks to stay memory-safe
        offset = 0
        while True:
            cursor.execute(
                f"""SELECT source_database, source_id, name, formula,
                           exact_mass, cas, inchikey
                    FROM compounds
                    WHERE {where_clause}
                    ORDER BY exact_mass ASC
                    LIMIT ? OFFSET ?""",
                params + [chunk_size, offset]
            )
            rows = cursor.fetchall()
            if not rows:
                break

            for row in rows:
                writer.writerow([
                    row['name'],
                    row['formula'] or '',
                    f"{row['exact_mass']:.6f}" if row['exact_mass'] else '',
                    '',                          # Retention time — blank (mass-only DB)
                    '',                          # Adducts — Progenesis computes these
                    build_identifier_string(row),
                    build_notes_string(row),
                ])
                written += 1

            offset += chunk_size
            if written % 50_000 == 0:
                print(f"   {written:,} / {total:,} written...")

    conn.close()

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n✅ Export complete")
    print(f"   File:      {output_path}")
    print(f"   Compounds: {written:,}")
    print(f"   Size:      {size_mb:.1f} MB")
    print(f"\nImport into Progenesis QI:")
    print(f"   Identify > Search Databases > Import Database > select {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Export compounds.db to Progenesis QI format")
    parser.add_argument('--output',    default="progenesis_export.csv",
                        help="Output CSV path (default: progenesis_export.csv)")
    parser.add_argument('--sources',   nargs='+',
                        choices=['HMDB', 'ChEBI', 'LipidMaps', 'NPAtlas', 'MoNA'],
                        help="Filter to specific sources (default: all)")
    parser.add_argument('--min-mass',  type=float, default=None,
                        help="Minimum exact mass Da (default: no limit)")
    parser.add_argument('--max-mass',  type=float, default=None,
                        help="Maximum exact mass Da (default: no limit)")
    args = parser.parse_args()

    export_progenesis(
        output_path=args.output,
        sources=args.sources,
        min_mass=args.min_mass,
        max_mass=args.max_mass,
    )


if __name__ == "__main__":
    main()