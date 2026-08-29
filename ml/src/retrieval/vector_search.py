import numpy as np
from typing import List, Dict, Any

class VectorSearchIndex:
    """In-memory cosine similarity ANN retrieval index for benchmark evaluation and pgvector testing."""
    
    def __init__(self):
        self.item_ids = []
        self.embeddings = []
        self.metadata = []

    def add_item(self, item_id: Any, embedding: List[float], meta: Dict[str, Any] = None):
        self.item_ids.append(item_id)
        self.embeddings.append(embedding)
        self.metadata.append(meta or {})

    def query(self, query_vec: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        if not self.embeddings:
            return []
        
        X = np.array(self.embeddings, dtype=np.float32)
        q = np.array(query_vec, dtype=np.float32)

        norms = np.linalg.norm(X, axis=1) * np.linalg.norm(q)
        norms[norms == 0] = 1e-10
        scores = np.dot(X, q) / norms

        top_indices = np.argsort(-scores)[:top_k]
        results = []
        for idx in top_indices:
            results.append({
                "item_id": self.item_ids[idx],
                "score": float(scores[idx]),
                "metadata": self.metadata[idx]
            })
        return results
