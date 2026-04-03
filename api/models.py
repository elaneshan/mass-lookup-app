"""
API Models
==========
Pydantic schemas for request validation and response serialization.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# ─────────────────────────────────────────────
# RESPONSE MODELS
# ─────────────────────────────────────────────

class CompoundResult(BaseModel):
    """Single compound match returned by mass or formula search."""
    source:       str
    source_id:    Optional[str]  = None
    name:         Optional[str]  = None
    formula:      Optional[str]  = None
    cas:          Optional[str]  = None
    inchikey:     Optional[str]  = None
    exact_mass:   Optional[float] = None

class MassResult(CompoundResult):
    """Mass search result — includes error fields."""
    observed_mass: float
    mass_error:    float
    ppm_error:     float
    adduct:        str
    ion_mode:      str

class BatchQueryResult(BaseModel):
    """One query within a batch search."""
    query_mass:  float
    adduct:      str
    adduct_delta: float
    result_count: int
    results:     List[MassResult]

class StatsResponse(BaseModel):
    """Database statistics."""
    total_compounds: int
    by_source:       dict
    min_mass:        Optional[float]
    max_mass:        Optional[float]


# ─────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────

class BatchSearchRequest(BaseModel):
    """POST body for /search/batch."""
    masses:    List[float] = Field(..., min_length=1, max_length=100)
    adducts:   List[str]   = Field(default=["[M+H]+"])
    tolerance: float       = Field(default=0.02, gt=0, le=5.0)
    sources:   Optional[List[str]] = None
    limit:     int         = Field(default=20, gt=0, le=500)



# ── Add these to api/models.py ────────────────────────────────────────────────
# (paste alongside the existing model definitions)

from pydantic import BaseModel
from typing import List, Optional

class MS2SearchRequest(BaseModel):
    fragment_masses: List[float]
    adduct:          str   = "[M+H]+"
    tolerance:       float = 0.02
    sources:         Optional[List[str]] = None
    limit:           int   = 20

class MS2FragmentMatch(BaseModel):
    fragment_mass: float
    ppm_error:     float
    mass_error:    float
    neutral_mass:  float

class MS2Candidate(BaseModel):
    source:             str
    source_id:          Optional[str]
    name:               Optional[str]
    formula:            Optional[str]
    n_explained:        int
    n_fragments:        int
    score_pct:          float
    avg_ppm:            float
    fragment_matches:   List[MS2FragmentMatch]
    unmatched_fragments: List[float]

class MS2NeutralLoss(BaseModel):
    from_mass:  float
    to_mass:    float
    delta:      float
    loss_name:  str
    loss_mass:  float
    ppm_error:  float

class MS2SearchResponse(BaseModel):
    fragments:      List[float]
    candidates:     List[MS2Candidate]
    neutral_losses: List[MS2NeutralLoss]