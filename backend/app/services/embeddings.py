"""SigLIP multimodal embedding generation.

The model is loaded lazily on first use, not at import time, so that:
  * app startup does not block on a ~400MB weight download, and
  * every non-matching route still works on a machine without the weights.

If the model cannot be loaded, the embedders return None rather than a
substitute vector. A fabricated embedding would still produce a plausible
cosine similarity, which reads as a confident match while meaning nothing --
matching degrades to category + decay instead, which is at least honest.
"""

import logging
import threading
from typing import List, Optional, Union

from PIL import Image

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768

# SigLIP was trained with a fixed 64-token text window and, unlike CLIP, expects
# every sequence padded to it. Dynamic padding silently degrades the embedding.
_TEXT_PADDING = "max_length"
_TEXT_MAX_LENGTH = 64


def resolve_device() -> str:
    """Pick the torch device. "auto" prefers CUDA and quietly falls back to CPU;
    an explicit "cuda" is honoured as-is so a GPU deploy fails loudly rather than
    silently running 20x slower on the CPU."""
    configured = (settings.SIGLIP_DEVICE or "auto").strip().lower()
    if configured != "auto":
        return configured

    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


class SigLIPEmbedder:
    """Thread-safe lazy wrapper around google/siglip-base-patch16-224."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        self._processor = None
        self._device = None
        self._load_failed = False
        self._lock = threading.Lock()

    @property
    def is_available(self) -> bool:
        """True once the weights are resident. Does not trigger a load."""
        return self._model is not None

    @property
    def device(self) -> Optional[str]:
        """The device the weights actually landed on, or None before loading."""
        return self._device

    def _ensure_loaded(self) -> bool:
        if not settings.SIGLIP_ENABLED:
            return False
        if self._model is not None:
            return True
        if self._load_failed:
            return False

        with self._lock:
            # Re-check under the lock: a concurrent request may have won the race.
            if self._model is not None:
                return True
            if self._load_failed:
                return False

            try:
                from transformers import AutoModel, AutoProcessor

                device = resolve_device()
                processor = AutoProcessor.from_pretrained(self.model_name)
                model = AutoModel.from_pretrained(self.model_name)
                model.eval()
                model.to(device)

                self._processor = processor
                self._model = model
                self._device = device
                logger.info("SigLIP %s loaded on %s", self.model_name, device)
                return True
            except Exception:
                # Missing torch/transformers, no network on first run, a corrupt
                # cache, or an unusable CUDA device. Latch the failure so every
                # later report does not pay the same timeout again.
                self._load_failed = True
                logger.exception("SigLIP failed to load; matching will run without embeddings")
                return False

    def embed_text(self, text: str) -> Optional[List[float]]:
        if not text or not text.strip():
            return None
        if not self._ensure_loaded():
            return None

        try:
            import torch

            inputs = self._processor(
                text=[text],
                padding=_TEXT_PADDING,
                max_length=_TEXT_MAX_LENGTH,
                truncation=True,
                return_tensors="pt",
            )
            inputs = self._to_device(inputs)
            with torch.no_grad():
                features = self._model.get_text_features(**inputs)
                features = features / features.norm(dim=-1, keepdim=True)
            # .cpu() before .tolist(): the tensor lives in GPU memory and pgvector
            # needs plain Python floats.
            return features[0].cpu().tolist()
        except Exception:
            logger.exception("SigLIP text embedding failed")
            return None

    def embed_image(self, image: Union[str, Image.Image]) -> Optional[List[float]]:
        if not self._ensure_loaded():
            return None

        try:
            import torch

            img = Image.open(image) if isinstance(image, str) else image
            img = img.convert("RGB")

            inputs = self._processor(images=img, return_tensors="pt")
            inputs = self._to_device(inputs)
            with torch.no_grad():
                features = self._model.get_image_features(**inputs)
                features = features / features.norm(dim=-1, keepdim=True)
            return features[0].cpu().tolist()
        except Exception:
            logger.exception("SigLIP image embedding failed")
            return None

    def _to_device(self, inputs):
        """Move every tensor in a processor batch onto the model's device."""
        if not self._device or self._device == "cpu":
            return inputs
        return {
            key: value.to(self._device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }


_embedder = SigLIPEmbedder(settings.SIGLIP_MODEL)


def get_embedder() -> SigLIPEmbedder:
    return _embedder


def build_item_text(title: str, description: str, category: str, campus_zone: str) -> str:
    """The text SigLIP sees for an item. Both sides of a match are built the
    same way, so a lost and a found report of the same object land near each
    other in the embedding space."""
    return " ".join(part for part in (title, description, category, campus_zone) if part)
