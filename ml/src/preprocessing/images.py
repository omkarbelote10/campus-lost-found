from PIL import Image, ImageOps
from typing import Union, Tuple
from pathlib import Path

def preprocess_image(image_input: Union[str, Path, Image.Image], target_size: Tuple[int, int] = (224, 224)) -> Image.Image:
    """Pad aspect ratio and convert to RGB for SigLIP input."""
    if isinstance(image_input, (str, Path)):
        img = Image.open(image_input)
    else:
        img = image_input

    img = img.convert("RGB")
    # Pad to square maintaining aspect ratio
    img.thumbnail(target_size, Image.Resampling.LANCZOS)
    delta_w = target_size[0] - img.size[0]
    delta_h = target_size[1] - img.size[1]
    padding = (delta_w // 2, delta_h // 2, delta_w - (delta_w // 2), delta_h - (delta_h // 2))
    padded_img = ImageOps.expand(img, padding, fill=(255, 255, 255))
    return padded_img
