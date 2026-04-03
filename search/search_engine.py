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
            162.0528: "hexose",
            146.0579: "deoxyhexose",
            132.0423: "pentose",
            176.0477: "glucuronic acid",
            308.1107: "hexose+deoxyhexose",
            324.1056: "dihexose",
            294.0634: "dihexose (alt)",
            # Acyl / ester losses
            120.0211: "caffeic acid",
            178.0528: "caffeoyl",
            164.0477: "coumaroyl",
            150.0685: "feruloyl",
            # Aglycone / ring losses
            302.0426: "quercetin aglycone",
            286.0477: "kaempferol aglycone",
            316.0583: "isorhamnetin aglycone",
            330.0532: "myricetin aglycone",
            300.0270: "delphinidin aglycone",
            270.0528: "apigenin aglycone",
            272.0685: "naringenin aglycone",
            # Small molecules
            18.0106: "water",
            28.0101: "CO",
            44.0262: "CO2",
            42.0106: "acetyl",
            80.0262: "sulfate (SO3)",
            98.0368: "phosphate (H3PO4)",
            14.0157: "methyl (CH2)",
        }

        NEUTRAL_LOSS_TOLERANCE = 0.02  # Da — tighter than mass search since we're comparing differences

        def search_ms2(
                self,
                fragment_masses: list,
                adduct_delta: float = 1.007276,
                tolerance: float = 0.02,
                source_filter=None,
                max_candidates: int = 20,
                top_n_per_fragment: int = 30,
        ) -> dict:
            """
            MS2 pattern analysis across a list of fragment masses.

            Steps:
              1. Search each fragment against the DB (reuses search_by_mass).
              2. Compute all pairwise mass differences between fragments.
              3. Match differences to the neutral loss table.
              4. For each candidate compound found in any fragment search:
                   - score = number of input fragments it explains (primary)
                   - avg_ppm = average ppm error across matched fragments (tiebreaker)
              5. Return ranked candidates + detected neutral loss ladder.
            """
            fragments = sorted(set(round(float(m), 6) for m in fragment_masses if float(m) > 0))
            if not fragments:
                return {"candidates": [], "neutral_losses": [], "fragments": []}

            # ── Step 1: search every fragment ─────────────────────────────────────
            # key: (source, source_id, name) → list of (fragment_mass, ppm_error, mass_error)
            candidate_map: dict[tuple, list] = {}

            fragment_results: dict[float, list] = {}  # frag mass → raw DB hits
            for frag in fragments:
                hits = self.search_by_mass(
                    target_mass=frag,
                    tolerance=tolerance,
                    adduct_delta=adduct_delta,
                    source_filter=source_filter,
                    max_results=top_n_per_fragment,
                )
                fragment_results[frag] = hits
                for h in hits:
                    key = (h["source"], h["source_id"], h["name"], h.get("formula", ""))
                    if key not in candidate_map:
                        candidate_map[key] = []
                    candidate_map[key].append({
                        "fragment_mass": frag,
                        "ppm_error": h["ppm_error"],
                        "mass_error": h["mass_error"],
                        "neutral_mass": h["neutral_mass"],
                    })

            # ── Step 2 & 3: pairwise mass differences → neutral losses ─────────────
            detected_losses = []
            for i, f1 in enumerate(fragments):
                for f2 in fragments[i + 1:]:
                    diff = abs(f2 - f1)
                    for loss_mass, loss_name in self.NEUTRAL_LOSSES.items():
                        if abs(diff - loss_mass) <= self.NEUTRAL_LOSS_TOLERANCE:
                            detected_losses.append({
                                "from_mass": round(f2, 6),  # larger fragment
                                "to_mass": round(f1, 6),  # smaller fragment
                                "delta": round(diff, 4),
                                "loss_name": loss_name,
                                "loss_mass": loss_mass,
                                "ppm_error": round(abs(diff - loss_mass) / loss_mass * 1e6, 2),
                            })

            # Deduplicate losses (same loss_name between same pair)
            seen_loss_keys = set()
            unique_losses = []
            for l in detected_losses:
                k = (l["from_mass"], l["to_mass"], l["loss_name"])
                if k not in seen_loss_keys:
                    seen_loss_keys.add(k)
                    unique_losses.append(l)

            # ── Step 4: score each candidate ──────────────────────────────────────
            scored = []
            n_fragments = len(fragments)

            for (source, source_id, name, formula), matches in candidate_map.items():
                # one match per input fragment (deduplicate if same compound matched same frag twice)
                frags_explained = {m["fragment_mass"] for m in matches}
                n_explained = len(frags_explained)
                avg_ppm = round(
                    sum(m["ppm_error"] for m in matches) / len(matches), 3
                )
                best_per_frag = {}
                for m in matches:
                    f = m["fragment_mass"]
                    if f not in best_per_frag or m["ppm_error"] < best_per_frag[f]["ppm_error"]:
                        best_per_frag[f] = m

                scored.append({
                    "source": source,
                    "source_id": source_id,
                    "name": name,
                    "formula": formula,
                    "n_explained": n_explained,
                    "n_fragments": n_fragments,
                    "score_pct": round(n_explained / n_fragments * 100, 1),
                    "avg_ppm": avg_ppm,
                    "fragment_matches": [
                        {
                            "fragment_mass": f,
                            "ppm_error": d["ppm_error"],
                            "mass_error": d["mass_error"],
                            "neutral_mass": d["neutral_mass"],
                        }
                        for f, d in sorted(best_per_frag.items(), reverse=True)
                    ],
                    # which input fragments this candidate does NOT explain
                    "unmatched_fragments": sorted(
                        [f for f in fragments if f not in frags_explained], reverse=True
                    ),
                })

            # ── Step 5: rank ──────────────────────────────────────────────────────
            scored.sort(key=lambda x: (-x["n_explained"], x["avg_ppm"]))

            return {
                "fragments": fragments,
                "candidates": scored[:max_candidates],
                "neutral_losses": unique_losses,
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