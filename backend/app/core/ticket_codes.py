import random, string
from datetime import datetime

def generate_ticket_code() -> str:
    """CIV-2025-04872 format. Deterministic enough, not sequential."""
    year = datetime.now().year
    suffix = ''.join(random.choices(string.digits, k=5))
    return f"CIV-{year}-{suffix}"
