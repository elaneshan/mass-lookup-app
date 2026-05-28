"""
API Models
==========
Pydantic schemas for request validation and response serialization.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal


# ─────────────────────────────────────────────
# RESPONSE MODELS
# ─────────────────────────────────────────────

# CompoundResult is the base identity record — every search type returns at least this.
# All fields beyond `source` are Optional because not every database populates every field
# (e.g. some sources lack a CAS number or InChIKey).
class CompoundResult(BaseModel):
    """Single compound match returned by mass or formula search."""
    source:       str                  # which database this came from (e.g. HMDB, ChEBI)
    source_id:    Optional[str]  = None  # the compound's ID within that database
    name:         Optional[str]  = None
    formula:      Optional[str]  = None
    cas:          Optional[str]  = None      # CAS registry number — widely used in chemistry
    inchikey:     Optional[str]  = None      # standardized structural hash — useful for deduplication across DBs
    exact_mass:   Optional[float] = None     # theoretical monoisotopic mass of the neutral molecule


# MassResult inherits everything from CompoundResult and adds the error fields
# that only make sense in an m/z search context — how far off was our match?
class MassResult(CompoundResult):
    """Mass search result — includes error fields."""
    observed_mass: float   # the raw m/z value the user queried
    mass_error:    float   # absolute difference in Da between observed and theoretical
    ppm_error:     float   # relative error in parts-per-million — instrument-agnostic metric
    adduct:        str     # the adduct form that was assumed (e.g. [M+H]+)
    ion_mode:      str     # positive / negative / neutral — derived from adduct


# BatchQueryResult wraps the results for a single (mass, adduct) pair within a batch.
# Keeping query_mass and adduct here lets callers match results back to their inputs
# without needing to track position in the response array.
class BatchQueryResult(BaseModel):
    """One query within a batch search."""
    query_mass:   float
    adduct:       str
    adduct_delta: float          # the Da offset applied — useful for debugging or re-scoring
    result_count: int            # quick summary count without unpacking the full results list
    results:      List[MassResult]


class StatsResponse(BaseModel):
    """Database statistics."""
    total_compounds: int
    by_source:       dict            # e.g. {"HMDB": 217000, "ChEBI": 59000, ...}
    min_mass:        Optional[float] # mass range of the database — useful for sanity checking queries
    max_mass:        Optional[float]


# ─────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────

# Pydantic validates incoming POST bodies against this model automatically.
# Field() lets us attach constraints (min/max, defaults) and descriptions
# that also show up in the auto-generated /docs Swagger UI.
class BatchSearchRequest(BaseModel):
    """POST body for /search/batch."""
    masses:    List[float] = Field(..., min_length=1, max_length=100)  # at least 1, hard cap at 100 to protect the server
    adducts:   List[str]   = Field(default=["[M+H]+"])                 # defaults to the most common positive-mode adduct
    tolerance: float       = Field(default=0.02, gt=0, le=5.0)        # 20 mDa default — typical for Orbitrap data
    sources:   Optional[List[str]] = None                              # None means search all sources
    limit:     int         = Field(default=20, gt=0, le=500)


from pydantic import BaseModel
from typing import List, Optional

class MS2SearchRequest(BaseModel):
    fragment_masses: List[float] = Field(
        ...,
        min_length=1,
        max_length=50,        # 50 fragments is already a very rich spectrum; caps compute cost
        description="List of fragment m/z values"
    )

    # Literal enforces an exact allow-list at the type level — Pydantic rejects
    # anything not in this list before the request even reaches our route logic.
    # This duplicates the ADDUCTS dict check in main.py but gives us earlier,
    # cleaner validation error messages for MS2 specifically.
    adduct: Literal[
        "[M+H]+",
        "[M+Na]+",
        "[M+K]+",
        "[M+NH4]+",
        "[M]+",
        "[M-H]-",
        "[M+Cl]-",
        "[M-2H]-",
        "[M-2H]2-",
        "neutral",
    ] = Field(
        "[M+H]+",   # default: protonated positive mode, the most common LC-MS/MS setup
        description="Adduct type"
    )

    tolerance: float = Field(
        0.02,
        gt=0,
        le=0.1,       # tighter upper bound than mass search — MS2 fragments are noisier so we don't want too loose a window
        description="Mass tolerance in Da"
    )

    sources: Optional[List[str]] = Field(
        None,
        description="Optional source database filter"
    )

    limit: int = Field(
        20,
        gt=1,
        le=100,       # smaller cap than batch — MS2 scoring is more expensive per candidate
        description="Max candidates to return"
    )


# ─────────────────────────────────────────────
# MS2 RESPONSE MODELS
# ─────────────────────────────────────────────

# Represents a single fragment ion that was successfully matched to a candidate compound.
# Keeping per-fragment ppm lets users judge match quality at the individual ion level.
class MS2FragmentMatch(BaseModel):
    fragment_mass: float   # the observed fragment m/z from the input spectrum
    ppm_error:     float   # how far off this match was in ppm
    mass_error:    float   # same in absolute Da
    neutral_mass:  float   # the theoretical neutral mass this fragment was matched to


# One candidate compound from the MS2 search, with its scoring breakdown.
# The score is fragment-count based — how many of the observed fragments
# can this compound structurally explain?
class MS2Candidate(BaseModel):
    source:              str
    source_id:           Optional[str]
    name:                Optional[str]
    formula:             Optional[str]
    n_explained:         int          # number of input fragments this candidate explains
    n_fragments:         int          # total fragments in the query spectrum
    score_pct:           float        # n_explained / n_fragments as a percentage — primary ranking signal
    avg_ppm:             float        # average ppm error across matched fragments — tiebreaker
    fragment_matches:    List[MS2FragmentMatch]   # detailed per-fragment breakdown
    unmatched_fragments: List[float]              # fragments this candidate couldn't explain


# A detected neutral loss — a mass difference between two observed fragments
# that matches a known chemical loss (e.g. -18 Da = water, -44 Da = CO2).
# Neutral losses are structurally informative: they hint at functional groups
# present in the molecule even without a database match.
class MS2NeutralLoss(BaseModel):
    from_mass:  float    # the higher-mass fragment
    to_mass:    float    # the lower-mass fragment
    delta:      float    # the observed mass difference between them
    loss_name:  str      # human-readable name, e.g. "Water loss", "CO2 loss"
    loss_mass:  float    # the theoretical mass of this neutral loss
    ppm_error:  float    # how closely our observed delta matched the theoretical


# Top-level MS2 response — bundles candidates and neutral losses together
# so the caller gets the full picture from a single request.
class MS2SearchResponse(BaseModel):
    fragments:      List[float]          # the original input fragment masses, echoed back for traceability
    candidates:     List[MS2Candidate]   # ranked by score_pct desc, avg_ppm asc
    neutral_losses: List[MS2NeutralLoss] # all detected losses across the spectrum