"""
Mass Search Engine v4
=====================

Performance fixes:
- Persistent SQLite connection (no reconnect per query)
- Formula stored and queried pre-normalized → idx_formula index actually used
- WAL mode for better read concurrency
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Literal

DB_FILE = "database/compounds.db"

ION_ADJUSTMENTS = {
    'positive':  1.007276,
    'negative': -1.007276,
    'neutral':   0.0,
}


def normalize_formula(formula: str) -> str:
    if not formula:
        return ''
    return formula.strip().upper().replace(' ', '')


class SearchEngine:

    def __init__(self, db_path: str = DB_FILE):
        if not Path(db_path).exists():
            raise FileNotFoundError(
                f"Database not found at: {db_path}\n"
                f"Please run: python scripts/build_database_v5.py"
            )
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=-64000")
        self.conn.execute("PRAGMA temp_store=MEMORY")

    # ─────────────────────────────────────────────
    # MASS SEARCH
    # ─────────────────────────────────────────────

    def search_by_mass(
        self,
        target_mass: float,
        tolerance: float = 0.5,
        ion_mode: Literal['positive', 'negative', 'neutral'] = 'neutral',
        source_filter: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        adduct_delta: Optional[float] = None,
    ) -> List[Dict]:

        # Use exact adduct delta if provided, otherwise fall back to generic ion mode offset
        if adduct_delta is not None:
            neutral_mass = target_mass - adduct_delta
        else:
            neutral_mass = target_mass - ION_ADJUSTMENTS.get(ion_mode, 0.0)
        lower        = neutral_mass - tolerance
        upper        = neutral_mass + tolerance

        query = '''
            SELECT source_database, source_id, name, formula,
                   exact_mass, cas, inchikey,
                   ABS(exact_mass - ?)             AS mass_error,
                   ABS((exact_mass - ?) / ? * 1e6) AS ppm_error
            FROM compounds
            WHERE exact_mass BETWEEN ? AND ?
        '''
        params = [neutral_mass, neutral_mass, neutral_mass, lower, upper]

        if source_filter:
            query += f' AND source_database IN ({",".join("?"*len(source_filter))})'
            params.extend(source_filter)

        query += ' ORDER BY mass_error ASC'
        if max_results:
            query += f' LIMIT {int(max_results)}'

        rows = self.conn.execute(query, params).fetchall()

        return [{
            'source':        row['source_database'],
            'source_id':     row['source_id'],
            'name':          row['name'],
            'formula':       row['formula'] or 'N/A',
            'cas':           row['cas'] or '',
            'inchikey':      row['inchikey'] or '',
            'neutral_mass':  round(row['exact_mass'], 6),
            'observed_mass': round(target_mass, 6),
            'mass_error':    round(row['mass_error'], 6),
            'ppm_error':     round(row['ppm_error'], 3),
            'ion_mode':      ion_mode,
        } for row in rows]

    # ─────────────────────────────────────────────
    # BATCH MASS SEARCH
    # ─────────────────────────────────────────────

    def search_batch_masses(
        self,
        mass_adduct_pairs: List[tuple],
        tolerance: float = 0.5,
        source_filter: Optional[List[str]] = None,
        max_results_per_query: int = 20
    ) -> List[Dict]:

        all_results = []

        for query_id, (observed_mass, adduct_delta, adduct_label) in enumerate(mass_adduct_pairs):
            # Use exact adduct delta directly
            neutral_mass = observed_mass - adduct_delta
            lower        = neutral_mass - tolerance
            upper        = neutral_mass + tolerance

            query = '''
                SELECT source_database, source_id, name, formula,
                       exact_mass, cas, inchikey,
                       ABS(exact_mass - ?)             AS mass_error,
                       ABS((exact_mass - ?) / ? * 1e6) AS ppm_error
                FROM compounds
                WHERE exact_mass BETWEEN ? AND ?
            '''
            params = [neutral_mass, neutral_mass, neutral_mass, lower, upper]

            if source_filter:
                query += f' AND source_database IN ({",".join("?"*len(source_filter))})'
                params.extend(source_filter)

            query += f' ORDER BY mass_error ASC LIMIT {int(max_results_per_query)}'

            rows = self.conn.execute(query, params).fetchall()

            for row in rows:
                all_results.append({
                    'query_id':      query_id,
                    'query_mass':    observed_mass,
                    'query_adduct':  adduct_label,
                    'adduct':        adduct_label,
                    'source':        row['source_database'],
                    'source_id':     row['source_id'],
                    'name':          row['name'],
                    'formula':       row['formula'] or 'N/A',
                    'cas':           row['cas'] or '',
                    'inchikey':      row['inchikey'] or '',
                    'neutral_mass':  round(neutral_mass, 6),
                    'observed_mass': round(observed_mass, 6),
                    'mass_error':    round(row['mass_error'], 6),
                    'ppm_error':     round(row['ppm_error'], 3),
                    'ion_mode':      'positive' if adduct_delta > 0 else
                                     'negative' if adduct_delta < 0 else 'neutral',
                })

        return all_results

    # ─────────────────────────────────────────────
    # FORMULA SEARCH
    # ─────────────────────────────────────────────

    def search_by_formula(
        self,
        formula: str,
        source_filter: Optional[List[str]] = None,
        max_results: Optional[int] = None
    ) -> List[Dict]:

        formula_norm = normalize_formula(formula)

        query = '''
            SELECT source_database, source_id, name, formula,
                   exact_mass, cas, inchikey
            FROM compounds
            WHERE formula_normalized = ?
        '''
        params = [formula_norm]

        if source_filter:
            query += f' AND source_database IN ({",".join("?"*len(source_filter))})'
            params.extend(source_filter)

        query += ' ORDER BY exact_mass ASC'
        if max_results:
            query += f' LIMIT {int(max_results)}'

        rows = self.conn.execute(query, params).fetchall()

        return [{
            'source':     row['source_database'],
            'source_id':  row['source_id'],
            'name':       row['name'],
            'formula':    row['formula'] or 'N/A',
            'cas':        row['cas'] or '',
            'inchikey':   row['inchikey'] or '',
            'exact_mass': round(row['exact_mass'], 6),
        } for row in rows]

    # ─────────────────────────────────────────────
    # NAME SEARCH
    # ─────────────────────────────────────────────

    def search_by_name(
        self,
        query: str,
        source_filter: Optional[List[str]] = None,
        max_results: int = 50
    ) -> List[Dict]:
        """
        Case-insensitive substring search on compound name.
        Returns compounds whose name contains the query string.
        """
        query_str = f'%{query.strip()}%'

        sql = '''
            SELECT source_database, source_id, name, formula,
                   exact_mass, cas, inchikey
            FROM compounds
            WHERE name LIKE ? COLLATE NOCASE
        '''
        params = [query_str]

        if source_filter:
            sql += f' AND source_database IN ({",".join("?"*len(source_filter))})'
            params.extend(source_filter)

        # Order by name length ascending so exact/short matches float to top
        sql += ' ORDER BY LENGTH(name) ASC'
        sql += f' LIMIT {int(max_results)}'

        rows = self.conn.execute(sql, params).fetchall()

        return [{
            'source':     row['source_database'],
            'source_id':  row['source_id'],
            'name':       row['name'],
            'formula':    row['formula'] or 'N/A',
            'cas':        row['cas'] or '',
            'inchikey':   row['inchikey'] or '',
            'exact_mass': round(row['exact_mass'], 6) if row['exact_mass'] else None,
        } for row in rows]

    # ─────────────────────────────────────────────
    # MS2 PATTERN ANALYSIS
    # ─────────────────────────────────────────────

    # Common neutral losses in flavonoid / anthocyanin MS2 (Da, exact monoisotopic)
    NEUTRAL_LOSSES = {
        162.0528: "hexose loss (−C6H10O5)",
        146.0579: "deoxyhexose loss",
        132.0423: "pentose loss",
        176.0477: "glucuronic acid loss",
        308.1107: "hexose+deoxyhexose loss",
        324.1056: "dihexose loss",
        294.0634: "dihexose loss (alt)",
        # Acyl / ester losses
        120.0211: "caffeic acid loss",
        178.0528: "caffeoyl loss",
        164.0477: "coumaroyl loss",
        150.0685: "feruloyl loss",
        # Aglycone / ring losses
        302.0426: "quercetin aglycone",
        286.0477: "kaempferol aglycone",
        316.0583: "isorhamnetin aglycone",
        330.0532: "myricetin aglycone",
        300.0270: "delphinidin aglycone",
        270.0528: "apigenin aglycone",
        272.0685: "naringenin aglycone",
        # Small molecules
        18.0106:  "water loss",
        28.0101:  "CO loss",
        44.0262:  "CO2 loss",
        42.0106:  "acetyl loss",
        80.0262:  "sulfate loss (SO3)",
        98.0368:  "phosphate loss (H3PO4)",
        14.0157:  "methyl loss (CH2)",
    }

    NEUTRAL_LOSS_TOLERANCE = 0.01  # Da

    def search_ms2(
        self,
        fragment_masses: list,
        adduct_delta: float = 1.007276,
        tolerance: float = 0.02,
        source_filter=None,
        max_candidates: int = 20,
        top_n_per_fragment: int = 50,
    ) -> dict:
        """
        MS2 pattern analysis — two-pass ladder-aware scoring.

        Key insight:
          - Fragment ions in a glycoside series carry a proton, so the
            SMALLEST fragment (likely the aglycone) needs adduct correction
            to find its neutral mass in the DB.
          - The LARGER fragments are sequential neutral losses — they are NOT
            stored as compounds. We explain them by walking UP the ladder
            from the aglycone match using the detected neutral losses.

        Algorithm:
          1. Detect all neutral losses between input fragment pairs.
          2. Search the smallest N fragments WITH adduct correction to find
             candidate aglycones in the DB.
          3. For each aglycone candidate, propagate coverage up the ladder:
             if fragment F is explained and F + loss_da ≈ another input
             fragment, that fragment is also explained.
          4. Also search ALL fragments with adduct correction as fallback
             (catches intact glycosides stored in the DB).
          5. Score = fragments explained / total. Rank and return.
        """
        fragments = sorted(set(round(float(m), 6) for m in fragment_masses if float(m) > 0))
        if not fragments:
            return {
                "candidates": [],
                "neutral_losses": [],
                "fragment_results": [],
                "n_fragments": 0,
            }

        n_fragments = len(fragments)
        frag_set = set(fragments)

        # ── Step 1: detect neutral losses ─────────────────────────────────────
        detected_losses = []
        for i, f1 in enumerate(fragments):
            for f2 in fragments[i + 1:]:
                diff = abs(f2 - f1)
                for loss_mass, loss_name in self.NEUTRAL_LOSSES.items():
                    if abs(diff - loss_mass) <= self.NEUTRAL_LOSS_TOLERANCE:
                        detected_losses.append({
                            "from_mass": round(max(f1, f2), 6),
                            "to_mass":   round(min(f1, f2), 6),
                            "loss_da":   round(diff, 4),
                            "loss_name": loss_name,
                            "ppm_error": round(abs(diff - loss_mass) / loss_mass * 1e6, 2),
                        })

        seen = set()
        unique_losses = []
        for l in detected_losses:
            k = (l["from_mass"], l["to_mass"], l["loss_name"])
            if k not in seen:
                seen.add(k)
                unique_losses.append(l)

        # ── Step 2: search candidates ──────────────────────────────────────────
        # Pass A: search smallest 2 fragments WITH adduct correction → finds aglycones
        # Pass B: search ALL fragments WITH adduct correction → catches intact glycosides
        # We use adduct_delta for all searches because all observed ions carry
        # the adduct (proton for [M+H]+), including fragment ions.

        candidate_map: dict[tuple, dict] = {}
        fragment_results = []

        for frag in fragments:
            hits = self.search_by_mass(
                target_mass=frag,
                tolerance=tolerance,
                adduct_delta=adduct_delta,
                source_filter=source_filter,
                max_results=top_n_per_fragment,
            )
            fragment_results.append({"mass": frag, "hits": len(hits)})
            for h in hits:
                key = (h["source"], h["source_id"], h["name"], h.get("formula", ""))
                if key not in candidate_map:
                    candidate_map[key] = {
                        "source":        h["source"],
                        "source_id":     h["source_id"],
                        "name":          h["name"],
                        "formula":       h.get("formula", ""),
                        "db_mass":       h["neutral_mass"],
                        "seed_fragment": frag,
                        "seed_ppm":      h["ppm_error"],
                        "seed_mass_err": h["mass_error"],
                    }

        # ── Step 3: score each candidate via ladder propagation ───────────────
        scored = []

        for key, cand in candidate_map.items():
            db_mass = cand["db_mass"]

            # Which input fragments directly match this compound (with adduct)?
            # observed fragment = db_mass + adduct_delta
            expected_ion = db_mass + adduct_delta
            direct_matches = set()
            for frag in fragments:
                if abs(frag - expected_ion) <= tolerance:
                    direct_matches.add(frag)

            # Propagate coverage up and down using the detected neutral loss ladder.
            # If fragment F is explained, then any fragment F' where
            # |F' - F| ≈ a known loss is also explained.
            explained = set(direct_matches)
            changed = True
            while changed:
                changed = False
                for exp_frag in list(explained):
                    for loss in unique_losses:
                        # Walk UP: exp_frag is the "to_mass", check if "from_mass" is in input
                        if abs(loss["to_mass"] - exp_frag) <= tolerance:
                            for f in fragments:
                                if abs(f - loss["from_mass"]) <= tolerance and f not in explained:
                                    explained.add(f)
                                    changed = True
                        # Walk DOWN: exp_frag is the "from_mass", check if "to_mass" is in input
                        if abs(loss["from_mass"] - exp_frag) <= tolerance:
                            for f in fragments:
                                if abs(f - loss["to_mass"]) <= tolerance and f not in explained:
                                    explained.add(f)
                                    changed = True

            n_explained = len(explained)
            coverage_pct = round(n_explained / n_fragments * 100, 1)

            # Build fragment_matches for the UI
            fragment_matches = []
            for f in sorted(explained, reverse=True):
                is_direct = f in direct_matches
                fragment_matches.append({
                    "fragment_mass": f,
                    "ppm_error":     cand["seed_ppm"] if is_direct else 0.0,
                    "mass_error":    cand["seed_mass_err"] if is_direct else 0.0,
                    "matched_mass":  db_mass,
                    "match_type":    "direct" if is_direct else "ladder",
                })

            scored.append({
                "source":              cand["source"],
                "source_id":           cand["source_id"],
                "name":                cand["name"],
                "formula":             cand["formula"],
                "fragments_explained": n_explained,
                "coverage_pct":        coverage_pct,
                "avg_ppm":             cand["seed_ppm"],
                "fragment_matches":    fragment_matches,
                "unmatched_fragments": sorted(
                    [f for f in fragments if f not in explained], reverse=True
                ),
            })

        # ── Step 4: rank ──────────────────────────────────────────────────────
        scored.sort(key=lambda x: (-x["fragments_explained"], x["avg_ppm"]))

        return {
            "n_fragments":      n_fragments,
            "fragment_results": fragment_results,
            "candidates":       scored[:max_candidates],
            "neutral_losses":   unique_losses,
        }

        # ─────────────────────────────────────────────
    # STATS
    # ─────────────────────────────────────────────

    def get_stats(self) -> Dict:
        total     = self.conn.execute('SELECT COUNT(*) FROM compounds').fetchone()[0]
        by_source = dict(self.conn.execute(
            'SELECT source_database, COUNT(*) FROM compounds GROUP BY source_database'
        ).fetchall())
        min_m, max_m = self.conn.execute(
            'SELECT MIN(exact_mass), MAX(exact_mass) FROM compounds'
        ).fetchone()

        return {
            'total_compounds': total,
            'by_source':       by_source,
            'min_mass':        round(min_m, 4) if min_m else None,
            'max_mass':        round(max_m, 4) if max_m else None,
        }

    def __del__(self):
        try:
            self.conn.close()
        except Exception:
            pass