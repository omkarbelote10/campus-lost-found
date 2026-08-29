import numpy as np
from typing import List, Dict, Any

def recall_at_k(actual_relevant_id: Any, ranked_candidate_ids: List[Any], k: int = 5) -> float:
    """Compute Recall@K (binary ground truth, single or set of relevant items)."""
    top_k = ranked_candidate_ids[:k]
    if isinstance(actual_relevant_id, (list, set)):
        relevant_set = set(actual_relevant_id)
        if not relevant_set:
            return 0.0
        hits = len(set(top_k) & relevant_set)
        return hits / len(relevant_set)
    else:
        return 1.0 if actual_relevant_id in top_k else 0.0

def precision_at_k(actual_relevant_id: Any, ranked_candidate_ids: List[Any], k: int = 5) -> float:
    """Compute Precision@K."""
    top_k = ranked_candidate_ids[:k]
    if not top_k:
        return 0.0
    if isinstance(actual_relevant_id, (list, set)):
        relevant_set = set(actual_relevant_id)
        hits = len(set(top_k) & relevant_set)
        return hits / len(top_k)
    else:
        return 1.0 / len(top_k) if actual_relevant_id in top_k else 0.0

def mean_reciprocal_rank(queries_results: List[Dict[str, Any]]) -> float:
    """
    Compute Mean Reciprocal Rank (MRR) across all test queries.
    queries_results: List of dicts with 'target_id' and 'ranked_ids'
    """
    if not queries_results:
        return 0.0
    
    rr_list = []
    for item in queries_results:
        target = item["target_id"]
        ranked = item["ranked_ids"]
        if target in ranked:
            rank = ranked.index(target) + 1
            rr_list.append(1.0 / rank)
        else:
            rr_list.append(0.0)
    
    return float(np.mean(rr_list))

def dcg_at_k(r: List[float], k: int) -> float:
    """Discounted Cumulative Gain at K."""
    r_arr = np.asarray(r, dtype=np.float64)[:k]
    if r_arr.size:
        return float(np.sum(r_arr / np.log2(np.arange(2, r_arr.size + 2))))
    return 0.0

def ndcg_at_k(r: List[float], k: int) -> float:
    """Normalized Discounted Cumulative Gain at K."""
    dcg_max = dcg_at_k(sorted(r, reverse=True), k)
    if not dcg_max:
        return 0.0
    return float(dcg_at_k(r, k) / dcg_max)
