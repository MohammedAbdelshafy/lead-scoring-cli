"""lead_scoring — transparent weighted lead scoring + seller/buyer matching."""
from .engine import score_row, score_property_row, grade, INTENT, WEIGHTS, PROPERTY_WEIGHTS

__version__ = "0.2.0"
__all__ = ["score_row", "score_property_row", "grade", "INTENT", "WEIGHTS", "PROPERTY_WEIGHTS"]
