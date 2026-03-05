"""
WorkCompletionAgent — Before/After Image Verification for Civic Repairs

Architecture (3-tier fallback, entirely free):

Tier 1: Gemini Vision (multimodal)
  - Uses the already-integrated gemini-2.0-flash model
  - Sends BOTH images + issue description in one prompt
  - Returns structured JSON: verified, confidence, explanation, change_detected
  - Free tier: 1500 req/day — more than enough for civic ticket volume
  - Best choice: understands WHAT was wrong and WHAT was fixed, not just pixels

Tier 2: SSIM + Perceptual Hash (local, zero dependencies beyond pillow+scikit-image)
  - Structural Similarity Index (SSIM) — measures luminance/contrast/structure
  - pHash — detect gross changes in image content
  - Heuristic: HIGH similarity = little change (bad for "fixed" claims)
             LOW similarity + specific change area = likely work done
  - Works offline, zero cost, ~30ms per comparison

Tier 3: Pixel-level fallback
  - Pure numpy/PIL histogram difference
  - Works even without scikit-image installed
  - Lower accuracy, but never crashes

Called from:
  - officer.py PATCH /tickets/{id}/verify-completion (technician submits after photo)
  - Returns WorkVerificationResult stored on the ticket

Ticket model fields used:
  - ticket.before_photo_url   — set by public user at complaint submission
  - ticket.after_photo_url    — set by technician when marking work done
  - ticket.issue_category     — e.g. "open_manhole", "pothole", "garbage"
  - ticket.description        — full complaint text
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional
import asyncio

import httpx

logger = logging.getLogger(__name__)


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class WorkVerificationResult:
    verified: bool                  # True = work is complete / issue resolved
    confidence: float               # 0.0 – 1.0
    method: str                     # "gemini_vision" | "ssim_local" | "pixel_fallback"
    explanation: str                # Human-readable reason (for dashboard)
    change_detected: bool           # True if images look meaningfully different
    ssim_score: Optional[float]     # Structural similarity (0=different, 1=identical)
    phash_distance: Optional[int]   # Perceptual hash distance (0=same, >10=very different)
    gemini_raw: Optional[str]       # Raw Gemini response (for debugging)

    def to_dict(self) -> dict:
        return {
            "verified": self.verified,
            "confidence": round(self.confidence, 3),
            "method": self.method,
            "explanation": self.explanation,
            "change_detected": self.change_detected,
            "ssim_score": round(self.ssim_score, 3) if self.ssim_score is not None else None,
            "phash_distance": self.phash_distance,
        }


# ── Image fetching ─────────────────────────────────────────────────────────────

async def _fetch_image_bytes(url: str) -> Optional[bytes]:
    """Download an image from a URL (local or remote). Returns bytes or None."""
    try:
        if url.startswith("http"):
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
        else:
            # Local file path
            import aiofiles
            async with aiofiles.open(url, "rb") as f:
                return await f.read()
    except Exception as exc:
        logger.warning("Image fetch failed for %s: %s", url, exc)
        return None


def _bytes_to_b64(img_bytes: bytes, mime: str = "image/jpeg") -> str:
    """Encode raw image bytes to a data URI string for Gemini."""
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _detect_mime(img_bytes: bytes) -> str:
    """Detect MIME type from magic bytes."""
    if img_bytes[:4] == b'\x89PNG':
        return "image/png"
    if img_bytes[:2] == b'\xff\xd8':
        return "image/jpeg"
    if img_bytes[:4] == b'RIFF' and img_bytes[8:12] == b'WEBP':
        return "image/webp"
    return "image/jpeg"  # safe default


# ── Tier 1: Gemini Vision ──────────────────────────────────────────────────────

GEMINI_SYSTEM_PROMPT = """You are an expert civic infrastructure quality inspector for a municipal digital governance system.

Your task is to compare a BEFORE image (showing a civic problem) and an AFTER image (showing the claimed repair/resolution) and determine if the work has been genuinely completed.

You will also be given:
- The issue category (e.g. "pothole", "garbage", "open_manhole", "street_light_out")
- The original complaint description

Rules:
1. Base your decision primarily on VISUAL evidence in the images
2. Be strict — if the after image is blurry, mismatched location, or the same problem persists, mark verified=false
3. If the after image shows clear resolution of the specific complaint, mark verified=true
4. Assign confidence based on image quality, clarity of change, and match to the issue type

Respond ONLY with valid JSON (no markdown, no explanation outside JSON):
{
  "verified": <true|false>,
  "confidence": <float 0.0-1.0>,
  "change_detected": <true|false — are the images visually different?>,
  "explanation": "<1-2 sentence human-readable verdict for the officer dashboard>"
}"""


async def _verify_with_gemini(
    before_bytes: bytes,
    after_bytes: bytes,
    issue_category: str,
    description: str,
) -> Optional[WorkVerificationResult]:
    """
    Uses Gemini Vision (multimodal) to compare before/after images.
    Returns WorkVerificationResult or None if the API call fails.
    """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.services.ai.gemini_client import get_llm

        before_b64 = _bytes_to_b64(before_bytes, _detect_mime(before_bytes))
        after_b64 = _bytes_to_b64(after_bytes, _detect_mime(after_bytes))

        llm = get_llm()  # gemini-2.0-flash — already configured in the project

        system = SystemMessage(content=GEMINI_SYSTEM_PROMPT)
        human = HumanMessage(content=[
            {
                "type": "text",
                "text": (
                    f"Issue Category: {issue_category}\n"
                    f"Original Complaint: {description[:500]}\n\n"
                    "BEFORE image (the problem):"
                )
            },
            {
                "type": "image_url",
                "image_url": {"url": before_b64},
            },
            {
                "type": "text",
                "text": "AFTER image (the claimed fix):"
            },
            {
                "type": "image_url",
                "image_url": {"url": after_b64},
            },
        ])

        response = await llm.ainvoke([system, human])
        raw = response.content.strip()

        # Strip markdown fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw).strip("`").strip()

        data = json.loads(raw)

        return WorkVerificationResult(
            verified=bool(data.get("verified", False)),
            confidence=float(data.get("confidence", 0.5)),
            method="gemini_vision",
            explanation=str(data.get("explanation", "Gemini analysis completed.")),
            change_detected=bool(data.get("change_detected", False)),
            ssim_score=None,
            phash_distance=None,
            gemini_raw=raw,
        )

    except Exception as exc:
        logger.warning("Gemini Vision verification failed: %s", exc)
        return None


# ── Tier 2: SSIM + Perceptual Hash (local) ────────────────────────────────────

def _compute_ssim(img1_bytes: bytes, img2_bytes: bytes) -> Optional[float]:
    """
    Compute Structural Similarity Index between two images.
    Returns float 0-1 or None if scikit-image unavailable.
    """
    try:
        from PIL import Image
        from skimage.metrics import structural_similarity as ssim
        import numpy as np

        def load_gray(b: bytes):
            img = Image.open(io.BytesIO(b)).convert("L").resize((256, 256))
            return np.array(img, dtype=np.float64)

        arr1 = load_gray(img1_bytes)
        arr2 = load_gray(img2_bytes)
        score, _ = ssim(arr1, arr2, full=True, data_range=255.0)
        return float(score)
    except ImportError:
        return None
    except Exception as exc:
        logger.debug("SSIM computation failed: %s", exc)
        return None


def _compute_phash(img_bytes: bytes) -> Optional[int]:
    """
    Compute a 64-bit perceptual hash of an image.
    Returns the integer hash value or None on failure.
    """
    try:
        from PIL import Image
        import numpy as np

        img = Image.open(io.BytesIO(img_bytes)).convert("L").resize((32, 32), Image.LANCZOS)
        arr = np.array(img, dtype=np.float32)
        mean = arr.mean()
        bits = (arr >= mean).flatten().tolist()
        # Pack bits into an integer
        value = 0
        for bit in bits:
            value = (value << 1) | int(bit)
        return value
    except Exception as exc:
        logger.debug("pHash computation failed: %s", exc)
        return None


def _phash_distance(h1: Optional[int], h2: Optional[int]) -> Optional[int]:
    """Hamming distance between two pHash values."""
    if h1 is None or h2 is None:
        return None
    return bin(h1 ^ h2).count("1")


def _ssim_verdict(
    ssim_score: Optional[float],
    phash_dist: Optional[int],
    issue_category: str,
) -> WorkVerificationResult:
    """
    Heuristic verdict from SSIM + pHash scores.

    Logic:
    - Very HIGH similarity (ssim > 0.90) → images look the same → NOT verified
      (unless the issue was "cosmetic": streetlight, minor crack — where same=fixed)
    - LOW similarity (ssim < 0.60) → big change — likely work done
    - Medium similarity → inconclusive, mark as low-confidence partial

    pHash distance helps catch gross location mismatches (distance > 30 = different scene)

    Edge case: for issue categories where "looking the same" means "fixed"
    (like streetlight_out — dark vs lit), a high SSIM is expected for fixed.
    We correct for this with issue_category awareness.
    """
    # Categories where same appearance = not fixed (construction, garbage, flooding)
    CHANGE_REQUIRED_CATS = {
        "pothole", "large_pothole", "small_pothole", "road_collapse",
        "garbage", "overflowing_bin", "illegal_dumping_large",
        "open_manhole", "sewage_overflow", "drain_blocked",
        "flood", "flooding", "dead_animal_carcass", "dead_carcass",
    }

    # Categories where illumination/presence change matters
    PRESENCE_CATS = {
        "street_light_out", "multiple_lights_out", "streetlight",
    }

    is_change_required = issue_category in CHANGE_REQUIRED_CATS
    is_presence = issue_category in PRESENCE_CATS
    s = ssim_score if ssim_score is not None else 0.5
    ph = phash_dist if phash_dist is not None else 20

    # Gross location mismatch guard
    if ph > 40:
        return WorkVerificationResult(
            verified=False,
            confidence=0.85,
            method="ssim_local",
            explanation=(
                "The after image shows a completely different location or scene. "
                "Perceptual hash distance is very high, suggesting the photo may not "
                "be of the same site."
            ),
            change_detected=True,
            ssim_score=ssim_score,
            phash_distance=phash_dist,
            gemini_raw=None,
        )

    if is_presence:
        # For lighting issues, significant difference alone isn't enough —
        # we need at least some change, but can't validate which direction
        change_detected = s < 0.85 or ph > 15
        verified = change_detected and s < 0.80
        return WorkVerificationResult(
            verified=verified,
            confidence=0.55 if verified else 0.45,
            method="ssim_local",
            explanation=(
                "Lighting change detected — images appear different in brightness, "
                "suggesting the streetlight may have been repaired."
                if verified else
                "Images appear similar. Cannot confirm lighting repair from images alone."
            ),
            change_detected=change_detected,
            ssim_score=ssim_score,
            phash_distance=phash_dist,
            gemini_raw=None,
        )

    if is_change_required:
        if s < 0.55:
            return WorkVerificationResult(
                verified=True, confidence=0.72, method="ssim_local",
                explanation=(
                    f"Significant visual change detected (SSIM={s:.2f}). "
                    "The after image looks substantially different, suggesting the "
                    f"repair has been completed."
                ),
                change_detected=True, ssim_score=ssim_score, phash_distance=phash_dist,
                gemini_raw=None,
            )
        elif s < 0.75:
            return WorkVerificationResult(
                verified=False, confidence=0.55, method="ssim_local",
                explanation=(
                    f"Moderate visual change detected (SSIM={s:.2f}) but insufficient "
                    "to confirm full resolution. Manual review recommended."
                ),
                change_detected=True, ssim_score=ssim_score, phash_distance=phash_dist,
                gemini_raw=None,
            )
        else:
            return WorkVerificationResult(
                verified=False, confidence=0.65, method="ssim_local",
                explanation=(
                    f"Images look very similar (SSIM={s:.2f}). The reported issue "
                    "may not have been resolved. Manual review required."
                ),
                change_detected=False, ssim_score=ssim_score, phash_distance=phash_dist,
                gemini_raw=None,
            )

    # Generic case
    change_detected = s < 0.75
    verified = s < 0.60
    return WorkVerificationResult(
        verified=verified,
        confidence=0.55,
        method="ssim_local",
        explanation=(
            f"Image comparison score: {s:.2f}. "
            + ("Meaningful change detected." if change_detected else "Images appear similar.")
            + " Gemini vision was unavailable for deeper analysis."
        ),
        change_detected=change_detected,
        ssim_score=ssim_score,
        phash_distance=phash_dist,
        gemini_raw=None,
    )


# ── Tier 3: Pixel-level histogram fallback ────────────────────────────────────

def _pixel_fallback(img1_bytes: bytes, img2_bytes: bytes, issue_category: str) -> WorkVerificationResult:
    """
    Pixel-level histogram difference fallback using only PIL.
    Less accurate but always works.
    """
    try:
        from PIL import Image
        import numpy as np

        def load_hist(b: bytes):
            img = Image.open(io.BytesIO(b)).convert("RGB").resize((128, 128))
            arr = np.array(img, dtype=np.float32)
            return arr

        arr1 = load_hist(img1_bytes)
        arr2 = load_hist(img2_bytes)
        diff = np.abs(arr1 - arr2).mean() / 255.0  # 0=same, 1=completely different
        change_detected = diff > 0.15
        verified = diff > 0.20
        return WorkVerificationResult(
            verified=verified,
            confidence=min(0.50, 0.3 + diff),
            method="pixel_fallback",
            explanation=(
                f"Basic pixel analysis (diff={diff:.2f}). "
                + ("Significant image change detected." if change_detected
                   else "Images appear similar.")
                + " For accurate verification, ensure image analysis dependencies are installed."
            ),
            change_detected=change_detected,
            ssim_score=None,
            phash_distance=None,
            gemini_raw=None,
        )
    except Exception as exc:
        return WorkVerificationResult(
            verified=False,
            confidence=0.0,
            method="pixel_fallback",
            explanation=f"Image verification failed: {exc}. Manual review required.",
            change_detected=False,
            ssim_score=None,
            phash_distance=None,
            gemini_raw=None,
        )


# ── Main Entry Point ──────────────────────────────────────────────────────────

async def verify_work_completion(
    before_url: str,
    after_url: str,
    issue_category: str,
    description: str,
) -> WorkVerificationResult:
    """
    Main entry point. 3-tier fallback:
      1. Gemini Vision (if images are fetchable)
      2. SSIM + pHash (if scikit-image available)
      3. Pixel histogram fallback (PIL only)

    Args:
        before_url:      URL of the before image (from public user complaint)
        after_url:       URL of the after image (submitted by technician)
        issue_category:  e.g. "pothole", "garbage", "open_manhole"
        description:     Original complaint text for context

    Returns:
        WorkVerificationResult with verified bool, confidence, explanation
    """
    # Fetch both images concurrently
    before_bytes, after_bytes = await asyncio.gather(
        _fetch_image_bytes(before_url),
        _fetch_image_bytes(after_url),
    )

    if before_bytes is None or after_bytes is None:
        missing = []
        if before_bytes is None: missing.append("before")
        if after_bytes is None: missing.append("after")
        return WorkVerificationResult(
            verified=False,
            confidence=0.0,
            method="error",
            explanation=f"Could not fetch {' and '.join(missing)} image(s). URLs may be invalid or expired.",
            change_detected=False,
            ssim_score=None,
            phash_distance=None,
            gemini_raw=None,
        )

    # ── Tier 1: Gemini Vision ──────────────────────────────────────────────────
    gemini_result = await _verify_with_gemini(
        before_bytes, after_bytes, issue_category, description
    )
    if gemini_result is not None:
        # Also compute local scores for supplemental data even when Gemini succeeds
        ssim_score = await asyncio.get_event_loop().run_in_executor(
            None, _compute_ssim, before_bytes, after_bytes
        )
        h1 = _compute_phash(before_bytes)
        h2 = _compute_phash(after_bytes)
        phash_dist = _phash_distance(h1, h2)
        gemini_result.ssim_score = ssim_score
        gemini_result.phash_distance = phash_dist
        return gemini_result

    # ── Tier 2: SSIM + pHash ──────────────────────────────────────────────────
    logger.info("Work verification: falling back to SSIM+pHash (Gemini unavailable)")
    ssim_score = await asyncio.get_event_loop().run_in_executor(
        None, _compute_ssim, before_bytes, after_bytes
    )
    if ssim_score is not None:
        h1 = _compute_phash(before_bytes)
        h2 = _compute_phash(after_bytes)
        phash_dist = _phash_distance(h1, h2)
        return _ssim_verdict(ssim_score, phash_dist, issue_category)

    # ── Tier 3: Pixel fallback ────────────────────────────────────────────────
    logger.info("Work verification: using pixel fallback (scikit-image unavailable)")
    return await asyncio.get_event_loop().run_in_executor(
        None, _pixel_fallback, before_bytes, after_bytes, issue_category
    )
