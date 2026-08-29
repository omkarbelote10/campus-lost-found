import math
import numpy as np
from datetime import datetime
from typing import Optional, Tuple, List

class HybridScorer:
    """Mathematical hybrid ranking formula implementation for ML pipeline evaluation."""
    
    WEIGHT_VISUAL = 0.45
    WEIGHT_TEXT = 0.30
    WEIGHT_CATEGORY = 0.25
    TEMPORAL_LAMBDA = 0.05
    SPATIAL_DECAY_CONSTANT = 0.5

    @classmethod
    def score_pair(
        cls,
        visual_sim: float,
        text_sim: float,
        cat_match: float,
        time_delta_days: float,
        distance_km: Optional[float] = None,
        zone_match_grade: float = 1.0,
        ocr_tokens_intersect: bool = False,
        has_images: bool = True
    ) -> float:
        # Dynamic weight rebalance
        if has_images:
            w_v, w_t, w_c = cls.WEIGHT_VISUAL, cls.WEIGHT_TEXT, cls.WEIGHT_CATEGORY
        else:
            w_v, w_t, w_c = 0.0, 0.70, 0.30

        multimodal_score = w_v * visual_sim + w_t * text_sim + w_c * cat_match

        # Temporal decay
        if time_delta_days < 0:
            d_temp = 0.1
        else:
            d_temp = math.exp(-cls.TEMPORAL_LAMBDA * time_delta_days)

        # Spatial decay
        if distance_km is not None:
            d_spat = 1.0 / (1.0 + cls.SPATIAL_DECAY_CONSTANT * distance_km)
        else:
            d_spat = zone_match_grade

        b_ocr = 0.25 if ocr_tokens_intersect else 0.0

        total = (multimodal_score * (d_spat * d_temp)) + b_ocr
        return min(1.0, max(0.0, total))
