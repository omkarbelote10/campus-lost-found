import re
from typing import List, Union
from PIL import Image

def extract_ocr_tokens_from_text(text: str) -> List[str]:
    """Extract alphanumeric serials and IDs (length >= 4)."""
    if not text:
        return []
    tokens = re.findall(r'[A-Za-z0-9]{4,}', text)
    return list(set(t.upper() for t in tokens))

def extract_ocr_from_image_file(image_path: str) -> List[str]:
    """Extract OCR tokens from an image file using Tesseract."""
    try:
        import pytesseract
        img = Image.open(image_path)
        raw_text = pytesseract.image_to_string(img)
        return extract_ocr_tokens_from_text(raw_text)
    except Exception:
        return []
