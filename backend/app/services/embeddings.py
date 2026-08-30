"""Multimodal embedding generation for item matching.

Two separate models, because the two jobs are different:

  text  -> SigLIP (google/siglip-base-patch16-224)
           A caption-aligned space is right for matching two people's free-text
           descriptions of the same object.

  image -> DINOv2 (facebook/dinov2-base)
           Re-identification needs instance-level discrimination. SigLIP is
           trained to align images with captions, which never mention which
           specific handset -- so it learns to ignore exactly the scuffs and
           wear that identify an object. Measured on real uploads, SigLIP scored
           two different Motorola phones (0.8642) higher than the same iPhone
           re-photographed (0.6839): the ranking inverted. DINOv2 is
           self-supervised with no text supervision and keeps that detail.

Both output 768-d, so Item.image_embedding and Item.text_embedding stay
Vector(768) and the pgvector indexes are unchanged.

Models load lazily on first use, not at import, so startup never blocks on a
download and every non-matching route works without the weights.

On failure the embedders return None rather than a substitute vector. A
fabricated embedding still yields a plausible-looking cosine similarity, which
reads as a confident match while meaning nothing.
"""

import logging
import threading
from typing import List, Optional, Union

from PIL import Image, ImageOps

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
    silently running several times slower on the CPU."""
    configured = (settings.EMBEDDING_DEVICE or "auto").strip().lower()
    if configured != "auto":
        return configured

    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


class _LazyModel:
    """Shared lazy-load and device plumbing for one HuggingFace model."""

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

    def _build(self, device: str):
        """Subclasses load their processor/model and return (processor, model)."""
        raise NotImplementedError

    def _ensure_loaded(self) -> bool:
        if not settings.EMBEDDINGS_ENABLED:
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
                device = resolve_device()
                processor, model = self._build(device)
                model.eval()
                model.to(device)

                self._processor = processor
                self._model = model
                self._device = device
                logger.info("%s loaded on %s", self.model_name, device)
                return True
            except Exception:
                # Missing deps, no network on first run, a corrupt cache, or an
                # unusable CUDA device. Latch the failure so every later report
                # does not pay the same timeout again.
                self._load_failed = True
                logger.exception(
                    "%s failed to load; matching will run without these embeddings",
                    self.model_name,
                )
                return False

    def _to_device(self, inputs):
        """Move every tensor in a processor batch onto the model's device."""
        if not self._device or self._device == "cpu":
            return inputs
        return {
            key: value.to(self._device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }


class SigLIPTextEmbedder(_LazyModel):
    """Text tower for descriptions, plus zero-shot brand reading from photos.

    SigLIP's image tower is useless for deciding whether two photos show the same
    physical object (see module docstring), but being caption-aligned makes it
    good at "what kind of thing is this" -- which is exactly what brand detection
    needs. Measured on the real uploads it identified Apple/Motorola correctly
    every time with runners-up at ~0.001.
    """

    def _build(self, device: str):
        from transformers import AutoModel, AutoProcessor

        return (
            AutoProcessor.from_pretrained(self.model_name),
            AutoModel.from_pretrained(self.model_name),
        )

    def detect_brand(self, image: Union[str, Image.Image]) -> Optional[str]:
        """Read the brand off a product photo, or None when unsure.

        Returning None on low confidence matters: an unknown brand must not be
        treated as evidence of a mismatch, only a confident disagreement should
        count against a pair.
        """
        if not settings.BRAND_VOCABULARY or not self._ensure_loaded():
            return None

        try:
            import torch

            brands = [b.strip() for b in settings.BRAND_VOCABULARY.split(",") if b.strip()]
            prompts = [f"a photo of a {brand} product" for brand in brands]
            img = Image.open(image) if isinstance(image, str) else image

            inputs = self._processor(
                text=prompts,
                images=img.convert("RGB"),
                padding=_TEXT_PADDING,
                max_length=_TEXT_MAX_LENGTH,
                truncation=True,
                return_tensors="pt",
            )
            inputs = self._to_device(inputs)
            with torch.no_grad():
                probs = torch.sigmoid(self._model(**inputs).logits_per_image[0]).cpu()

            order = probs.argsort(descending=True)
            top, runner = probs[order[0]].item(), probs[order[1]].item() if len(order) > 1 else 0.0
            if top < settings.BRAND_MIN_CONFIDENCE or top < 2 * runner:
                return None
            return brands[order[0]]
        except Exception:
            logger.exception("Brand detection failed")
            return None

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
            logger.exception("Text embedding failed")
            return None


class DINOv2ImageEmbedder(_LazyModel):
    """Self-supervised image features for instance-level re-identification."""

    INPUT_SIZE = 224

    def _build(self, device: str):
        from transformers import AutoImageProcessor, AutoModel

        return (
            AutoImageProcessor.from_pretrained(self.model_name),
            AutoModel.from_pretrained(self.model_name),
        )

    @classmethod
    def _letterbox(cls, img: Image.Image) -> Image.Image:
        """Fit the whole image into a square by padding, never cropping.

        DINOv2's default processor resizes the shortest edge to 256 and then
        centre-crops 224. A tall product photo (a phone shot at 297x744) becomes
        256x641 and the crop keeps only the middle band -- most of the object is
        thrown away, and what survives is mostly background. Measured on the real
        uploads that made a black Motorola score higher against an orange iPhone
        (0.656) than against a blue Motorola (0.615): the wrong object won purely
        because its aspect ratio survived the crop. Padding instead of cropping
        flips that to 0.828 for the correct pair.
        """
        img = img.convert("RGB")
        img.thumbnail((cls.INPUT_SIZE, cls.INPUT_SIZE), Image.Resampling.LANCZOS)
        pad_w = cls.INPUT_SIZE - img.size[0]
        pad_h = cls.INPUT_SIZE - img.size[1]
        return ImageOps.expand(
            img,
            (pad_w // 2, pad_h // 2, pad_w - pad_w // 2, pad_h - pad_h // 2),
            fill=(255, 255, 255),
        )

    GRID = 16  # 224 / patch size 14

    def _object_crop(self, original: Image.Image) -> Image.Image:
        """Crop to the salient object so the surroundings cannot sway the vector.

        DINOv2 foreground patches align with the CLS token and background patches
        do not, which gives a saliency map for free -- no extra model. Cropping to
        its bounding box means the same item photographed on a desk, on grass or
        on tiles produces nearly the same embedding. Measured: separation from the
        nearest wrong object improved from +0.063 to +0.076 (desk), +0.071 to
        +0.081 (grass), +0.072 to +0.085 (tiles).
        """
        try:
            import torch

            boxed = self._letterbox(original)
            inputs = self._processor(
                images=boxed, return_tensors="pt", do_resize=False, do_center_crop=False
            )
            inputs = self._to_device(inputs)
            with torch.no_grad():
                out = self._model(**inputs).last_hidden_state[0]
            cls = out[0] / out[0].norm()
            patches = out[1:] / out[1:].norm(dim=-1, keepdim=True)

            saliency = (patches @ cls).reshape(self.GRID, self.GRID)
            ys, xs = torch.where(saliency > saliency.mean() + 0.35 * saliency.std())
            if len(xs) < 4:
                return boxed

            cell = self.INPUT_SIZE / self.GRID
            box = (xs.min().item() * cell, ys.min().item() * cell,
                   (xs.max().item() + 1) * cell, (ys.max().item() + 1) * cell)

            # Map the box out of letterboxed space back onto original pixels.
            w, h = original.size
            scale = min(self.INPUT_SIZE / w, self.INPUT_SIZE / h)
            pad_x = (self.INPUT_SIZE - w * scale) / 2
            pad_y = (self.INPUT_SIZE - h * scale) / 2
            crop = (max(0, (box[0] - pad_x) / scale), max(0, (box[1] - pad_y) / scale),
                    min(w, (box[2] - pad_x) / scale), min(h, (box[3] - pad_y) / scale))

            # A degenerate box means the saliency map was flat; keep the full frame.
            if crop[2] - crop[0] < 12 or crop[3] - crop[1] < 12:
                return boxed
            return self._letterbox(original.crop(tuple(int(v) for v in crop)))
        except Exception:
            logger.exception("Object crop failed; falling back to the whole frame")
            return self._letterbox(original)

    def embed_image(self, image: Union[str, Image.Image]) -> Optional[List[float]]:
        if not self._ensure_loaded():
            return None

        try:
            import torch

            original = Image.open(image) if isinstance(image, str) else image
            original = original.convert("RGB")
            img = self._object_crop(original) if settings.OBJECT_CROP else self._letterbox(original)

            # Already sized to 224x224 above, so the processor must not resize or
            # crop again -- it would undo the padding.
            inputs = self._processor(
                images=img, return_tensors="pt", do_resize=False, do_center_crop=False
            )
            inputs = self._to_device(inputs)
            with torch.no_grad():
                outputs = self._model(**inputs)
                # DINOv2 is not CLIP-style, so there is no get_image_features().
                # The CLS token is the representation used for retrieval; the
                # remaining positions are per-patch features.
                features = outputs.last_hidden_state[:, 0]
                features = features / features.norm(dim=-1, keepdim=True)
            return features[0].cpu().tolist()
        except Exception:
            logger.exception("Image embedding failed")
            return None


class Embedder:
    """Facade over both towers, so callers stay unaware of which model does what."""

    def __init__(self):
        self.text = SigLIPTextEmbedder(settings.SIGLIP_MODEL)
        self.image = DINOv2ImageEmbedder(settings.DINOV2_MODEL)

    def embed_text(self, text: str) -> Optional[List[float]]:
        return self.text.embed_text(text)

    def embed_image(self, image: Union[str, Image.Image]) -> Optional[List[float]]:
        return self.image.embed_image(image)

    def detect_brand(self, image: Union[str, Image.Image]) -> Optional[str]:
        return self.text.detect_brand(image)


_embedder = Embedder()


def get_embedder() -> Embedder:
    return _embedder


def build_item_text(title: str, description: str, category: str, campus_zone: str) -> str:
    """The text the model sees for an item. Both sides of a match are built the
    same way, so a lost and a found report of the same object land near each
    other in the embedding space."""
    return " ".join(part for part in (title, description, category, campus_zone) if part)
