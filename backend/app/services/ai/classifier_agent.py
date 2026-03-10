"""
ClassifierAgent

Classifies a civic complaint into a department.

Layer 1 (Primary):  IndicBERTv2-MLM-Sam-TLM (fine-tuned) OR mDeBERTa-v3-base-mnli-xnli (zero-shot)
Layer 2 (Fallback): Sarvam-M via NVIDIA NIM API (free key, OpenAI-compatible)
                    — best for Hinglish / romanised Indian text (low confidence cases)
Layer 3 (Last):     Keyword matching — always works, zero dependencies
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Paths
_BACKEND_DIR        = Path(__file__).resolve().parents[3]  # backend/
_FINETUNED_MODEL_DIR = _BACKEND_DIR / "training" / "models" / "janvedha-classifier"

# Lazy-loaded pipelines
_finetuned_pipeline = None
_zeroshot_pipeline  = None

# ─────────────────────────────────────────────────────────────────
# Department catalogue
# ─────────────────────────────────────────────────────────────────
DEPARTMENT_CATALOGUE = {
    "D01": {"name": "Roads & Bridges",        "keywords": ["pothole", "road", "bridge", "footpath", "pavement", "crack",
                                                            "sadak", "gaddha", "rasta", "sarak"]},
    "D02": {"name": "Buildings & Planning",   "keywords": ["construction", "illegal", "encroachment", "building", "permit",
                                                            "nirmaan", "makan"]},
    "D03": {"name": "Water Supply",           "keywords": ["water", "supply", "pipe", "leak", "low pressure", "no water",
                                                            "pani", "paani", "nal"]},
    "D04": {"name": "Sewage & Drainage",      "keywords": ["sewage", "drain", "blocked", "overflow", "manhole",
                                                            "naali", "nali"]},
    "D05": {"name": "Solid Waste Management", "keywords": ["garbage", "waste", "bin", "collection", "dumping", "trash",
                                                            "kachra", "kachara", "gandagi", "kuda"]},
    "D06": {"name": "Street Lighting",        "keywords": ["light", "lamp", "dark", "street light", "electricity", "bulb",
                                                            "batti", "bijli", "andhera"]},
    "D07": {"name": "Parks & Greenery",       "keywords": ["park", "tree", "garden", "grass", "playground", "fallen tree",
                                                            "ped", "bagicha", "maidan"]},
    "D08": {"name": "Health & Sanitation",    "keywords": ["mosquito", "dengue", "fever", "epidemic", "stray", "dog",
                                                            "macchar", "machar", "bimari"]},
    "D09": {"name": "Fire & Emergency",       "keywords": ["fire", "accident", "emergency", "explosion", "hazard",
                                                            "aag", "haadsa", "durghatna"]},
    "D10": {"name": "Traffic & Transport",    "keywords": ["traffic", "signal", "bus", "road block", "parking",
                                                            "jam", "jaam", "chakka jaam"]},
    "D11": {"name": "Revenue & Property",     "keywords": ["tax", "property", "document", "certificate"]},
    "D12": {"name": "Social Welfare",         "keywords": ["pension", "welfare", "disability", "ration", "subsidy"]},
    "D13": {"name": "Education",              "keywords": ["school", "teacher", "education", "college", "student"]},
    "D14": {"name": "Disaster Management",    "keywords": ["flood", "cyclone", "landslide", "tsunami", "disaster",
                                                            "baarish", "toofan"]},
}

# Zero-shot candidate labels (English NLI phrases → dept ID)
_ZEROSHOT_CANDIDATE_MAP = {
    "D01": "roads and potholes",
    "D02": "illegal buildings",
    "D03": "water supply",
    "D04": "sewage and drainage",
    "D05": "garbage and solid waste",
    "D06": "streetlights and electricity",
    "D07": "parks and greenery",
    "D08": "health and disease",
    "D09": "fire and emergencies",
    "D10": "traffic and transport",
    "D11": "property taxes",
    "D12": "social welfare",
    "D13": "schools and education",
    "D14": "natural disasters",
}


@dataclass
class ClassificationResult:
    dept_id: str
    dept_name: str
    issue_category: str
    issue_summary: str
    location_extracted: str
    language_detected: str
    confidence: float
    needs_clarification: bool
    clarification_question: Optional[str] = None
    requires_human_review: bool = False
    classifier_source: str = "zeroshot"   # "finetuned" | "zeroshot" | "sarvam_nim" | "keyword"


# Layer 1a: Fine-tuned IndicBERTv2 (best — loads after training)
# ─────────────────────────────────────────────────────────────────

_DEPT_IDS = [
    "D01", "D02", "D03", "D04", "D05", "D06", "D07",
    "D08", "D09", "D10", "D11", "D12", "D13", "D14",
]


def _get_finetuned_pipeline():
    """Load fine-tuned model if it exists."""
    global _finetuned_pipeline
    if _finetuned_pipeline is None:
        if not _FINETUNED_MODEL_DIR.exists():
            return None  # not trained yet
        try:
            from transformers import pipeline as hf_pipeline
            logger.info("Loading fine-tuned JanVedha classifier from %s …", _FINETUNED_MODEL_DIR)
            _finetuned_pipeline = hf_pipeline(
                "text-classification",
                model=str(_FINETUNED_MODEL_DIR),
                tokenizer=str(_FINETUNED_MODEL_DIR),
            )
            logger.info("✅  Fine-tuned model loaded.")
        except Exception as exc:
            logger.warning("Could not load fine-tuned model: %s — using zero-shot.", exc)
            _finetuned_pipeline = None
    return _finetuned_pipeline


def _finetuned_classify(text: str) -> ClassificationResult:
    """Fast 14-class classification using fine-tuned IndicBERTv2."""
    clf = _get_finetuned_pipeline()
    if clf is None:
        return _zeroshot_classify(text)  # fall through

    result    = clf(text, truncation=True, max_length=128)[0]
    dept_id   = result["label"]   # e.g. "D06"
    score     = float(result["score"])

    if score < 0.40:
        logger.info("Fine-tuned model low confidence (%.2f) — escalating to Sarvam-M.", score)
        return _sarvam_nim_classify(text)

    dept_info = DEPARTMENT_CATALOGUE.get(dept_id, DEPARTMENT_CATALOGUE["D05"])
    return ClassificationResult(
        dept_id=dept_id,
        dept_name=str(dept_info["name"]),
        issue_category="general_complaint",
        issue_summary=str(text[:200]),
        location_extracted="Unknown",
        language_detected="unknown",
        confidence=score,
        needs_clarification=score < 0.3,
        clarification_question="Could you describe the issue in more detail?" if score < 0.3 else None,
        requires_human_review=score < 0.6,
        classifier_source="finetuned"
    )


# ─────────────────────────────────────────────────────────────────
# Layer 1b: Zero-shot mDeBERTa (fallback before Sarvam-M)
# ─────────────────────────────────────────────────────────────────

def _get_zeroshot_pipeline():
    global _zeroshot_pipeline
    if _zeroshot_pipeline is None:
        from transformers import pipeline
        logger.info("Loading mDeBERTa-v3-base-mnli-xnli zero-shot model (cached)...")
        _zeroshot_pipeline = pipeline(
            "zero-shot-classification",
            model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
        )
    return _zeroshot_pipeline


def _zeroshot_classify(text: str) -> ClassificationResult:
    """
    Layer 1: Local mDeBERTa zero-shot classification.
    Fast (~1-2s), works great on native Indian scripts (Hindi, Tamil, Bengali, Marathi).
    Falls back to Sarvam-M NIM when confidence < 0.40 (typically Hinglish).
    """
    try:
        classifier     = _get_zeroshot_pipeline()
        candidate_labels = list(_ZEROSHOT_CANDIDATE_MAP.values())

        result = classifier(
            text,
            candidate_labels,
            multi_label=True,
            hypothesis_template="The topic of this problem is {}."
        )
        top_label  = result["labels"][0]
        confidence = float(result["scores"][0])

        if confidence < 0.40:
            logger.info("mDeBERTa low confidence (%.2f) — escalating to Sarvam-M NIM.", confidence)
            return _sarvam_nim_classify(text)

        best_dept = "D05"
        for did, label_text in _ZEROSHOT_CANDIDATE_MAP.items():
            if label_text == top_label:
                best_dept = did
                break

        dept_info = DEPARTMENT_CATALOGUE[best_dept]
        return ClassificationResult(
            dept_id=best_dept,
            dept_name=str(dept_info["name"]),
            issue_category="general_complaint",
            issue_summary=str(text[:200]),
            location_extracted="Unknown",
            language_detected="unknown",
            confidence=confidence,
            needs_clarification=confidence < 0.3,
            clarification_question="Could you describe the issue in more detail?" if confidence < 0.3 else None,
            requires_human_review=confidence < 0.6,
            classifier_source="zeroshot"
        )
    except Exception as exc:
        logger.error("mDeBERTa zero-shot failed: %s — escalating to Sarvam-M NIM.", exc)
        return _sarvam_nim_classify(text)


# ─────────────────────────────────────────────────────────────────
# Layer 2: Sarvam-M via NVIDIA NIM (Hinglish fallback)
# ─────────────────────────────────────────────────────────────────

_SARVAM_SYSTEM = """You are a civic complaint classifier for India.
Departments:
{dept_list}

Instructions:
1. Respond with a JSON block FIRST.
2. The JSON must have: "dept_id", "dept_name", "confidence", and "language_detected".
3. After the JSON, you may explain your reasoning.
4. If unsure, use D05 (Solid Waste Management) but with low confidence.
"""


def _sarvam_nim_classify(text: str) -> ClassificationResult:
    """
    Layer 2: Sarvam-M (24B) via NVIDIA NIM free API.
    Best model for Hinglish / romanised Indian languages.
    Uses OpenAI-compatible endpoint. Falls back to keywords if API key missing.
    """
    nvidia_api_key = os.getenv("NVIDIA_API_KEY", "")
    if not nvidia_api_key:
        logger.warning("NVIDIA_API_KEY not set — skipping Sarvam-M, falling back to keywords.")
        return _keyword_fallback(text)

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=nvidia_api_key,
        )

        dept_list = "\n".join(f"  {did}: {info['name']}" for did, info in DEPARTMENT_CATALOGUE.items())
        system_msg = _SARVAM_SYSTEM.format(dept_list=dept_list)

        response = client.chat.completions.create(
            model="sarvamai/sarvam-m",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": f"Complaint: {text}\nClassification JSON:"},
            ],
            temperature=0.0,
            max_tokens=256,
        )

        raw = response.choices[0].message.content.strip()
        logger.info(f"Raw Sarvam-M Response: {raw}")

        try:
            # Find the FIRST {...} block (we nudged it to output JSON first)
            match = re.search(r"(\{.*?\})", raw, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
            else:
                # Fallback extraction: Find ALL Dxx codes and pick the most frequent or last one
                matches = re.findall(r"(D\d{2})", raw)
                if matches:
                    # Often the last Dxx mentioned is the final choice
                    dept_id = matches[-1]
                    dept_info = DEPARTMENT_CATALOGUE.get(dept_id, DEPARTMENT_CATALOGUE["D05"])
                    return ClassificationResult(
                        dept_id=dept_id,
                        dept_name=str(dept_info["name"]),
                        issue_category="general_complaint",
                        issue_summary=str(text[:200]),
                        location_extracted="Unknown",
                        language_detected="unknown",
                        confidence=0.7,
                        needs_clarification=False,
                        classifier_source="sarvam_nim"
                    )
                raise ValueError("No JSON or Dept ID found")
        except Exception as json_err:
            logger.error(f"Failed to parse Sarvam-M output: {json_err}")
            return _keyword_fallback(text)

        dept_id = str(data.get("dept_id", "D05"))
        if len(dept_id) == 2 and not dept_id.startswith("D"):
            # If they just output "01" instead of "D01"
            dept_id = f"D{dept_id}"
            
        dept_info = DEPARTMENT_CATALOGUE.get(dept_id, DEPARTMENT_CATALOGUE["D05"])
        confidence = float(data.get("confidence", 0.75))
        language = str(data.get("language_detected", "hi"))

        return ClassificationResult(
            dept_id=dept_id,
            dept_name=str(dept_info["name"]),
            issue_category="general_complaint",
            issue_summary=str(text[:200]),
            location_extracted="Unknown",
            language_detected=language,
            confidence=confidence,
            needs_clarification=confidence < 0.5,
            clarification_question="Could you describe the issue in more detail?" if confidence < 0.5 else None,
            requires_human_review=confidence < 0.6,
            classifier_source="sarvam_nim"
        )

    except Exception as exc:
        logger.error("Sarvam-M NIM failed: %s — falling back to keywords.", exc)
        return _keyword_fallback(text)


# ─────────────────────────────────────────────────────────────────
# Layer 3: Keyword fallback (last resort)
# ─────────────────────────────────────────────────────────────────

def _keyword_fallback(text: str) -> ClassificationResult:
    """Always-works keyword match. Covers English + common Hinglish transliterations."""
    text_lower = text.lower()
    best_dept  = "D05"
    best_score = 0
    for dept_id, info in DEPARTMENT_CATALOGUE.items():
        score = sum(1 for kw in info["keywords"] if kw in text_lower)
        if score > best_score:
            best_score = score
            best_dept  = dept_id
    dept_info = DEPARTMENT_CATALOGUE[best_dept]
    matched = best_score > 0
    return ClassificationResult(
        dept_id=best_dept,
        dept_name=str(dept_info["name"]),
        issue_category="general_complaint",
        issue_summary=str(text[:200]),
        location_extracted="Unknown",
        language_detected="en",
        confidence=0.75 if matched else 0.45,
        needs_clarification=not matched,
        clarification_question="Could you describe the issue in more detail?" if not matched else None,
        requires_human_review=not matched,
        classifier_source="keyword"
    )


# ─────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────

async def classify_complaint(description: str, photo_url: Optional[str] = None) -> ClassificationResult:
    """
    Main entry point called by the AI pipeline.
    Waterfall: Fine-tuned model → mDeBERTa zero-shot → Sarvam-M NIM → Keyword.
    Auto-promotes to fine-tuned once training/fine_tune.py has been run.
    """
    return _finetuned_classify(description)
