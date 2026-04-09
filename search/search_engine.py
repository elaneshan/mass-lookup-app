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

        if adduct_delta is not None:
            neutral_mass = target_mass - adduct_delta
        else:
            neutral_mass = target_mass - ION_ADJUSTMENTS.get(ion_mode, 0.0)
        lower = neutral_mass - tolerance
        upper = neutral_mass + tolerance

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
        for r in rows[:3]:
            print("DEBUG SQL:", dict(r))

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
            'ppm_error':     row['ppm_error'],
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
                    'ppm_error':     row['ppm_error'],
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

    # ── Neutral loss library (from PI's flavonoid reference table) ────────────
    # Classification: "Hexose", "Deoxyhexose", "Pentose", "Hexose Disaccharide",
    #                 "Hexose Deoxyhexose", "Acyl Hexose", "Acyl Deoxyhexose", "Acyl Moiety"
    NEUTRAL_LOSSES = {
        # Sugars
        162.0528: ("hexose",                  "Hexose"),
        146.0579: ("rhamnoside",              "Deoxyhexose"),
        132.0422: ("pentose",                 "Pentose"),
        324.1056: ("sophoroside",             "Hexose Disaccharide"),
        308.1107: ("rutinoside",              "Hexose Deoxyhexose"),
        # Acylated sugars
        204.0634: ("acetyl glucoside",        "Acyl Hexose"),
        188.0684: ("acetyl rhamnoside",       "Acyl Deoxyhexose"),
        308.0896: ("coumaroyl glucoside",     "Acyl Hexose"),
        292.0947: ("coumaroyl rhamnoside",    "Acyl Deoxyhexose"),
        246.0739: ("diacetyl glucoside",      "Acyl Hexose"),
        324.0845: ("caffeoyl hexose",         "Acyl Hexose"),
        # Acyl moieties
        42.0105:  ("acetyl",                  "Acyl Moiety"),
        102.0105: ("benzoyl",                 "Acyl Moiety"),
        162.0317: ("caffeoyl",                "Acyl Moiety"),
        130.0418: ("cinnamyl",                "Acyl Moiety"),
        146.0368: ("coumaroyl",               "Acyl Moiety"),
        176.0473: ("feruloyl",                "Acyl Moiety"),
        152.0109: ("galloyl",                 "Acyl Moiety"),
        86.0368:  ("hydroxyisobutyryl",       "Acyl Moiety"),
        86.0003:  ("malonyl",                 "Acyl Moiety"),
        166.0993: ("menthiafoloyl",           "Acyl Moiety"),
        160.0524: ("methoxycinnamyl",         "Acyl Moiety"),
        84.0575:  ("methylbutyryl/pentanoyl", "Acyl Moiety"),
        166.0266: ("methylgalloyl",           "Acyl Moiety"),
        128.0473: ("methylglutaryl",          "Acyl Moiety"),
        71.9847:  ("oxalyl",                  "Acyl Moiety"),
        206.0579: ("sinapoyl",                "Acyl Moiety"),
        150.0317: ("vanilloyl",               "Acyl Moiety"),
    }

    NEUTRAL_LOSS_TOLERANCE = 0.02  # Da

    # ── Flavonoid aglycone reference table (from PI) ──────────────────────────
    # Each entry: name → {classification, positive_ion, negative_ion}
    # positive_ion: observed m/z in positive mode ([M]+ for anthocyanins, [M+H]+ for flavonols)
    # negative_ion: observed m/z in negative mode ([M-H]-)
    FLAVONOID_AGLYCONES = [
        # Anthocyanins — exist as flavylium cations [M]+
        {"name": "pelargonidin",        "class": "anthocyanin", "positive_mz": 271.0601, "negative_mz": 269.0455},
        {"name": "cyanidin",            "class": "anthocyanin", "positive_mz": 287.0550, "negative_mz": 285.0405},
        {"name": "delphinidin",         "class": "anthocyanin", "positive_mz": 303.0499, "negative_mz": 301.0354},
        {"name": "peonidin",            "class": "anthocyanin", "positive_mz": 301.0707, "negative_mz": 299.0561},
        {"name": "petunidin",           "class": "anthocyanin", "positive_mz": 317.0656, "negative_mz": 315.0510},
        {"name": "malvidin",            "class": "anthocyanin", "positive_mz": 331.0812, "negative_mz": 329.0667},
        # Flavonols — detected as [M+H]+ in positive, [M-H]- in negative
        {"name": "kaempferol",          "class": "flavonol",    "positive_mz": 287.0550, "negative_mz": 285.0405},
        {"name": "quercetin",           "class": "flavonol",    "positive_mz": 303.0499, "negative_mz": 301.0354},
        {"name": "myricetin",           "class": "flavonol",    "positive_mz": 319.0448, "negative_mz": 317.0303},
        {"name": "isorhamnetin",        "class": "flavonol",    "positive_mz": 317.0656, "negative_mz": 315.0510},
    ]

    AGLYCONE_TOLERANCE = 0.02  # Da for aglycone matching

    # Source priority for DB fallback
    SOURCE_PRIORITY = {"HMDB": 0, "ChEBI": 1, "LipidMaps": 2, "NPAtlas": 3}

    def _match_aglycone(self, observed_mz: float, adduct: str) -> list:
        """
        Match observed smallest fragment against flavonoid aglycone table,
        with adduct-class compatibility filtering.
        """
        print("🔥 ENTERING _match_aglycone", observed_mz, adduct)
        # ── Determine ion mode key ─────────────────────────────
        is_negative = adduct in ("[M-H]-", "[M+Cl]-", "[M+FA-H]-", "[M-2H]-", "[M-2H]2-")
        mz_key = "negative_mz" if is_negative else "positive_mz"

        # ── Allowed class by adduct ────────────────────────────
        def is_valid_class(ag_class: str) -> bool:
            if adduct in ("[M]+",):
                return ag_class == "anthocyanin"

            if adduct in ("[M+H]+", "[M+Na]+", "[M+K]+", "[M+NH4]+"):
                return ag_class == "flavonol"

            if adduct in ("[M-H]-", "[M+Cl]-", "[M+FA-H]-"):
                return ag_class == "flavonol"

            if adduct in ("[M-2H]-", "[M-2H]2-"):
                return ag_class == "anthocyanin"

            return True  # fallback (shouldn't happen)

        # ── Matching ───────────────────────────────────────────
        matches = []

        for ag in self.FLAVONOID_AGLYCONES:
            if not is_valid_class(ag["class"]):
                continue  # 🔥 THIS IS THE KEY LINE

            ref_mz = ag[mz_key]
            if ref_mz is None:
                continue

            err = abs(observed_mz - ref_mz)
            if err <= self.AGLYCONE_TOLERANCE:
                ppm = err / ref_mz * 1e6
                print("DEBUG AG:", {
                    "observed": observed_mz,
                    "ref": ref_mz,
                    "err": err,
                    "ppm": ppm
                })

                matches.append({
                    **ag,
                    "ppm_error": ppm,
                    "observed_mz": observed_mz
                })

        matches.sort(key=lambda x: x["ppm_error"])
        return matches

    def search_ms2(
        self,
        fragment_masses: list,
        adduct_delta: float = 1.007276,
        tolerance: float = 0.02,
        source_filter=None,
        max_candidates: int = 20,
        top_n_per_fragment: int = 50,
        adduct: str = "[M+H]+",
    ) -> dict:
        """
        MS2 pattern analysis optimized for flavonoid glycosides.

        1. Detect all pairwise neutral losses using PI's flavonoid loss library.
        2. Find sequential losses between adjacent fragments.
        3. Match smallest fragment against flavonoid aglycone table (positive + negative mode).
        4. Build mixed-composition sugar annotation (e.g. 3× hexose + 1× caffeoyl).
        5. Search DB for supporting candidates.
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

        # ── Step 1: detect all pairwise neutral losses ─────────────────────────
        detected_losses = []
        for i, f1 in enumerate(fragments):
            for f2 in fragments[i + 1:]:
                diff = abs(f2 - f1)
                for loss_mass, (loss_name, loss_class) in self.NEUTRAL_LOSSES.items():
                    if abs(diff - loss_mass) <= self.NEUTRAL_LOSS_TOLERANCE:
                        detected_losses.append({
                            "from_mass":  round(max(f1, f2), 6),
                            "to_mass":    round(min(f1, f2), 6),
                            "loss_da":    round(diff, 4),
                            "loss_name":  loss_name,
                            "loss_class": loss_class,
                            "ppm_error":  round(abs(diff - loss_mass) / loss_mass * 1e6, 2),
                        })

        seen = set()
        unique_losses = []
        for l in detected_losses:
            k = (l["from_mass"], l["to_mass"], l["loss_name"])
            if k not in seen:
                seen.add(k)
                unique_losses.append(l)

        # ── Step 2: sequential losses between adjacent fragments ───────────────
        frag_list = sorted(fragments)
        sequential_losses = []
        for i in range(len(frag_list) - 1):
            lo, hi = frag_list[i], frag_list[i + 1]
            diff = hi - lo
            best_match = None
            best_err = float("inf")
            for loss_mass, (loss_name, loss_class) in self.NEUTRAL_LOSSES.items():
                err = abs(diff - loss_mass)
                if err <= self.NEUTRAL_LOSS_TOLERANCE and err < best_err:
                    best_err = err
                    best_match = (loss_mass, loss_name, loss_class,
                                  round(diff, 4), round(err / loss_mass * 1e6, 2))
            if best_match:
                sequential_losses.append({
                    "from_mass":  round(hi, 6),
                    "to_mass":    round(lo, 6),
                    "loss_mass":  best_match[0],
                    "loss_name":  best_match[1],
                    "loss_class": best_match[2],
                    "loss_da":    best_match[3],
                    "ppm_error":  best_match[4],
                })

        # ── Step 3: mixed sugar composition ───────────────────────────────────
        # Count each loss class separately for full composition description
        loss_class_counts = {}
        loss_name_counts  = {}
        for sl in sequential_losses:
            cls  = sl["loss_class"]
            name = sl["loss_name"]
            loss_class_counts[cls]  = loss_class_counts.get(cls, 0) + 1
            loss_name_counts[name]  = loss_name_counts.get(name, 0) + 1

        # Build composition string e.g. "3× hexose + 1× caffeoyl + 1× rhamnoside"
        # Group by name for specificity, sorted by count descending
        composition_parts = []
        for name, count in sorted(loss_name_counts.items(), key=lambda x: -x[1]):
            composition_parts.append(f"{count}× {name}")
        composition_str = " + ".join(composition_parts) if composition_parts else "unknown sugars"

        # Dominant class for summary
        dominant_class = max(loss_class_counts, key=loss_class_counts.get) if loss_class_counts else None
        total_losses   = len(sequential_losses)

        # ── Step 4: aglycone matching ──────────────────────────────────────────
        aglycone_frag    = frag_list[0]
        aglycone_matches = self._match_aglycone(aglycone_frag, adduct)

        # Group by ppm — isobars share the same ppm
        best_ppm          = aglycone_matches[0]["ppm_error"] if aglycone_matches else None
        isobar_threshold  = 0.5  # ppm difference threshold to call isobars
        isobars           = [m for m in aglycone_matches
                             if best_ppm is not None and abs(m["ppm_error"] - best_ppm) <= isobar_threshold]
        non_isobars       = [m for m in aglycone_matches
                             if m not in isobars]

        best_aglycone     = isobars[0] if isobars else None
        aglycone_ambiguous = len(isobars) > 1

        # Classes present among isobars
        isobar_classes    = list({m["class"] for m in isobars})
        isobar_names      = [m["name"] for m in isobars]

        # If isobars span both anthocyanin and flavonol, note that
        has_anthocyanin   = any(m["class"] == "anthocyanin" for m in isobars)
        has_flavonol      = any(m["class"] == "flavonol" for m in isobars)

        # Fallback to DB if no aglycone table match
        if not best_aglycone:
            db_hits = self.search_by_mass(
                target_mass=aglycone_frag,
                tolerance=tolerance,
                adduct_delta=adduct_delta,
                source_filter=source_filter,
                max_results=100,
            )
            best_db = min(
                db_hits,
                key=lambda h: (self.SOURCE_PRIORITY.get(h["source"], 99), h["ppm_error"])
            ) if db_hits else None
        else:
            best_db = None

        predicted_parent_neutral = round(frag_list[-1] - adduct_delta, 4)

        # ── Build prediction string ────────────────────────────────────────────
        if best_aglycone and composition_parts:
            aglycone_label = "/".join(isobar_names) if aglycone_ambiguous else best_aglycone["name"]
            prediction     = f"{aglycone_label} + {composition_str}"
            confidence     = "high" if total_losses >= 3 and not aglycone_ambiguous else "moderate"
        elif best_aglycone:
            aglycone_label = "/".join(isobar_names) if aglycone_ambiguous else best_aglycone["name"]
            prediction     = f"{aglycone_label} glycoside (sugar composition unclear)"
            confidence     = "low"
        elif best_db and composition_parts:
            prediction     = f"{best_db['name']} + {composition_str}"
            confidence     = "low"
        else:
            prediction     = "Unknown — aglycone not matched to flavonoid library"
            confidence     = "none"

        ladder_annotation = {
            "predicted_structure": prediction,
            "confidence": confidence,

            # Aglycone info
            "aglycone_mass": round(aglycone_frag, 4),
            "aglycone_matches": isobars,
            "aglycone_name": "/".join(isobar_names) if isobars else (best_db["name"] if best_db else None),
            "aglycone_formula": None,  # FIXED
            "aglycone_ppm": best_ppm,
            "aglycone_ambiguous": aglycone_ambiguous,
            "aglycone_isobar_names": isobar_names,
            "aglycone_classes": isobar_classes,
            "has_anthocyanin": has_anthocyanin,
            "has_flavonol": has_flavonol,

            # (fix for frontend expectation)
            "aglycone_source": None,
            "aglycone_source_id": None,

            # Sugar composition
            "composition_str": composition_str,
            "composition_parts": composition_parts,
            "loss_class_counts": loss_class_counts,
            "loss_name_counts": loss_name_counts,
            "sequential_losses": sequential_losses,
            "total_sequential_losses": total_losses,
            "dominant_loss_class": dominant_class,

            # Parent mass
            "predicted_parent_neutral": predicted_parent_neutral,
            "ladder_length": len(frag_list),
        }

        # ── Step 5: search DB for supporting candidates ────────────────────────
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

        scored = []
        for key, cand in candidate_map.items():
            db_mass      = cand["db_mass"]
            expected_ion = db_mass + adduct_delta
            direct_matches = set()
            for frag in fragments:
                if abs(frag - expected_ion) <= tolerance:
                    direct_matches.add(frag)

            n_explained  = len(direct_matches)
            coverage_pct = round(n_explained / n_fragments * 100, 1)

            scored.append({
                "source":              cand["source"],
                "source_id":           cand["source_id"],
                "name":                cand["name"],
                "formula":             cand["formula"],
                "fragments_explained": n_explained,
                "coverage_pct":        coverage_pct,
                "avg_ppm":             cand["seed_ppm"],
                "fragment_matches": [
                    {
                        "fragment_mass": f,
                        "ppm_error":     cand["seed_ppm"],
                        "mass_error":    cand["seed_mass_err"],
                        "matched_mass":  db_mass,
                        "match_type":    "direct",
                    }
                    for f in sorted(direct_matches, reverse=True)
                ],
                "unmatched_fragments": sorted(
                    [f for f in fragments if f not in direct_matches], reverse=True
                ),
            })

        scored.sort(key=lambda x: (-x["fragments_explained"], x["avg_ppm"]))

        return {
            "n_fragments":       n_fragments,
            "fragment_results":  fragment_results,
            "candidates":        scored[:max_candidates],
            "neutral_losses":    unique_losses,
            "ladder_annotation": ladder_annotation,
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