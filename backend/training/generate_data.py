"""
Synthetic training data generator for JanVedha civic classifier.

Strategy: 4 departments per call (small, fast, avoids NVIDIA NIM timeouts).
          Uses kimi-k2-instruct (stable) with streaming.
          6 languages × 4 batches = 24 API calls → ~840 examples in ~10 min.

Usage:
    python training/generate_data.py
    python training/generate_data.py --examples-per-dept 10 --model moonshotai/kimi-k2.5
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
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ── Load .env ──────────────────────────────────────────────────────────────
_ENV = Path(__file__).resolve().parents[2] / ".env"
if _ENV.exists():
    for line in _ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
if not NVIDIA_API_KEY:
    sys.exit("❌  NVIDIA_API_KEY not set in .env")

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

LANGUAGES = {
    "en":    "English",
    "hi":    "Hindi in Devanagari script (e.g. सड़क पर गड्ढा है)",
    "hi-en": "Hinglish — romanised Hindi + English (e.g. 'Road pe gaddha hai, kab theek hoga?')",
    "ta":    "Tamil in Tamil script (e.g. சாலையில் பள்ளம்)",
    "bn":    "Bengali in Bengali script (e.g. রাস্তায় গর্ত আছে)",
    "mr":    "Marathi in Devanagari script (e.g. रस्त्यावर खड्डा आहे)",
}

DEPT_BATCH_SIZE = 4   # departments per API call (keeps output < 800 tokens)
DEFAULT_MODEL   = "moonshotai/kimi-k2-instruct"   # stable; kimi-k2.5 also works


def build_user_prompt(lang_desc: str, batch: dict[str, str], n: int) -> str:
    dept_lines = "\n".join(f'  "{did}": "{name}"' for did, name in batch.items())
    return f"""Generate exactly {n} civic complaint messages in {lang_desc} for each department below.

{dept_lines}

Rules:
- 1-2 sentences each, as a mobile-app citizen complaint.
- Vary urgency, tone, location hints (fictional colony/street names OK).
- Language: {lang_desc} — use the actual script (not romanisation) for native scripts.
- Do NOT mention the department name or ID inside the complaint text.

Output ONLY this JSON (no explanation):
{{
{chr(10).join(f'  "{did}": ["complaint_1", "complaint_2", ...],' for did in batch)}
}}"""


def call_api(model: str, prompt: str, timeout: int = 120, retries: int = 3) -> str:
    from openai import OpenAI
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY,
        timeout=timeout,
        max_retries=0,   # we handle retries ourselves
    )
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content":
                     "You are a JSON dataset generator. Output only valid JSON. No markdown, no explanation."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9,
                max_tokens=1500,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            wait = 5 * (2 ** attempt)
            logger.warning("    Attempt %d/%d failed: %s — waiting %ds…", attempt + 1, retries, exc, wait)
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


def batches_of(d: dict, size: int):
    items = list(d.items())
    for i in range(0, len(items), size):
        yield dict(items[i:i + size])


def generate_all(model: str, examples_per_dept: int) -> list[dict]:
    all_records: list[dict] = []
    dept_batches = list(batches_of(DEPARTMENTS, DEPT_BATCH_SIZE))
    total_calls  = len(LANGUAGES) * len(dept_batches)
    call_n       = 0

    for lang, lang_desc in LANGUAGES.items():
        for batch_idx, batch in enumerate(dept_batches, 1):
            call_n += 1
            dept_names = ", ".join(batch.values())
            logger.info("[%d/%d] %s | batch %d — %s", call_n, total_calls, lang, batch_idx, dept_names)

            prompt = build_user_prompt(lang_desc, batch, examples_per_dept)
            raw    = call_api(model, prompt)
            data   = extract_json(raw)

            batch_records = 0
            for dept_id, dept_name in batch.items():
                texts = data.get(dept_id, [])
                if not isinstance(texts, list):
                    texts = []
                for text in texts[:examples_per_dept]:
                    text = str(text).strip()
                    if len(text) >= 5:
                        all_records.append({
                            "text":      text,
                            "dept_id":   dept_id,
                            "dept_name": dept_name,
                            "language":  lang,
                        })
                        batch_records += 1

            logger.info("   → %d records", batch_records)
            time.sleep(0.5)  # gentle rate limiting

    return all_records


def main(examples_per_dept: int, output: str, val_ratio: float, model: str) -> None:
    out_path     = Path(output)
    val_out_path = out_path.with_name(out_path.stem + "_val.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Model    : %s", model)
    logger.info("Examples : %d per (dept × language)", examples_per_dept)
    logger.info("Expected : ~%d records total", len(DEPARTMENTS) * len(LANGUAGES) * examples_per_dept)

    all_records = generate_all(model, examples_per_dept)

    random.shuffle(all_records)
    split_at   = int(len(all_records) * (1 - val_ratio))
    train_recs = all_records[:split_at]
    val_recs   = all_records[split_at:]

    out_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in train_recs) + "\n",
                        encoding="utf-8")
    val_out_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in val_recs) + "\n",
                            encoding="utf-8")

    logger.info("\n🎉  Done!")
    logger.info("   Train : %d → %s", len(train_recs), out_path)
    logger.info("   Val   : %d → %s", len(val_recs),   val_out_path)
    logger.info("\n   Per-department counts:")
    for dept_id, dept_name in DEPARTMENTS.items():
        count = sum(1 for r in all_records if r["dept_id"] == dept_id)
        logger.info("     %s  %-30s  %d", dept_id, dept_name, count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--examples-per-dept", type=int, default=10)
    parser.add_argument("--output",            default="training/data/synthetic_train.jsonl")
    parser.add_argument("--val-ratio",          type=float, default=0.15)
    parser.add_argument("--model",             default=DEFAULT_MODEL,
                        help="NVIDIA NIM model (default: moonshotai/kimi-k2-instruct)")
    args = parser.parse_args()
    main(args.examples_per_dept, args.output, args.val_ratio, args.model)
