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

    # ── Prayagraj Nagar Nigam Wards (IDs 1001–1100) ──────────────────────────────
    # Each key is the locality/neighbourhood name — NO city-level keys like
    # "prayagraj" or "allahabad" (they are too broad and cause false matches).
    "mahewa": 1001,
    "sulem sarai": 1002, "sulemsarai": 1002,
    "bamhrouli": 1003, "bamhrouli uparhar": 1003,
    "nibi taluka": 1004, "nibi": 1004,
    "pipalgaon": 1005,
    "kanihar": 1006,
    "rajapur allahabad": 1007,
    "tenduavan": 1008,
    "sonauti": 1009,
    "gohri": 1010,
    "amarsapur": 1011,
    "malakraj": 1013,
    "bhadri": 1014,
    "jayantipur": 1015,
    "bahmalpur": 1016,
    "chaka allahabad": 1017,
    "harwara": 1018,
    "andawa": 1019,
    "chak raghunath": 1020,
    "myorabad": 1021,
    "baswar": 1022,
    "sadiyabad": 1023,
    "swaraj nagar prayagraj": 1024,
    "malawa buzurg": 1025, "malawa": 1025,
    "civil lines first": 1026,
    "salori": 1027,
    "jhulelal nagar": 1028, "jhulelal": 1028,
    "mohabbatganj": 1029,
    "jahangirabad": 1031,
    "alenganj": 1032,
    "lavayan": 1033,
    "shivkuti": 1034,
    "jhalwa": 1035,
    "madhwapur": 1036,
    "shantipuram": 1037,
    "baghambari": 1038, "baghambari housing": 1038,
    "malak harhar": 1039,
    "naini dadri": 1040, "naini": 1040,
    "mamfordganj": 1041,
    "azad square": 1043,
    "chakiya": 1044,
    "chhatnag": 1045,
    "pura padain": 1046,
    "arail": 1047,
    "alopi bagh": 1048, "alopibagh": 1048,
    "katka": 1050,
    "mundera": 1051,
    "haweliya": 1052,
    "chak niratul": 1053,
    "rajruppur": 1054,
    # Ward 55 — Teliarganj (MNNIT)
    "teliarganj": 1055, "teliyarganj": 1055,
    "mnnit": 1055, "mnmit": 1055, "mnnit allahabad": 1055, "mnnit prayagraj": 1055,
    # Ward 56 — Fafamau / Phaphamau
    "fafamau": 1056, "phaphamau": 1056,
    "kashiraj nagar": 1057,
    "civil lines second": 1058,
    "neem sarai": 1059,
    "minhajpur": 1060, "minhajpur gadhikala": 1060,
    "colonelganj": 1061, "colonelgunj": 1061,
    "nai basti": 1062,
    "purana katra": 1063,
    "mehandauree": 1064,
    "tagore town": 1065,
    "chak dondi": 1066,
    "kazipur": 1067,
    "nyay marg": 1068,
    "bharadwajpuram": 1069,
    "mavaiya": 1070,
    "govindpur": 1072,
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
        1001: "Ward 1 - Mahewa (Prayagraj)",
    1002: "Ward 2 - Sulem Sarai (Prayagraj)",
    1003: "Ward 3 - Bamhrouli Uparhar (Prayagraj)",
    1004: "Ward 4 - Nibi Taluka Khurd (Prayagraj)",
    1005: "Ward 5 - Pipalgaon (Prayagraj)",
    1006: "Ward 6 - Kanihar (Prayagraj)",
    1007: "Ward 7 - Rajapur (Prayagraj)",
    1008: "Ward 8 - Tenduavan (Prayagraj)",
    1009: "Ward 9 - Sonauti (Prayagraj)",
    1010: "Ward 10 - Gohri (Prayagraj)",
    1011: "Ward 11 - Amarsapur (Prayagraj)",
    1012: "Ward 12 - Ashok Nagar (Prayagraj)",
    1013: "Ward 13 - Malakraj (Prayagraj)",
    1014: "Ward 14 - Bhadri (Prayagraj)",
    1015: "Ward 15 - Jayantipur (Prayagraj)",
    1016: "Ward 16 - Bahmalpur (Prayagraj)",
    1017: "Ward 17 - Chaka (Prayagraj)",
    1018: "Ward 18 - Harwara (Prayagraj)",
    1019: "Ward 19 - Andawa (Prayagraj)",
    1020: "Ward 20 - Chak Raghunath (Prayagraj)",
    1021: "Ward 21 - Myorabad (Prayagraj)",
    1022: "Ward 22 - Baswar (Prayagraj)",
    1023: "Ward 23 - Sadiyabad (Prayagraj)",
    1024: "Ward 24 - Swaraj Nagar (Prayagraj)",
    1025: "Ward 25 - Malawa Buzurg (Prayagraj)",
    1026: "Ward 26 - Civil Lines First (Prayagraj)",
    1027: "Ward 27 - Salori (Prayagraj)",
    1028: "Ward 28 - Jhulelal Nagar (Prayagraj)",
    1029: "Ward 29 - Mohabbatganj (Prayagraj)",
    1030: "Ward 30 - Krishna Nagar (Prayagraj)",
    1031: "Ward 31 - Jahangirabad (Prayagraj)",
    1032: "Ward 32 - Alenganj (Prayagraj)",
    1033: "Ward 33 - Lavayan (Prayagraj)",
    1034: "Ward 34 - Shivkuti (Prayagraj)",
    1035: "Ward 35 - Jhalwa (Prayagraj)",
    1036: "Ward 36 - Madhwapur (Prayagraj)",
    1037: "Ward 37 - Shantipuram (Prayagraj)",
    1038: "Ward 38 - Baghambari Housing Scheme (Prayagraj)",
    1039: "Ward 39 - Malak Harhar (Prayagraj)",
    1040: "Ward 40 - Naini Dadri (Prayagraj)",
    1041: "Ward 41 - Mamfordganj (Prayagraj)",
    1042: "Ward 42 - Ganga Nagar (Prayagraj)",
    1043: "Ward 43 - Azad Square (Prayagraj)",
    1044: "Ward 44 - Chakiya (Prayagraj)",
    1045: "Ward 45 - Chhatnag (Prayagraj)",
    1046: "Ward 46 - Pura Padain (Prayagraj)",
    1047: "Ward 47 - Arail (Prayagraj)",
    1048: "Ward 48 - Alopi Bagh (Prayagraj)",
    1049: "Ward 49 - Transport Nagar (Prayagraj)",
    1050: "Ward 50 - Katka (Prayagraj)",
    1051: "Ward 51 - Mundera (Prayagraj)",
    1052: "Ward 52 - Haweliya (Prayagraj)",
    1053: "Ward 53 - Chak Niratul (Prayagraj)",
    1054: "Ward 54 - Rajruppur (Prayagraj)",
    1055: "Ward 55 - Teliarganj (Prayagraj)",
    1056: "Ward 56 - Fafamau (Prayagraj)",
    1057: "Ward 57 - Kashiraj Nagar (Prayagraj)",
    1058: "Ward 58 - Civil Lines Second (Prayagraj)",
    1059: "Ward 59 - Neem Sarai (Prayagraj)",
    1060: "Ward 60 - Minhajpur Gadhikala (Prayagraj)",
    1061: "Ward 61 - Colonelganj (Prayagraj)",
    1062: "Ward 62 - Nai Basti (Prayagraj)",
    1063: "Ward 63 - Purana Katra (Prayagraj)",
    1064: "Ward 64 - Mehandauree (Prayagraj)",
    1065: "Ward 65 - Tagore Town (Prayagraj)",
    1066: "Ward 66 - Chak Dondi (Prayagraj)",
    1067: "Ward 67 - Kazipur (Prayagraj)",
    1068: "Ward 68 - Nyay Marg Kshetra (Prayagraj)",
    1069: "Ward 69 - Bharadwajpuram (Prayagraj)",
    1070: "Ward 70 - Mavaiya (Prayagraj)",
    1071: "Ward 71 - Omprakash Sabhasad Nagar (Prayagraj)",
    1072: "Ward 72 - Govindpur (Prayagraj)",
    1073: "Ward 73 - Prayagraj Ward 73 (Prayagraj)",
    1074: "Ward 74 - Prayagraj Ward 74 (Prayagraj)",
    1075: "Ward 75 - Prayagraj Ward 75 (Prayagraj)",
    1076: "Ward 76 - Prayagraj Ward 76 (Prayagraj)",
    1077: "Ward 77 - Prayagraj Ward 77 (Prayagraj)",
    1078: "Ward 78 - Prayagraj Ward 78 (Prayagraj)",
    1079: "Ward 79 - Prayagraj Ward 79 (Prayagraj)",
    1080: "Ward 80 - Prayagraj Ward 80 (Prayagraj)",
    1081: "Ward 81 - Prayagraj Ward 81 (Prayagraj)",
    1082: "Ward 82 - Prayagraj Ward 82 (Prayagraj)",
    1083: "Ward 83 - Prayagraj Ward 83 (Prayagraj)",
    1084: "Ward 84 - Prayagraj Ward 84 (Prayagraj)",
    1085: "Ward 85 - Prayagraj Ward 85 (Prayagraj)",
    1086: "Ward 86 - Prayagraj Ward 86 (Prayagraj)",
    1087: "Ward 87 - Prayagraj Ward 87 (Prayagraj)",
    1088: "Ward 88 - Prayagraj Ward 88 (Prayagraj)",
    1089: "Ward 89 - Prayagraj Ward 89 (Prayagraj)",
    1090: "Ward 90 - Prayagraj Ward 90 (Prayagraj)",
    1091: "Ward 91 - Prayagraj Ward 91 (Prayagraj)",
    1092: "Ward 92 - Prayagraj Ward 92 (Prayagraj)",
    1093: "Ward 93 - Prayagraj Ward 93 (Prayagraj)",
    1094: "Ward 94 - Prayagraj Ward 94 (Prayagraj)",
    1095: "Ward 95 - Prayagraj Ward 95 (Prayagraj)",
    1096: "Ward 96 - Prayagraj Ward 96 (Prayagraj)",
    1097: "Ward 97 - Prayagraj Ward 97 (Prayagraj)",
    1098: "Ward 98 - Prayagraj Ward 98 (Prayagraj)",
    1099: "Ward 99 - Prayagraj Ward 99 (Prayagraj)",
    1100: "Ward 100 - Prayagraj Ward 100 (Prayagraj)",
}

_GEMINI_PROMPT = """\
You are an Indian city locality extractor. Given a user's free-text location input, \
extract the single most specific locality, neighbourhood, area, or landmark name from it.

Rules:
- Return ONLY the locality name — nothing else, no punctuation, no explanation.
- Normalise it to its most commonly known name (e.g. "Velachery", "Adyar", "Teliarganj", "Civil Lines").
- The locality must be a real neighbourhood, area, landmark, or institution name.
- If the input is too vague or contains no usable locality (only a country/state name), return exactly: UNKNOWN
- Do NOT return UNKNOWN just because the city is not Chennai. All Indian cities are valid.

Examples:
  Input: "Near phoenix mall velachery"      → Velachery
  Input: "Adyar signal near bridge"         → Adyar
  Input: "MNNIT teliarganj prayagraj"       → Teliarganj
  Input: "MNNIT teliarganj allahabad"       → Teliarganj
  Input: "Civil Lines Allahabad"            → Civil Lines
  Input: "Behind Anna Nagar temple"         → Anna Nagar
  Input: "opp to Koyambedu bus stand"       → Koyambedu
  Input: "Bangalore MG Road"               → MG Road
  Input: "India"                            → UNKNOWN

User input: "{location_text}"
Locality"""


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
      3. Word-overlap fallback — at least one significant word in common.
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
        1. Always try a direct fuzzy match on the raw input first (fast path).
        2. Use Gemini Flash to extract a clean locality from raw user input.
        3. Map that locality to a ward_id using fuzzy matching.
        4. Return WardDetectionResult.
        """
        if not location_text or len(location_text.strip()) < 3:
            return WardDetectionResult(detection_status="manual_required")

        # ── Step 0: Fast-path — try raw input directly ────────────────────────
        fast_ward = _fuzzy_match(location_text)
        if fast_ward is not None:
            ward_name = WARD_DISPLAY_NAMES.get(fast_ward, f"Ward {fast_ward}")
            logger.info("Fast-path matched '%s' → ward_id=%s", location_text, fast_ward)
            return WardDetectionResult(
                detection_status="auto-detected",
                locality=location_text.strip(),
                ward_id=fast_ward,
                ward_name=ward_name,
            )

        # ── Step 1: Gemini locality extraction ───────────────────────────────
        locality: Optional[str] = None
        try:
            llm = get_llm()
            prompt = _GEMINI_PROMPT.format(location_text=location_text.strip())
            response = await llm.ainvoke(prompt)
            raw = str(response.content).strip()

            # Take only the first line — model should be concise
            first_line = raw.splitlines()[0].strip()
            # Remove leading label if model echoes it (e.g. "Locality: Adyar")
            if ":" in first_line:
                first_line = first_line.split(":", 1)[-1].strip()
            locality = first_line if first_line and first_line.upper() != "UNKNOWN" else None

            logger.info("Gemini extracted locality '%s' from '%s'", locality, location_text)
        except Exception as exc:
            logger.warning("Gemini ward extraction failed: %s — falling back to direct fuzzy match.", exc)
            locality = location_text

        # ── Step 2: Fuzzy ward mapping ────────────────────────────────────────
        ward_id: Optional[int] = None

        if locality:
            ward_id = _fuzzy_match(locality)

        # Final fallback: try raw input if Gemini returned UNKNOWN or a different locality
        if ward_id is None:
            ward_id = _fuzzy_match(location_text)

        if ward_id is None:
            return WardDetectionResult(
                detection_status="manual_required",
                locality=locality,
            )

        ward_name = WARD_DISPLAY_NAMES.get(ward_id, f"Ward {ward_id}")
        return WardDetectionResult(
            detection_status="auto-detected",
            locality=locality or location_text.strip(),
            ward_id=ward_id,
            ward_name=ward_name,
        )
