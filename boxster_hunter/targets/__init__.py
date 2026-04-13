"""Target registry. Each target is a ``TargetConfig`` instance that fully
describes one car-shaped thing the hunter looks for.

To add a new target: write a new ``targets/<name>.py``, define ``TARGET``,
and append it to ``ALL_TARGETS`` below.
"""

from boxster_hunter.targets.audi_s3_8v_facelift import TARGET as AUDI_S3_8V_FACELIFT
from boxster_hunter.targets.base import (
    Disqualifier,
    ScoringRule,
    TargetConfig,
    TieredRule,
    any_match,
    match_color,
)
from boxster_hunter.targets.porsche_986_boxster_s import TARGET as PORSCHE_986_BOXSTER_S

ALL_TARGETS: list[TargetConfig] = [
    PORSCHE_986_BOXSTER_S,
    AUDI_S3_8V_FACELIFT,
]

__all__ = [
    "ALL_TARGETS",
    "PORSCHE_986_BOXSTER_S",
    "AUDI_S3_8V_FACELIFT",
    "TargetConfig",
    "Disqualifier",
    "ScoringRule",
    "TieredRule",
    "any_match",
    "match_color",
]
