import re
from typing import List, Union
from PIL import Image

# Must mix letters and digits (DL992384, SERIAL9931) or be a long digit run.
# Plain [A-Za-z0-9]{4,} matched ordinary words, so any two reports sharing the
# word "black" looked like they shared a serial number.
_IDENTIFIER = re.compile(r"\b(?=[A-Za-z0-9-]*\d)(?=[A-Za-z0-9-]*[A-Za-z])[A-Za-z0-9-]{4,}\b|\b\d{6,}\b")


def extract_ocr_tokens_from_text(text: str) -> List[str]:
    """Extract alphanumeric serials and IDs, not ordinary words."""
    if not text:
        return []
    return sorted({m.group(0).upper().replace("-", "") for m in _IDENTIFIER.finditer(text)})

def extract_ocr_from_image_file(image_path: str) -> List[str]:
    """Extract OCR tokens from an image file using Tesseract."""
    try:
        import pytesseract
        img = Image.open(image_path)
        raw_text = pytesseract.image_to_string(img)
        return extract_ocr_tokens_from_text(raw_text)
    except Exception:
        return []
