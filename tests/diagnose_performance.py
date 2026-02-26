"""
Performance diagnostic — run this to identify where the slowness is.
Usage: python scripts/diagnose_performance.py
"""
import sqlite3
import time
import sys
sys.path.insert(0, '.')

DB_FILE = "database/compounds.db"

def bench(label, fn, n=10):
    start = time.time()
    for _ in range(n):
        fn()
    elapsed = (time.time() - start) / n * 1000
    print(f"  {label:<40} {elapsed:6.1f} ms/query")

print("=" * 60)
print("Performance Diagnostic")
print("=" * 60)

conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Raw SQLite speed
print("\n1. Raw SQLite queries:")
bench("mass search ±0.5 Da",
      lambda: cur.execute(
          "SELECT * FROM compounds WHERE exact_mass BETWEEN ? AND ? LIMIT 20",
          [180.5, 181.5]).fetchall())

bench("mass search ±0.02 Da",
      lambda: cur.execute(
          "SELECT * FROM compounds WHERE exact_mass BETWEEN ? AND ? LIMIT 20",
          [181.05, 181.09]).fetchall())

bench("formula search C6H12O6",
      lambda: cur.execute(
          "SELECT * FROM compounds WHERE UPPER(formula)=? LIMIT 100",
          ["C6H12O6"]).fetchall())

# 2. Check indices exist
print("\n2. Index check:")
for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'"):
    print(f"  ✓ {row[0]}")

# 3. Row counts
print("\n3. Row counts:")
for row in conn.execute("SELECT source_database, COUNT(*) FROM compounds GROUP BY source_database"):
    print(f"  {row[0]:<12} {row[1]:>10,}")

# 4. SearchEngine overhead
print("\n4. SearchEngine overhead:")
from search.search_engine import SearchEngine
se = SearchEngine()
bench("search_by_mass (positive)",
      lambda: se.search_by_mass(181.071, tolerance=0.02, ion_mode='positive'))
bench("search_by_mass (±0.5 Da wide)",
      lambda: se.search_by_mass(181.071, tolerance=0.5,  ion_mode='positive'))
bench("search_by_formula C6H12O6",
      lambda: se.search_by_formula('C6H12O6'))

conn.close()
print("\n" + "=" * 60)
print("If raw SQLite < 10ms but SearchEngine > 50ms → overhead is in Python layer")
print("If raw SQLite > 20ms → need to optimize indices or query")