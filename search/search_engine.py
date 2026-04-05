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
        MS2 pattern analysis with structural annotation.

        Core insight: for glycoside ladders, the parent compound often isn't
        in the DB. Instead we:
          1. Detect the neutral loss ladder pattern across all fragment pairs.
          2. Identify the dominant loss type (hexose, deoxyhexose, etc.)
             and count how many rungs the ladder has.
          3. Search the SMALLEST fragment as a candidate aglycone (with adduct
             correction — it's an [M+H]+ ion like any other).
          4. Score DB candidates by direct fragment hits only.
          5. Return a ladder_annotation block describing the predicted
             compound class even if the exact molecule isn't in the DB.
        """
        fragments = sorted(set(round(float(m), 6) for m in fragment_masses if float(m) > 0))
        if not fragments:
            return {
                "candidates": [],
                "neutral_losses": [],
                "fragment_results": [],
                "n_fragments": 0,
                "ladder_annotation": None,
            }

        n_fragments = len(fragments)

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
                            "loss_mass": loss_mass,
                            "ppm_error": round(abs(diff - loss_mass) / loss_mass * 1e6, 2),
                        })

        seen = set()
        unique_losses = []
        for l in detected_losses:
            k = (l["from_mass"], l["to_mass"], l["loss_name"])
            if k not in seen:
                seen.add(k)
                unique_losses.append(l)

        # ── Step 2: build the ladder annotation ───────────────────────────────
        # Find the dominant sequential loss (consecutive fragment pairs only)
        # A "sequential" loss connects two adjacent fragments in the sorted list
        frag_list = sorted(fragments)
        sequential_losses = []
        for i in range(len(frag_list) - 1):
            lo = frag_list[i]
            hi = frag_list[i + 1]
            diff = hi - lo
            best_match = None
            best_err = float("inf")
            for loss_mass, loss_name in self.NEUTRAL_LOSSES.items():
                err = abs(diff - loss_mass)
                if err <= self.NEUTRAL_LOSS_TOLERANCE and err < best_err:
                    best_err = err
                    best_match = (loss_mass, loss_name, round(diff, 4),
                                  round(err / loss_mass * 1e6, 2))
            if best_match:
                sequential_losses.append({
                    "from_mass": round(hi, 6),
                    "to_mass":   round(lo, 6),
                    "loss_mass": best_match[0],
                    "loss_name": best_match[1],
                    "loss_da":   best_match[2],
                    "ppm_error": best_match[3],
                })

        # Count dominant loss type among sequential losses
        loss_counts = {}
        for sl in sequential_losses:
            key = sl["loss_name"]
            loss_counts[key] = loss_counts.get(key, 0) + 1

        dominant_loss = max(loss_counts, key=loss_counts.get) if loss_counts else None
        dominant_count = loss_counts.get(dominant_loss, 0) if dominant_loss else 0

        # Search smallest fragment as aglycone candidate
        aglycone_frag = frag_list[0]
        aglycone_hits = self.search_by_mass(
            target_mass=aglycone_frag,
            tolerance=tolerance,
            adduct_delta=adduct_delta,
            source_filter=source_filter,
            max_results=10,
        )

        # Best aglycone match
        source_priority = {"HMDB": 0, "ChEBI": 1, "LipidMaps": 2, "NPAtlas": 3}
        best_aglycone = min(aglycone_hits,
                            key=lambda h: source_priority.get(h["source"], 99)) if aglycone_hits else None
        # Predicted neutral mass of parent = largest fragment - adduct
        largest_frag = frag_list[-1]
        predicted_parent_neutral = round(largest_frag - adduct_delta, 4)

        # Build human-readable structural prediction
        if best_aglycone and dominant_loss and dominant_count >= 2:
            sugar_count = dominant_count  # number of sequential losses = number of sugars
            # Map loss name to short sugar label
            sugar_label_map = {
                "hexose loss (−C6H10O5)": "hexose",
                "deoxyhexose loss": "deoxyhexose",
                "pentose loss": "pentose",
                "glucuronic acid loss": "glucuronic acid",
                "dihexose loss": "dihexose",
            }
            sugar_label = sugar_label_map.get(dominant_loss, dominant_loss.replace(" loss", ""))
            prediction = (
                f"{best_aglycone['name']} + {sugar_count}× {sugar_label}"
            )
            confidence = "high" if dominant_count >= 3 else "moderate"
        elif best_aglycone:
            prediction = f"{best_aglycone['name']} glycoside (sugar type unclear)"
            confidence = "low"
        else:
            prediction = "Unknown — aglycone not found in database"
            confidence = "none"

        ladder_annotation = {
            "predicted_structure":      prediction,
            "confidence":               confidence,
            "aglycone_mass":            round(aglycone_frag, 4),
            "aglycone_name":            best_aglycone["name"] if best_aglycone else None,
            "aglycone_formula":         best_aglycone.get("formula") if best_aglycone else None,
            "aglycone_ppm":             best_aglycone["ppm_error"] if best_aglycone else None,
            "aglycone_source":          best_aglycone["source"] if best_aglycone else None,
            "aglycone_source_id":       best_aglycone["source_id"] if best_aglycone else None,
            "dominant_loss":            dominant_loss,
            "dominant_loss_count":      dominant_count,
            "sequential_losses":        sequential_losses,
            "predicted_parent_neutral": predicted_parent_neutral,
            "ladder_length":            len(frag_list),
        }

        # ── Step 3: search all fragments for DB candidates ────────────────────
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

        # ── Step 4: score by direct hits only ─────────────────────────────────
        scored = []

        for key, cand in candidate_map.items():
            db_mass = cand["db_mass"]
            expected_ion = db_mass + adduct_delta

            direct_matches = set()
            for frag in fragments:
                if abs(frag - expected_ion) <= tolerance:
                    direct_matches.add(frag)

            n_explained = len(direct_matches)
            coverage_pct = round(n_explained / n_fragments * 100, 1)

            fragment_matches = []
            for f in sorted(direct_matches, reverse=True):
                fragment_matches.append({
                    "fragment_mass": f,
                    "ppm_error":     cand["seed_ppm"],
                    "mass_error":    cand["seed_mass_err"],
                    "matched_mass":  db_mass,
                    "match_type":    "direct",
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
                    [f for f in fragments if f not in direct_matches], reverse=True
                ),
            })

        scored.sort(key=lambda x: (-x["fragments_explained"], x["avg_ppm"]))

        return {
            "n_fragments":        n_fragments,
            "fragment_results":   fragment_results,
            "candidates":         scored[:max_candidates],
            "neutral_losses":     unique_losses,
            "ladder_annotation":  ladder_annotation,
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