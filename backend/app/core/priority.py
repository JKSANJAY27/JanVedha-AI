SEVERITY_MAP = {
    "street_light_out": 15, "multiple_lights_out": 22,
    "electrical_spark_hazard": 30,
    "small_pothole": 12, "large_pothole": 20,
    "road_collapse": 28, "bridge_crack": 30,
    "low_pressure": 14, "no_water_supply": 22,
    "dirty_water": 25, "burst_pipe_flooding": 30,
    "drain_blocked": 18, "sewage_overflow": 26, "open_manhole": 30,
    "missed_collection_once": 10, "overflowing_bin": 16,
    "dead_animal_carcass": 22, "illegal_dumping_large": 20,
    "mosquito_breeding": 18, "stray_dog_bite": 28,
    "disease_outbreak_concern": 30,
    "default": 15
}

SAFETY_KEYWORDS = [
    "accident", "danger", "hazard", "fire", "electric shock",
    "child fell", "injury", "death", "hospital", "emergency",
    "flood", "collapse", "snake", "rabies", "epidemic",
    "விபத்து", "ஆபத்து", "आग", "खतरा", "ప్రమాదం"
]

DEPT_SLA_DAYS = {
    "D01": 3, "D02": 14, "D03": 5, "D04": 3, "D05": 2,
    "D06": 7, "D07": 30, "D08": 5, "D09": 1, "D10": 1,
    "D11": 21, "D12": 7, "D13": 14, "D14": 1
}

def calculate_priority_score(
    subcategory: str,
    report_count: int,
    location_type: str,
    days_open: int,
    hours_until_sla_breach: float,
    social_media_mentions: int,
    description: str
) -> tuple[float, str]:
    """
    Returns (score: float 0-100, label: str CRITICAL/HIGH/MEDIUM/LOW)
    Pure function. No side effects. No DB calls. No external calls.
    """
    # Factor 1: Base severity (0-30)
    base = SEVERITY_MAP.get(subcategory, SEVERITY_MAP["default"])
    safety_bonus = 5 if any(kw.lower() in description.lower() for kw in SAFETY_KEYWORDS) else 0
    severity = min(30, base + safety_bonus)

    # Factor 2: Population impact (0-25)
    location_scores = {
        "main_road": 10, "hospital_vicinity": 10, "school_vicinity": 9,
        "market": 8, "residential": 5, "internal_street": 3, "unknown": 4
    }
    impact = min(15, report_count * 3) + location_scores.get(location_type, 4)

    # Factor 3: Time decay (0-20)
    if days_open <= 1: time_score = 0
    elif days_open <= 3: time_score = 5
    elif days_open <= 7: time_score = 10
    elif days_open <= 14: time_score = 15
    else: time_score = 20

    # Factor 4: SLA breach proximity (0-15)
    if hours_until_sla_breach <= 0: sla_score = 15
    elif hours_until_sla_breach <= 6: sla_score = 12
    elif hours_until_sla_breach <= 24: sla_score = 8
    elif hours_until_sla_breach <= 48: sla_score = 4
    else: sla_score = 0

    # Factor 5: Social amplification (0-10)
    if social_media_mentions > 100: social_score = 10
    elif social_media_mentions > 50: social_score = 7
    elif social_media_mentions > 10: social_score = 4
    else: social_score = 0

    score = min(100.0, severity + impact + time_score + sla_score + social_score)

    if score >= 80: label = "CRITICAL"
    elif score >= 60: label = "HIGH"
    elif score >= 35: label = "MEDIUM"
    else: label = "LOW"

    return round(score, 2), label
