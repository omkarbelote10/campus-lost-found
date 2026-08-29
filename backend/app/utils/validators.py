import re
from app.core.config import get_settings

settings = get_settings()

def validate_campus_email(email: str) -> bool:
    pattern = rf"^[a-zA-Z0-9._%+-]+@{re.escape(settings.CAMPUS_EMAIL_DOMAIN)}$"
    return re.match(pattern, email) is not None

def extract_ocr_tokens(text: str) -> list:
    tokens = re.findall(r'[A-Za-z0-9]{4,}', text)
    return [token.upper() for token in tokens]

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
