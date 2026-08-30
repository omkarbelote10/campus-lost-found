import math
from datetime import datetime
from typing import Tuple, Optional
import numpy as np

class ScoringEngine:
    """
    Hybrid scoring formula:
    S_total = (w_v * S_visual + w_t * S_text + w_c * S_cat) * (D_spatial * D_temporal) + B_ocr
    """
    
    # Default weights
    WEIGHT_VISUAL = 0.45
    WEIGHT_TEXT = 0.30
    WEIGHT_CATEGORY = 0.25
    
    # Decay constants
    TEMPORAL_LAMBDA = 0.05
    SPATIAL_DECAY_CONSTANT = 0.5

    # Context (space/time) can attenuate a match, never veto it. Multiplying the
    # feature score by raw decay makes thresholds impossible: a true match found
    # 7 days later (0.90 * 0.705 = 0.63) scores BELOW a same-day false match
    # (0.65 * 1.0). With the floor, context scales the score into
    # [CONTEXT_FLOOR, 1.0] x feature, so "right item, found later / elsewhere"
    # stays above "wrong item, found here and now".
    CONTEXT_FLOOR = 0.65

    # Two products of the same category whose photos carry different brand marks
    # are almost never the same object, however alike they look. Applied only
    # when BOTH brands were read confidently -- an unknown brand is not evidence.
    BRAND_MISMATCH_PENALTY = 0.55

    # Thresholds, calibrated on backend/scripts/benchmark.py (real uploads,
    # graded re-photography): at 0.70 precision was 57% -> after the context
    # floor the false band tops out ~0.65, so 0.70 surfaces true matches across
    # a two-week gap while cutting same-day false pairs.
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    POTENTIAL_THRESHOLD = 0.70
    
    @staticmethod
    def calculate_visual_score(image_embedding_1: Optional[list], image_embedding_2: Optional[list]) -> float:
        """Calculate cosine similarity between image embeddings"""
        if image_embedding_1 is None or image_embedding_2 is None:
            return 0.0
        
        try:
            vec1 = np.array(image_embedding_1)
            vec2 = np.array(image_embedding_2)
            
            # Cosine similarity. float() is required, not cosmetic: numpy returns
            # a float32 scalar here and psycopg2 cannot adapt one, so persisting
            # the score raises "can't adapt type 'numpy.float32'".
            similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            return float(max(0.0, similarity))
        except Exception:
            return 0.0

    @staticmethod
    def calculate_text_score(text_embedding_1: Optional[list], text_embedding_2: Optional[list]) -> float:
        """Calculate cosine similarity between text embeddings"""
        if text_embedding_1 is None or text_embedding_2 is None:
            return 0.0
        
        try:
            vec1 = np.array(text_embedding_1)
            vec2 = np.array(text_embedding_2)
            
            # See calculate_visual_score: the float() cast keeps psycopg2 able to
            # persist this value.
            similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            return float(max(0.0, similarity))
        except Exception:
            return 0.0

    @staticmethod
    def calculate_category_score(category_1: str, category_2: str) -> float:
        """Category exact match score"""
        return 1.0 if category_1 == category_2 else 0.0
    
    @staticmethod
    def calculate_temporal_decay(lost_time: datetime, found_time: datetime) -> float:
        """Exponential temporal decay function"""
        if found_time < lost_time:
            # Found before lost (anomaly)
            return 0.1
        
        delta_t = (found_time - lost_time).total_seconds() / 86400  # Convert to days
        
        if delta_t < 0:
            return 0.1
        
        # D_temporal = exp(-lambda * delta_t)
        decay = math.exp(-ScoringEngine.TEMPORAL_LAMBDA * delta_t)
        return max(0.0, min(1.0, decay))
    
    @staticmethod
    def calculate_spatial_decay(lat1: Optional[float], lon1: Optional[float], 
                               lat2: Optional[float], lon2: Optional[float],
                               zone_1: Optional[str], zone_2: Optional[str]) -> float:
        """Spatial decay using GPS or campus zones"""
        
        # If both have GPS coordinates
        if all([lat1, lon1, lat2, lon2]):
            distance_km = ScoringEngine.haversine_distance(lat1, lon1, lat2, lon2)
            decay = 1.0 / (1.0 + ScoringEngine.SPATIAL_DECAY_CONSTANT * distance_km)
            return max(0.0, min(1.0, decay))
        
        # Zone-based scoring
        if zone_1 and zone_2:
            if zone_1 == zone_2:
                return 1.0  # Exact zone match
            elif ScoringEngine.are_adjacent_zones(zone_1, zone_2):
                return 0.8  # Adjacent zones
            else:
                return 0.4  # Distant zones
        
        return 0.5  # Default if no location info
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in km between two GPS coordinates"""
        R = 6371  # Earth radius in km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    @staticmethod
    def are_adjacent_zones(zone1: str, zone2: str) -> bool:
        """Check if two zones are adjacent"""
        # Keys must match the zone names the frontend submits exactly. These
        # previously said "Engineering Block B" and "Hostel 3" while the forms
        # send "Engineering Block" and "Hostel", so adjacency never matched and
        # every cross-zone pair was scored as distant.
        adjacent_map = {
            "Library Zone": ["Engineering Block", "Administration Block"],
            "Engineering Block": ["Library Zone", "Hostel"],
            "Hostel": ["Engineering Block", "Sports Complex"],
            "Administration Block": ["Library Zone", "Science Block"],
            "Science Block": ["Administration Block", "Sports Complex"],
            "Sports Complex": ["Hostel", "Science Block"],
        }
        
        return zone1 in adjacent_map.get(zone2, [])
    
    @staticmethod
    def calculate_ocr_bonus(ocr_tokens_1: list, ocr_tokens_2: list) -> float:
        """OCR token matching bonus"""
        if not ocr_tokens_1 or not ocr_tokens_2:
            return 0.0
        
        intersection = len(set(ocr_tokens_1) & set(ocr_tokens_2))
        return 0.25 if intersection > 0 else 0.0
    
    @staticmethod
    def rebalance_weights(has_image_1: bool, has_image_2: bool) -> Tuple[float, float, float]:
        """Dynamically rebalance weights if images are missing"""
        if has_image_1 and has_image_2:
            return ScoringEngine.WEIGHT_VISUAL, ScoringEngine.WEIGHT_TEXT, ScoringEngine.WEIGHT_CATEGORY
        else:
            # No images: rely on text and category
            return 0.0, 0.70, 0.30
    
    @staticmethod
    def calculate_brand_factor(brand_1: Optional[str], brand_2: Optional[str]) -> float:
        """1.0 unless both brands are known and disagree."""
        if not brand_1 or not brand_2:
            return 1.0
        if brand_1.strip().lower() == brand_2.strip().lower():
            return 1.0
        return ScoringEngine.BRAND_MISMATCH_PENALTY

    @staticmethod
    def calculate_total_score(
        visual_score: float,
        text_score: float,
        category_score: float,
        spatial_decay: float,
        temporal_decay: float,
        ocr_bonus: float,
        has_image_1: bool,
        has_image_2: bool,
        brand_factor: float = 1.0
    ) -> Tuple[float, str]:
        """
        Calculate total match score and determine status
        
        Returns:
            (total_score, status)
        """
        
        # Rebalance weights
        w_v, w_t, w_c = ScoringEngine.rebalance_weights(has_image_1, has_image_2)
        
        # Multimodal feature score
        feature_score = w_v * visual_score + w_t * text_score + w_c * category_score

        # Apply contextual decay, floored so context attenuates but never vetoes
        # (see CONTEXT_FLOOR).
        floor = ScoringEngine.CONTEXT_FLOOR
        context = floor + (1.0 - floor) * (spatial_decay * temporal_decay)
        contextual_score = feature_score * context

        # A confident brand disagreement scales the whole thing down, including
        # the OCR bonus: a shared serial-like token means nothing if the photos
        # show products from two different makers.
        total_score = (contextual_score + ocr_bonus) * brand_factor
        
        # Normalize to [0, 1]
        total_score = min(1.0, max(0.0, total_score))
        
        # Determine status
        if total_score >= ScoringEngine.HIGH_CONFIDENCE_THRESHOLD:
            status = "HIGH_CONFIDENCE"
        elif total_score >= ScoringEngine.POTENTIAL_THRESHOLD:
            status = "POTENTIAL"
        else:
            status = "REJECTED"
        
        return total_score, status
