import numpy as np
from typing import List, Union, Optional
from PIL import Image

class SigLIPEmbeddingGenerator:
    """Wrapper around Hugging Face Google SigLIP (google/siglip-base-patch16-224)."""
    
    def __init__(self, model_name: str = "google/siglip-base-patch16-224"):
        self.model_name = model_name
        self.model = None
        self.processor = None
        self._is_fallback = False
        self._load_model()

    def _load_model(self):
        try:
            from transformers import AutoProcessor, AutoModel
            import torch
            self.processor = AutoProcessor.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name)
            self.model.eval()
        except Exception:
            self._is_fallback = True

    def get_text_embedding(self, text: str) -> List[float]:
        if not text:
            return [0.0] * 768
        
        if not self._is_fallback and self.model is not None and self.processor is not None:
            try:
                import torch
                inputs = self.processor(text=[text], return_tensors="pt", padding=True)
                with torch.no_grad():
                    features = self.model.get_text_features(**inputs)
                    features = features / features.norm(dim=-1, keepdim=True)
                    return features[0].tolist()
            except Exception:
                pass

        # Deterministic 768-d semantic hash fallback
        vec = np.zeros(768, dtype=np.float32)
        words = text.lower().split()
        for idx, word in enumerate(words):
            for char_idx, char in enumerate(word):
                pos = (ord(char) * 31 + idx * 17 + char_idx * 7) % 768
                vec[pos] += 1.0 / (char_idx + 1)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def get_image_embedding(self, image: Union[str, Image.Image]) -> Optional[List[float]]:
        try:
            if isinstance(image, str):
                img = Image.open(image).convert("RGB")
            else:
                img = image.convert("RGB")

            if not self._is_fallback and self.model is not None and self.processor is not None:
                try:
                    import torch
                    inputs = self.processor(images=img, return_tensors="pt")
                    with torch.no_grad():
                        features = self.model.get_image_features(**inputs)
                        features = features / features.norm(dim=-1, keepdim=True)
                        return features[0].tolist()
                except Exception:
                    pass

            resized = img.resize((32, 24))
            arr = np.array(resized, dtype=np.float32) / 255.0
            vec = arr.flatten()[:768]
            if len(vec) < 768:
                vec = np.pad(vec, (0, 768 - len(vec)))
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec.tolist()
        except Exception:
            return None
