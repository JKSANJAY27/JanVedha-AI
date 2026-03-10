"""
Synthetic training data generator for JanVedha civic complaint classifier.

Generates high-quality multilingual training data across 8 Indian languages
and 14 departments using NVIDIA NIM API (OpenAI-compatible).

Strategy:
  - 2 departments per API call (higher quality outputs)
  - 4 rotating persona/tone templates for diversity
  - 8 languages × 7 batches × 4 personas = 224 API calls
  - Post-processing: dedup, length filter, dept-name leak filter
  - Target: ~3,000+ examples in ~20 min

Usage:
    python training/generate_data.py
    python training/generate_data.py --examples-per-dept 30 --model moonshotai/kimi-k2.5
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── Load .env ──────────────────────────────────────────────────────────────
# Check backend/.env first, then root .env
_SCRIPT_DIR = Path(__file__).resolve().parent          # training/
_BACKEND_DIR = _SCRIPT_DIR.parent                       # backend/
_ROOT_DIR = _BACKEND_DIR.parent                         # project root

for env_path in [_BACKEND_DIR / ".env", _ROOT_DIR / ".env"]:
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

GEMINI_API_KEY = os.getenv("GEMINI_DATA_KEY", "") or os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    sys.exit("❌  GEMINI_DATA_KEY / GEMINI_API_KEY not set in .env — cannot generate data.")

# ── Department catalogue ───────────────────────────────────────────────────
DEPARTMENTS = {
    "D01": "Roads & Bridges",
    "D02": "Buildings & Planning",
    "D03": "Water Supply",
    "D04": "Sewage & Drainage",
    "D05": "Solid Waste Management",
    "D06": "Street Lighting",
    "D07": "Parks & Greenery",
    "D08": "Health & Sanitation",
    "D09": "Fire & Emergency",
    "D10": "Traffic & Transport",
    "D11": "Revenue & Property",
    "D12": "Social Welfare",
    "D13": "Education",
    "D14": "Disaster Management",
}

# Lower-cased department names for leak detection
_DEPT_NAMES_LOWER = {name.lower() for name in DEPARTMENTS.values()}

# ── Languages ──────────────────────────────────────────────────────────────
LANGUAGES = {
    "en":    "English",
    "hi":    "Hindi in Devanagari script (e.g. सड़क पर गड्ढा है, कचरा नहीं उठाया जा रहा)",
    "hi-en": "Hinglish — romanised Hindi mixed with English words (e.g. 'Road pe bahut bada gaddha hai, kab theek hoga?', 'Kachra nahi utha rahe colony mein')",
    "ta":    "Tamil in Tamil script (e.g. சாலையில் பள்ளம் உள்ளது, குடிநீர் வரவில்லை)",
    "bn":    "Bengali in Bengali script (e.g. রাস্তায় বড় গর্ত আছে, জল আসছে না)",
    "mr":    "Marathi in Devanagari script (e.g. रस्त्यावर खड्डा आहे, पाणी येत नाही)",
    "te":    "Telugu in Telugu script (e.g. రోడ్డు మీద గుంట ఉంది, నీరు రావడం లేదు)",
    "kn":    "Kannada in Kannada script (e.g. ರಸ್ತೆಯಲ್ಲಿ ಗುಂಡಿ ಇದೆ, ನೀರು ಬರುತ್ತಿಲ್ಲ)",
}

# ── Persona templates for diversity ────────────────────────────────────────
PERSONAS = {
    "angry_citizen": (
        "Tone: ANGRY and frustrated citizen. Use exclamation marks, express "
        "urgency, demand action. Examples of tone: 'When will you fix this?!', "
        "'It's been 3 weeks and nobody cares!', 'This is unacceptable!'"
    ),
    "formal_report": (
        "Tone: Polite and formal, like an official written complaint. Use "
        "structured sentences. Examples of tone: 'I wish to bring to your "
        "attention that...', 'Kindly look into this matter at the earliest.'"
    ),
    "casual_mobile": (
        "Tone: Very casual and informal, like a WhatsApp message typed quickly "
        "on a phone. Short sentences, abbreviations OK, minor typos realistic. "
        "Examples: 'bro the road near my house totally broken', 'light nhi aa rha 2 din se'"
    ),
    "elderly_simple": (
        "Tone: Simple vocabulary, basic sentence structure, as if spoken by an "
        "elderly person with limited tech literacy. Short, direct statements. "
        "Examples: 'Water not coming since yesterday', 'Road has big hole near temple'"
    ),
}

DEPT_BATCH_SIZE = 2    # departments per API call
DEFAULT_MODEL = "gemini-2.0-flash"


# ── API helpers ────────────────────────────────────────────────────────────

def _get_client():
    from openai import OpenAI
    return OpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=GEMINI_API_KEY,
        timeout=120,
        max_retries=0,
    )


def build_prompt(lang_desc: str, batch: dict[str, str], n: int, persona_desc: str) -> str:
    dept_lines = "\n".join(f'  "{did}": "{name}"' for did, name in batch.items())
    return f"""Generate exactly {n} civic complaint messages for each department below.

Departments:
{dept_lines}

Language: {lang_desc}
{persona_desc}

Rules:
- Each complaint is 1-3 sentences, as if typed by a real citizen on a mobile phone.
- Include fictional but realistic Indian location names (colony names, street names, area names, ward numbers).
- Do NOT mention the department name, department ID, or category name inside the complaint text.
- Vary the specific sub-issues within each department (e.g. for Roads: pothole, cracked pavement, missing railing, broken speed bump, etc.)
- For native-script languages, use the ACTUAL script (Devanagari, Tamil, Bengali, Telugu, Kannada) — not romanisation.
- For Hinglish, use Roman script with natural Hindi-English mixing.

Output ONLY this JSON (no markdown fences, no explanation):
{{
{chr(10).join(f'  "{did}": ["complaint_1", "complaint_2", ...],' for did in batch)}
}}"""


def call_api(client, model: str, prompt: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content":
                     "You are a JSON dataset generator. Output ONLY valid JSON. "
                     "No markdown fences, no explanation, no extra text."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9,
                max_tokens=2000,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            wait = 5 * (2 ** attempt)
            logger.warning(
                "    Attempt %d/%d failed: %s — waiting %ds…",
                attempt + 1, retries, exc, wait,
            )
            if attempt < retries - 1:
                time.sleep(wait)
    return "{}"


def extract_json(raw: str) -> dict:
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip()).strip("`").strip()
    match = re.search(r"(\{[\s\S]*\})", raw)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {}


# ── Core generation ────────────────────────────────────────────────────────

def batches_of(d: dict, size: int):
    items = list(d.items())
    for i in range(0, len(items), size):
        yield dict(items[i : i + size])


def generate_all(model: str, examples_per_dept: int) -> list[dict]:
    client = _get_client()
    all_records: list[dict] = []

    dept_batches = list(batches_of(DEPARTMENTS, DEPT_BATCH_SIZE))
    persona_keys = list(PERSONAS.keys())

    # Each (language, dept_batch) pair gets a rotating persona
    total_calls = len(LANGUAGES) * len(dept_batches)
    call_n = 0
    persona_idx = 0

    for lang, lang_desc in LANGUAGES.items():
        for batch_idx, batch in enumerate(dept_batches, 1):
            call_n += 1
            persona_key = persona_keys[persona_idx % len(persona_keys)]
            persona_desc = PERSONAS[persona_key]
            persona_idx += 1

            dept_names_str = ", ".join(batch.values())
            logger.info(
                "[%d/%d] %s | batch %d | %s — %s",
                call_n, total_calls, lang, batch_idx, persona_key, dept_names_str,
            )

            prompt = build_prompt(lang_desc, batch, examples_per_dept, persona_desc)
            raw = call_api(client, model, prompt)
            data = extract_json(raw)

            batch_count = 0
            for dept_id, dept_name in batch.items():
                texts = data.get(dept_id, [])
                if not isinstance(texts, list):
                    texts = []
                for text in texts[:examples_per_dept]:
                    text = str(text).strip()
                    if len(text) >= 15:
                        all_records.append({
                            "text": text,
                            "dept_id": dept_id,
                            "dept_name": dept_name,
                            "language": lang,
                        })
                        batch_count += 1

            logger.info("   → %d records", batch_count)
            time.sleep(0.5)  # rate limiting

    return all_records


# ── Post-processing ────────────────────────────────────────────────────────

def postprocess(records: list[dict]) -> list[dict]:
    """Filter out bad examples."""
    original = len(records)

    # 1. Remove too-short
    records = [r for r in records if len(r["text"]) >= 15]

    # 2. Remove exact duplicates
    seen_texts: set[str] = set()
    deduped = []
    for r in records:
        if r["text"] not in seen_texts:
            seen_texts.add(r["text"])
            deduped.append(r)
    records = deduped

    # 3. Remove near-duplicates (same first 50 chars)
    seen_prefix: set[str] = set()
    unique = []
    for r in records:
        prefix = r["text"][:50].lower().strip()
        if prefix not in seen_prefix:
            seen_prefix.add(prefix)
            unique.append(r)
    records = unique

    # 4. Remove dept name leaks (complaint text literally contains dept name)
    clean = []
    for r in records:
        text_lower = r["text"].lower()
        leaked = any(dname in text_lower for dname in _DEPT_NAMES_LOWER)
        if not leaked:
            clean.append(r)
    records = clean

    logger.info(
        "Post-processing: %d → %d records (removed %d)",
        original, len(records), original - len(records),
    )
    return records


# ── Main ───────────────────────────────────────────────────────────────────

def main(examples_per_dept: int, output: str, val_ratio: float, model: str) -> None:
    out_path = Path(output)
    val_out_path = out_path.with_name(out_path.stem + "_val.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    expected = len(DEPARTMENTS) * len(LANGUAGES) * examples_per_dept
    logger.info("Model     : %s", model)
    logger.info("Examples  : %d per (dept × language)", examples_per_dept)
    logger.info("Languages : %d", len(LANGUAGES))
    logger.info("Personas  : %d (rotating)", len(PERSONAS))
    logger.info("Expected  : ~%d records total (before filtering)", expected)
    logger.info("")

    all_records = generate_all(model, examples_per_dept)
    all_records = postprocess(all_records)

    # Shuffle and split
    random.shuffle(all_records)
    split_at = int(len(all_records) * (1 - val_ratio))
    train_recs = all_records[:split_at]
    val_recs = all_records[split_at:]

    # Write JSONL
    out_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in train_recs) + "\n",
        encoding="utf-8",
    )
    val_out_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in val_recs) + "\n",
        encoding="utf-8",
    )

    # ── Summary ────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("🎉  Done!")
    logger.info("   Train : %d → %s", len(train_recs), out_path)
    logger.info("   Val   : %d → %s", len(val_recs), val_out_path)

    logger.info("")
    logger.info("Per-department counts:")
    for dept_id, dept_name in DEPARTMENTS.items():
        count = sum(1 for r in all_records if r["dept_id"] == dept_id)
        logger.info("  %s  %-30s  %d", dept_id, dept_name, count)

    logger.info("")
    logger.info("Per-language counts:")
    lang_counts = Counter(r["language"] for r in all_records)
    for lang, count in sorted(lang_counts.items()):
        logger.info("  %-6s  %d", lang, count)

    # Warn about gaps
    logger.info("")
    for dept_id in DEPARTMENTS:
        for lang in LANGUAGES:
            pair_count = sum(
                1 for r in all_records
                if r["dept_id"] == dept_id and r["language"] == lang
            )
            if pair_count < 5:
                logger.warning(
                    "⚠️  Low data: %s × %s = only %d examples",
                    dept_id, lang, pair_count,
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic training data for JanVedha civic classifier"
    )
    parser.add_argument(
        "--examples-per-dept", type=int, default=25,
        help="Examples per department per language per call (default: 25)",
    )
    parser.add_argument(
        "--output", default="training/data/synthetic_train.jsonl",
        help="Output JSONL path (default: training/data/synthetic_train.jsonl)",
    )
    parser.add_argument(
        "--val-ratio", type=float, default=0.15,
        help="Validation split ratio (default: 0.15)",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"NVIDIA NIM model (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()
    main(args.examples_per_dept, args.output, args.val_ratio, args.model)
