"""
WardDetectionService
====================
Auto-detects the Chennai ward from a free-text location using:
  1. Gemini Flash — extracts a clean Chennai locality name from messy user input
  2. Fuzzy ward mapping — maps locality → ward_id using the canonical WARD_MAP

Usage (from FastAPI endpoint):
    result = await WardDetectionService.detect_ward(location_text)
    # result.detection_status = "auto-detected" | "manual_required"
    # result.ward_id          = int | None
    # result.locality         = str | None
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.services.ai.gemini_client import get_llm

logger = logging.getLogger(__name__)


# ── Canonical Chennai ward → locality mapping ─────────────────────────────────
# Sourced from frontend/src/lib/constants.ts WARD_NAMES + extended with aliases.
# Structure: locality_alias (lowercase) → ward_id
WARD_MAP: dict[str, Optional[int]] = {
    # Ward 1
    "kathivakkam": 1,
    # Ward 2
    "ennore": 2,
    # Ward 3
    "ernavoor": 3,
    # Ward 4
    "ajax nagar": 4, "ajax": 4,
    # Ward 5
    "tiruvottiyur": 5, "thiruvottiyur": 5,
    # Ward 6
    "kaladipet": 6,
    # Ward 7
    "rajakadai": 7,
    # Ward 8
    "kodungaiyur west": 8, "kodungaiyur (west)": 8,
    # Ward 9
    "kodungaiyur east": 9, "kodungaiyur (east)": 9, "kodungaiyur": 9,
    # Ward 15
    "edyanchavadi": 15,
    # Ward 18
    "manali": 18,
    # Ward 19
    "mathur": 19,
    # Ward 23
    "puzhal": 23,
    # Ward 26
    "madhavaram": 26,
    # Ward 34
    "tondiarpet": 34,
    # Ward 35
    "new washermenpet": 35, "washermenpet": 35,
    # Ward 36
    "old washermenpet": 36,
    # Ward 38
    "perambur": 38,
    # Ward 39
    "vyasarpadi": 39,
    # Ward 43
    "george town": 43, "georgetown": 43,
    # Ward 44
    "broadway": 44,
    # Ward 47
    "sowcarpet": 47, "sowcarpet": 47,
    # Ward 56
    "ayanavaram": 56,
    # Ward 58
    "purasavakkam": 58, "pursawalkam": 58,
    # Ward 60
    "royapuram": 60,
    # Ward 61
    "anna salai": 61, "mount road": 61,
    # Ward 62
    "chepauk": 62,
    # Ward 64
    "kolathur": 64,
    # Ward 67
    "villivakkam": 67,
    # Ward 73
    "thiru vi ka nagar": 73, "thiruvika nagar": 73,
    # Ward 75
    "otteri": 75,
    # Ward 79
    "kilpauk": 79,
    # Ward 88
    "ambattur": 88,
    # Ward 97
    "korattur": 97,
    # Ward 106
    "anna nagar west": 106, "anna nagar": 106,
    # Ward 111
    "aminjikarai": 111,
    # Ward 114
    "chetpet": 114,
    # Ward 115
    "egmore": 115,
    # Ward 118
    "choolaimedu": 118,
    # Ward 129
    "nungambakkam": 129,
    # Ward 131
    "gopalapuram": 131,
    # Ward 132
    "royapettah": 132,
    # Ward 134
    "kodambakkam": 134,
    # Ward 135
    "triplicane": 135,
    # Ward 136
    "t nagar": 136, "t. nagar": 136, "tnagar": 136, "pondy bazaar": 136, "panagal park": 136,
    # Ward 137
    "mylapore": 137,
    # Ward 139
    "alwarpet": 139,
    # Ward 140
    "nandanam": 140,
    # Ward 141
    "r a puram": 141, "r.a. puram": 141, "ra puram": 141,
    # Ward 144
    "west mambalam": 144,
    # Ward 145
    "koyambedu": 145,
    # Ward 146
    "virugambakkam": 146,
    # Ward 150
    "vadapalani": 150,
    # Ward 151
    "kk nagar": 151, "k.k. nagar": 151, "k k nagar": 151,
    # Ward 152
    "ashok nagar": 152,
    # Ward 160
    "alandur": 160,
    # Ward 165
    "adambakkam": 165,
    # Ward 170
    "kotturpuram": 170,
    # Ward 173 / 175
    "adyar": 173,
    # Ward 176
    "besant nagar": 176, "besantnagar": 176,
    # Ward 178
    "thiruvanmiyur": 178,
    # Ward 179
    "velachery": 179, "velacheri": 179,
    # Ward 181
    "perungudi": 181,
    # Ward 192
    "sholinganallur": 192,
    # Ward 195
    "ullagaram": 195,
    # Ward 198
    "madipakkam": 198,
    # Extra common landmarks / areas
    "phoenix mall": 179,         # Phoenix MarketCity is in Velachery
    "forum mall": 179,
    "pallikaranai": 192,
    "thoraipakkam": 192,
    "omr": 192,
    "old mahabalipuram road": 192,
    "ecr": 192,
    "iit madras": 173,
    "iit": 173,
    "guindy": 160,
    "saidapet": 170,
    "little mount": 170,
    "teynampet": 140,
    "thousand lights": 132,
    "spencer plaza": 61,
    "marina beach": 62,
    "marina": 62,
    "nagapattinam": None,   # outside Chennai → will return UNKNOWN
}

# Reverse map: ward_id -> canonical ward name (for display)
WARD_DISPLAY_NAMES: dict[int, str] = {
    1: "Kathivakkam", 2: "Ennore", 3: "Ernavoor", 4: "Ajax", 5: "Tiruvottiyur",
    6: "Kaladipet", 7: "Rajakadai", 8: "Kodungaiyur (West)", 9: "Kodungaiyur (East)",
    15: "Edyanchavadi", 18: "Manali", 19: "Mathur", 23: "Puzhal", 26: "Madhavaram",
    34: "Tondiarpet", 35: "New Washermenpet", 36: "Old Washermenpet",
    38: "Perambur", 39: "Vyasarpadi", 43: "George Town", 44: "Broadway",
    47: "Sowcarpet", 56: "Ayanavaram", 58: "Purasavakkam", 60: "Royapuram",
    61: "Anna Salai", 62: "Chepauk", 64: "Kolathur", 67: "Villivakkam",
    73: "Thiru-Vi-Ka-Nagar", 75: "Otteri", 79: "Kilpauk", 88: "Ambattur",
    97: "Korattur", 106: "Anna Nagar West", 111: "Aminjikarai", 114: "Chetpet",
    115: "Egmore", 118: "Choolaimedu", 129: "Nungambakkam", 131: "Gopalapuram",
    132: "Royapettah", 134: "Kodambakkam", 135: "Triplicane", 136: "T. Nagar",
    137: "Mylapore", 139: "Alwarpet", 140: "Nandanam", 141: "R.A. Puram",
    144: "West Mambalam", 145: "Koyambedu", 146: "Virugambakkam", 150: "Vadapalani",
    151: "K.K. Nagar", 152: "Ashok Nagar", 160: "Alandur", 165: "Adambakkam",
    170: "Kotturpuram", 173: "Adyar", 175: "Adyar", 176: "Besant Nagar",
    178: "Thiruvanmiyur", 179: "Velachery", 181: "Perungudi",
    192: "Sholinganallur", 195: "Ullagaram", 198: "Madipakkam",
}

_GEMINI_PROMPT = """\
You are a Chennai city locality extractor. Given a user's free-text location input, \
extract the single most specific Chennai locality name from it.

Rules:
- Return ONLY the locality name — nothing else, no punctuation, no explanation.
- The locality must be a real neighbourhood, area, or landmark inside Chennai city limits.
- Normalise it to its most commonly known name (e.g. "Velachery", "Adyar", "T. Nagar").
- If the location is clearly outside Chennai (another city/state), return exactly: UNKNOWN
- If the location is too vague to identify a Chennai locality, return exactly: UNKNOWN

Examples:
  Input: "Near phoenix mall velachery"  → Velachery
  Input: "Adyar signal near bridge"     → Adyar
  Input: "Katpadi Vellore"              → UNKNOWN
  Input: "Behind Anna Nagar temple"     → Anna Nagar
  Input: "opp to Koyambedu bus stand"  → Koyambedu
  Input: "Bangalore MG Road"            → UNKNOWN

User input: "{location_text}"
Locality:"""


@dataclass
class WardDetectionResult:
    detection_status: str          # "auto-detected" | "manual_required"
    locality: Optional[str] = None
    ward_id: Optional[int] = None
    ward_name: Optional[str] = None


def _fuzzy_match(locality: str) -> Optional[int]:
    """
    Match a locality name to a ward_id.
    Strategy:
      1. Exact match (lowercase, stripped).
      2. Substring match — locality contained in a key or key in locality.
    Returns ward_id or None.
    """
    loc_lower = locality.lower().strip()

    # 1. Exact match
    if loc_lower in WARD_MAP:
        return WARD_MAP[loc_lower]

    # 2. Substring match — check both directions
    for key, ward in WARD_MAP.items():
        if key in loc_lower or loc_lower in key:
            return ward

    # 3. Word-overlap fallback — at least one significant word in common
    loc_words = set(w for w in loc_lower.split() if len(w) > 3)
    for key, ward in WARD_MAP.items():
        key_words = set(w for w in key.split() if len(w) > 3)
        if loc_words & key_words:  # non-empty intersection
            return ward

    return None


class WardDetectionService:

    @staticmethod
    async def detect_ward(location_text: str) -> WardDetectionResult:
        """
        Main entry-point.
        1. Use Gemini Flash to extract a clean Chennai locality from raw user input.
        2. Map that locality to a ward_id using fuzzy matching.
        3. Return WardDetectionResult.
        """
        if not location_text or len(location_text.strip()) < 3:
            return WardDetectionResult(detection_status="manual_required")

        # ── Step 1: Gemini locality extraction ───────────────────────────────
        locality: Optional[str] = None
        try:
            llm = get_llm()
            prompt = _GEMINI_PROMPT.format(location_text=location_text.strip())
            response = await llm.ainvoke(prompt)
            raw = str(response.content).strip()

            # Take only the first line / first word(s) — model should be concise
            first_line = raw.splitlines()[0].strip()
            # Remove leading label if model echoes it (e.g. "Locality: Adyar")
            if ":" in first_line:
                first_line = first_line.split(":", 1)[-1].strip()
            locality = first_line if first_line and first_line.upper() != "UNKNOWN" else None

            logger.info("Gemini extracted locality '%s' from '%s'", locality, location_text)
        except Exception as exc:
            logger.warning("Gemini ward extraction failed: %s — falling back to direct fuzzy match.", exc)
            # If Gemini fails, try to directly fuzzy-match the raw input
            locality = location_text

        if not locality:
            return WardDetectionResult(detection_status="manual_required")

        # ── Step 2: Fuzzy ward mapping ────────────────────────────────────────
        ward_id = _fuzzy_match(locality)

        if ward_id is None:
            # One more attempt: directly match the raw user input if locality ≠ user input
            if locality.lower() != location_text.lower():
                ward_id = _fuzzy_match(location_text)

        if ward_id is None:
            return WardDetectionResult(
                detection_status="manual_required",
                locality=locality,
            )

        ward_name = WARD_DISPLAY_NAMES.get(ward_id, f"Ward {ward_id}")
        return WardDetectionResult(
            detection_status="auto-detected",
            locality=locality,
            ward_id=ward_id,
            ward_name=ward_name,
        )
