"""
fix_aglycone_masses.py
=======================

PROBLEM:
The 'aglycones' CSV tab contained average molecular weight (MW) values,
not monoisotopic mass. This is inconsistent with every other source in
the `compounds` table (HMDB, ChEBI, LipidMaps), which all use monoisotopic
mass. This script recalculates correct monoisotopic mass from the molecular
formula for every row with source_database = 'Aglycones', and shows a
before/after diff for review before any write happens.

SCOPE: Only touches rows where source_database = 'Aglycones'.
Nothing else in the table is read or modified.

USAGE:
    python3 scripts/fix_aglycone_masses.py --dry-run     # preview diffs only
    python3 scripts/fix_aglycone_masses.py                # apply the update
"""

import argparse
import re
import sqlite3
from pathlib import Path

DB_FILE = "database/compounds.db"

# Rows flagged as having a likely data-entry error in the source spreadsheet
# (not just an average-vs-monoisotopic mass mismatch -- the formula and the
# originally-listed mass don't correspond to the same compound at all).
# These are SKIPPED here and left untouched pending manual review against
# the original spreadsheet.
SKIP_SOURCE_IDS = {
    "AGLY-0005",  # Genistein: formula C15H10O5 -> 270.05 Da, but sheet listed 226.275
                  # (matches Luteoforol's value two rows up -- likely a copy/paste error)
}

# Monoisotopic atomic masses (Da) for elements expected in flavonoid-related
# formulas. Values from CODATA / NIST standard isotope tables.
MONOISOTOPIC_MASSES = {
    "H":  1.0078250319,
    "C": 12.0000000000,
    "N": 14.0030740052,
    "O": 15.9949146221,
    "P": 30.97376151,
    "S": 31.97207069,
    "Cl": 34.96885271,
    "Na": 22.98976928,
    "K":  38.96370649,
}


def formula_to_monoisotopic_mass(formula: str) -> float:
    """
    Parse a molecular formula like 'C8H10O3' and return monoisotopic mass.

    Supports simple formulas: element symbol followed by optional integer count.
    Does NOT support nested groups, charges, or isotope notation -- formulas
    in the aglycones tab are simple neutral molecular formulas, so this is
    sufficient for this dataset.
    """
    formula = formula.strip()

    # Matches things like: C, C8, H10, O3, Cl, Na
    # Element symbol = one uppercase letter + optional lowercase letter
    # Count = optional digits (defaults to 1 if absent)
    pattern = re.compile(r'([A-Z][a-z]?)(\d*)')

    total_mass = 0.0
    matched_any = False

    for element, count_str in pattern.findall(formula):
        if not element:
            continue

        if element not in MONOISOTOPIC_MASSES:
            raise ValueError(
                f"Unknown element '{element}' in formula '{formula}' -- "
                f"add it to MONOISOTOPIC_MASSES before proceeding."
            )

        count = int(count_str) if count_str else 1
        total_mass += MONOISOTOPIC_MASSES[element] * count
        matched_any = True

    if not matched_any:
        raise ValueError(f"Could not parse formula: '{formula}'")

    return round(total_mass, 6)


def self_test():
    """
    Validate the calculator against known-correct monoisotopic masses
    already present in the live DB (HMDB/ChEBI), before trusting it
    to fix anything.
    """
    known_good = [
        ("C8H10O3",  154.062994),   # Hydroxytyrosol, confirmed via HMDB0005784
        ("C6H12O6",  180.063388),   # Glucose, standard reference value
        ("C15H10O6", 286.047738),   # Kaempferol, standard reference value
        ("C9H6O3",   162.031694),   # Umbelliferone/4-Hydroxycoumarin
    ]

    print("Running self-test against known monoisotopic masses...")
    all_passed = True

    for formula, expected in known_good:
        calculated = formula_to_monoisotopic_mass(formula)
        diff = abs(calculated - expected)
        status = "PASS" if diff < 0.001 else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] {formula}: calculated={calculated}, expected={expected}, diff={diff:.6f}")

    if not all_passed:
        raise RuntimeError("Self-test failed -- do not proceed until calculator is verified correct.")

    print("Self-test passed. Calculator is reliable.\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                         help="Preview diffs without writing to DB")
    args = parser.parse_args()

    self_test()

    if not Path(DB_FILE).exists():
        raise FileNotFoundError(f"Database not found at {DB_FILE}")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT id, source_id, name, formula, exact_mass FROM compounds "
        "WHERE source_database = 'Aglycones' ORDER BY id"
    ).fetchall()

    print(f"Found {len(rows)} rows with source_database = 'Aglycones'\n")

    updates = []
    errors = []
    skipped_flagged = []

    for row in rows:
        if row["source_id"] in SKIP_SOURCE_IDS:
            skipped_flagged.append({"source_id": row["source_id"], "name": row["name"],
                                     "formula": row["formula"], "old_mass": row["exact_mass"]})
            continue

        try:
            new_mass = formula_to_monoisotopic_mass(row["formula"])
            old_mass = row["exact_mass"]
            delta = round(new_mass - old_mass, 4) if old_mass is not None else None

            updates.append({
                "id": row["id"],
                "source_id": row["source_id"],
                "name": row["name"],
                "formula": row["formula"],
                "old_mass": old_mass,
                "new_mass": new_mass,
                "delta": delta,
            })
        except ValueError as e:
            errors.append({"source_id": row["source_id"], "name": row["name"],
                            "formula": row["formula"], "error": str(e)})

    # Print full diff table for review
    print(f"{'source_id':<12} {'name':<30} {'formula':<15} {'old_mass':>12} {'new_mass':>12} {'delta':>10}")
    print("-" * 95)
    for u in updates:
        print(f"{u['source_id']:<12} {u['name'][:30]:<30} {u['formula']:<15} "
              f"{u['old_mass']:>12} {u['new_mass']:>12} {u['delta']:>10}")

    if errors:
        print(f"\n{len(errors)} rows could not be parsed (skipped, NOT updated):")
        for e in errors:
            print(f"  {e['source_id']} | {e['name']} | formula='{e['formula']}' | {e['error']}")

    if skipped_flagged:
        print(f"\n{len(skipped_flagged)} rows flagged and SKIPPED pending manual review (not touched):")
        for s in skipped_flagged:
            print(f"  {s['source_id']} | {s['name']} | formula='{s['formula']}' | current_mass={s['old_mass']}")

    print(f"\n{len(updates)} rows would be updated, {len(errors)} rows skipped due to parse errors, "
          f"{len(skipped_flagged)} rows flagged and skipped pending review.")

    if args.dry_run:
        print("\nDRY RUN - no changes written.")
        conn.close()
        return

    # Apply updates, scoped strictly by id (and double-checked source_database)
    cur = conn.cursor()
    for u in updates:
        cur.execute(
            "UPDATE compounds SET exact_mass = ? WHERE id = ? AND source_database = 'Aglycones'",
            (u["new_mass"], u["id"])
        )

    conn.commit()
    print(f"\nApplied {len(updates)} mass corrections to source_database = 'Aglycones'.")
    conn.close()


if __name__ == "__main__":
    main()