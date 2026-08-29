import re

def preprocess_text(text: str) -> str:
    """Clean and normalize textual descriptions for embedding generation."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def canonicalize_campus_alias(zone_str: str) -> str:
    """Map common campus aliases to standard canonical zones."""
    zone = zone_str.lower()
    if "lib" in zone:
        return "Library Zone"
    if "eng" in zone:
        return "Engineering Block B"
    if "sci" in zone:
        return "Science Block"
    if "hos" in zone:
        return "Hostel 3"
    if "sport" in zone or "gym" in zone:
        return "Sports Complex"
    if "admin" in zone:
        return "Administration Block"
    return zone_str.title()
