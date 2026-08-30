import re
from app.core.config import get_settings

settings = get_settings()

def validate_campus_email(email: str) -> bool:
    pattern = rf"^[a-zA-Z0-9._%+-]+@{re.escape(settings.CAMPUS_EMAIL_DOMAIN)}$"
    return re.match(pattern, email) is not None

# An identifier is a run of letters+digits with at least one of each (DL992384,
# SERIAL9931, A1B2C3), or a long pure-digit run (IMEI/receipt fragments).
_IDENTIFIER = re.compile(r"\b(?=[A-Za-z0-9-]*\d)(?=[A-Za-z0-9-]*[A-Za-z])[A-Za-z0-9-]{4,}\b|\b\d{6,}\b")


def extract_ocr_tokens(text: str) -> list:
    """Pull serial-number-like identifiers out of a description.

    This must NOT return ordinary words. It previously matched [A-Za-z0-9]{4,},
    which meant a phone described as "black" and an umbrella described as "black"
    shared an "OCR token" and collected the full 0.25 identity bonus -- the
    strongest term in the scoring formula -- for having a colour in common.
    A serial number is real evidence of identity; the word "black" is not.
    """
    if not text:
        return []
    tokens = {match.group(0).upper().replace("-", "") for match in _IDENTIFIER.finditer(text)}
    return sorted(tokens)

def parse_campus_zone(zone_name: str) -> str:
    zone_mapping = {
        "lib": "Library Zone",
        "eng": "Engineering Block",
        "sci": "Science Block",
        "hos": "Hostel",
        "admin": "Administration Block",
        "sport": "Sports Complex",
    }
    
    for key, value in zone_mapping.items():
        if key.lower() in zone_name.lower():
            return value
    return zone_name

def validate_file_extension(filename: str, allowed_extensions: list = None) -> bool:
    if allowed_extensions is None:
        allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf']
    
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in allowed_extensions
