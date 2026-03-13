"""
Misinformation Detector — Feature 3.

Background task that runs every 30 minutes to detect false/misleading social
media posts and auto-draft fact-based counter-responses using real ticket data.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Gemini call: detect suspicious posts ─────────────────────────────────────

async def detect_misinformation_in_posts(posts: List[Dict], ward_id: int) -> List[Dict]:
    """
    Call Gemini to identify false/misleading/inflammatory claims in social posts.
    Returns a list of flagged items.
    """
    if not settings.GEMINI_API_KEY or not posts:
        return []

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")

        posts_text = "\n".join([
            f"[Post {p.get('post_id', i)}]: {p.get('text', '')}"
            for i, p in enumerate(posts)
        ])

        prompt = f"""You are a fact-checking assistant for a municipal corporation.
Below are recent social media posts from ward {ward_id}.
Identify any posts that contain potentially false, misleading, or inflammatory claims about the municipality's work or governance.

Posts:
{posts_text}

For each suspicious post respond in a JSON array with this exact format:
[
  {{
    "post_id": "...",
    "claim": "The false/misleading claim in one sentence",
    "risk_level": "high/medium/low",
    "suggested_counter_data_needed": ["e.g. flood relief ticket count", "budget spent on roads"]
  }}
]
If no suspicious posts, return an empty JSON array: []
Return ONLY the JSON array, no extra text."""

        response = await model.generate_content_async(prompt)
        text = response.text.strip()

        # Clean up possible markdown code block
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        flags = json.loads(text)
        return flags if isinstance(flags, list) else []
    except Exception as e:
        logger.error(f"Misinformation detection failed: {e}")
        return []


# ─── Fetch relevant counter-data from ticket DB ────────────────────────────────

async def fetch_counter_data(claim: str, ward_id: int) -> Dict[str, Any]:
    """Fetch relevant ticket statistics to counter a specific claim."""
    from app.mongodb.models.ticket import TicketMongo
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    tickets_30d = await TicketMongo.find(
        TicketMongo.ward_id == ward_id,
        TicketMongo.created_at >= thirty_days_ago,
    ).to_list()

    closed = [t for t in tickets_30d if t.status in {"CLOSED", "RESOLVED"}]
    verified = [t for t in closed if t.work_verified is True]

    # Categorize by department for targeted counter-data
    dept_breakdown = {}
    for t in tickets_30d:
        d = t.dept_id
        if d not in dept_breakdown:
            dept_breakdown[d] = {"total": 0, "closed": 0}
        dept_breakdown[d]["total"] += 1
        if t.status in {"CLOSED", "RESOLVED"}:
            dept_breakdown[d]["closed"] += 1

    avg_res_hours = None
    if closed:
        times = [
            (t.resolved_at - t.created_at).total_seconds() / 3600
            for t in closed if t.resolved_at
        ]
        avg_res_hours = round(sum(times) / len(times), 1) if times else None

    return {
        "total_tickets_last_30_days": len(tickets_30d),
        "resolved_last_30_days": len(closed),
        "verified_resolutions": len(verified),
        "avg_resolution_hours": avg_res_hours,
        "resolution_rate_pct": round((len(closed) / len(tickets_30d) * 100), 1) if tickets_30d else 0,
        "department_breakdown": dept_breakdown,
    }


# ─── Gemini call: draft counter-response ───────────────────────────────────────

async def draft_counter_response(claim: str, counter_data: Dict, ward_id: int) -> str:
    """Use Gemini to draft an official, factual response to the claim."""
    if not settings.GEMINI_API_KEY:
        return f"The claim is inaccurate. Our records show {counter_data.get('resolved_last_30_days', 0)} issues resolved in the last 30 days with a {counter_data.get('resolution_rate_pct', 0)}% resolution rate. For full details, visit our portal."

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")

        data_summary = f"""
- Total complaints (last 30 days): {counter_data.get('total_tickets_last_30_days', 0)}
- Issues resolved: {counter_data.get('resolved_last_30_days', 0)}
- Avg resolution time: {counter_data.get('avg_resolution_hours', 'N/A')} hours
- Verified resolutions: {counter_data.get('verified_resolutions', 0)}
- Resolution rate: {counter_data.get('resolution_rate_pct', 0)}%"""

        prompt = f"""Draft an official, factual, calm response to this claim: "{claim}"
Use this real data as evidence: {data_summary}
Format: 2-3 sentences. Professional but accessible tone. Reference specific numbers.
End with: "For full details, visit our civic portal."
Do NOT be aggressive or dismissive. Just state facts."""

        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Counter-response drafting failed: {e}")
        return f"Our records show {counter_data.get('resolved_last_30_days', 0)} civic issues resolved in the past 30 days with a {counter_data.get('resolution_rate_pct', 0)}% resolution rate. For full details, visit our civic portal."


# ─── Main detector task ────────────────────────────────────────────────────────

async def run_misinformation_check(ward_id: Optional[int] = None) -> int:
    """
    Check recent social posts for misinformation.
    Returns number of new flags created.
    """
    from app.mongodb.models.social_post import SocialPostMongo
    from app.mongodb.models.misinformation_flag import MisinformationFlagMongo

    try:
        # Fetch posts from the last 30 minutes
        since = datetime.utcnow() - timedelta(minutes=30)
        query = SocialPostMongo.find(SocialPostMongo.timestamp >= since)
        if ward_id:
            query = SocialPostMongo.find(
                SocialPostMongo.ward_id == ward_id,
                SocialPostMongo.timestamp >= since,
            )

        recent_posts = await query.limit(50).to_list()
        if not recent_posts:
            return 0

        # Get already-flagged post IDs to avoid re-flagging
        existing = await MisinformationFlagMongo.find().to_list()
        flagged_ids = {f.post_id for f in existing}

        new_posts = [
            {"post_id": str(p.id), "text": p.text}
            for p in recent_posts
            if str(p.id) not in flagged_ids
        ]
        if not new_posts:
            return 0

        # Use ward_id from first post if not provided
        effective_ward = ward_id or (recent_posts[0].ward_id if recent_posts else 0) or 0
        flags = await detect_misinformation_in_posts(new_posts, effective_ward)

        created = 0
        for flag in flags:
            post_id = flag.get("post_id", "")
            if post_id in flagged_ids:
                continue

            # Find original post text
            original_post = next((p for p in new_posts if p["post_id"] == post_id), None)
            if not original_post:
                continue

            # For high-risk flags, fetch counter-data and draft response
            counter_data = None
            draft_response = None
            if flag.get("risk_level") == "high":
                counter_data = await fetch_counter_data(flag.get("claim", ""), effective_ward)
                draft_response = await draft_counter_response(
                    flag.get("claim", ""),
                    counter_data,
                    effective_ward,
                )

            flag_doc = MisinformationFlagMongo(
                post_id=post_id,
                post_text=original_post["text"],
                ward_id=effective_ward,
                claim=flag.get("claim", "Unspecified claim"),
                risk_level=flag.get("risk_level", "low"),
                suggested_counter_data_needed=flag.get("suggested_counter_data_needed", []),
                counter_data=counter_data,
                draft_response=draft_response,
            )
            await flag_doc.insert()
            created += 1
            flagged_ids.add(post_id)

        return created
    except Exception as e:
        logger.error(f"Misinformation check failed: {e}")
        return 0


# ─── Scheduler loop ───────────────────────────────────────────────────────────

async def start_misinformation_detector():
    """Runs the misinformation detector every 30 minutes as a background task."""
    logger.info("Misinformation detector background task started.")
    while True:
        try:
            count = await run_misinformation_check()
            if count > 0:
                logger.info(f"Misinformation detector: {count} new flag(s) created.")
        except Exception as e:
            logger.error(f"Misinformation detector loop error: {e}")
        await asyncio.sleep(30 * 60)  # 30 minutes
