"""
Scheme Eligibility Advisor API

Endpoints for councillors to query constituent scheme eligibility,
view query history, and submit feedback. All tied into Langfuse observability.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.mongodb.models.scheme_query import SchemeQueryMongo
from app.enums import UserRole
from app.services.rag.scheme_advisor import get_scheme_advisor

logger = logging.getLogger(__name__)
router = APIRouter()

class SchemeQueryRequest(BaseModel):
    constituent_profile: str
    ward_id: Optional[int] = None

class FeedbackRequest(BaseModel):
    score: int # 1 for thumbs up, 0 for down
    
def _require_authorized(current_user: UserMongo = Depends(get_current_user)):
    allowed = {UserRole.COUNCILLOR, UserRole.WARD_OFFICER, UserRole.SUPERVISOR, UserRole.COMMISSIONER, UserRole.SUPER_ADMIN}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Scheme Advisor access denied")
    return current_user

@router.post("/query")
async def process_scheme_query(
    request: SchemeQueryRequest, 
    current_user: UserMongo = Depends(_require_authorized)
):
    """Run a constituent profile through the RAG pipeline."""
    advisor = get_scheme_advisor()
    ward_context = f"Ward {request.ward_id}" if request.ward_id else f"Ward {current_user.ward_id}"
    
    # Run the generation (traces automatically attached via langfuse object context or decorators)
    # The Langfuse @observe decorator captures the span tree.
    # To get trace ID natively from Langfuse SDK, we use langfuse_context
    try:
        from langfuse import get_client
        trace_id = get_client().get_current_trace_id()
    except Exception:
        trace_id = None
        
    result = advisor.assess_eligibility(
        profile_text=request.constituent_profile, 
        ward_context=ward_context
    )
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    # Save the query result to MongoDB
    record = SchemeQueryMongo(
        constituent_profile=request.constituent_profile,
        ward_id=request.ward_id or current_user.ward_id,
        councillor_user_id=str(current_user.id),
        result=result,
        langfuse_trace_id=trace_id
    )
    await record.insert()
    
    return {
        "success": True,
        "query_id": str(record.id),
        "trace_id": trace_id,
        "assessment": result
    }

@router.get("/history")
async def get_query_history(
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0),
    current_user: UserMongo = Depends(_require_authorized)
):
    """Retrieve history of queries for the current councillor."""
    queries = await SchemeQueryMongo.find(
        SchemeQueryMongo.councillor_user_id == str(current_user.id)
    ).sort("-created_at").skip(skip).limit(limit).to_list()
    
    return [{
        "id": str(q.id),
        "profile": q.constituent_profile[:100] + "..." if len(q.constituent_profile) > 100 else q.constituent_profile,
        "created_at": q.created_at,
        "feedback_score": q.feedback_score,
        "eligible_count": len(q.result.get("eligible_schemes", [])) if q.result else 0
    } for q in queries]

@router.get("/query/{query_id}")
async def get_query_detail(query_id: str, current_user: UserMongo = Depends(_require_authorized)):
    from bson import ObjectId
    q = await SchemeQueryMongo.get(ObjectId(query_id))
    if not q:
        raise HTTPException(404, "Query not found")
        
    return {
        "id": str(q.id),
        "profile": q.constituent_profile,
        "result": q.result,
        "created_at": q.created_at,
        "feedback_score": q.feedback_score
    }

@router.post("/{query_id}/feedback")
async def submit_feedback(
    query_id: str, 
    feedback: FeedbackRequest,
    current_user: UserMongo = Depends(_require_authorized)
):
    from bson import ObjectId
    q = await SchemeQueryMongo.get(ObjectId(query_id))
    if not q:
        raise HTTPException(404, "Query not found")
        
    q.feedback_score = feedback.score
    await q.save()
    
    # Forward feedback to Langfuse if there's a trace_id
    if q.langfuse_trace_id:
        try:
            from app.services.langfuse_client import get_langfuse
            lf = get_langfuse()
            lf.score(
                trace_id=q.langfuse_trace_id,
                name="user_feedback",
                value=feedback.score,
                comment="Thumbs up/down from councillor UI"
            )
            lf.flush()
        except Exception as e:
            logger.error(f"Failed to submit Langfuse score: {e}")
            
    return {"success": True}

@router.get("/stats")
async def get_global_stats(current_user: UserMongo = Depends(_require_authorized)):
    """Commissioner-level stats on AI scheme advisor usage."""
    if current_user.role not in {UserRole.COMMISSIONER, UserRole.SUPER_ADMIN}:
        raise HTTPException(status_code=403, detail="Commissioner access required")
        
    total_queries = await SchemeQueryMongo.count()
    
    # Aggregate feedback manually
    queries_with_feedback = await SchemeQueryMongo.find(SchemeQueryMongo.feedback_score != None).to_list()
    if queries_with_feedback:
        avg_feedback = sum(q.feedback_score for q in queries_with_feedback) / len(queries_with_feedback)
    else:
        avg_feedback = 0.0
        
    # We could query Langfuse metrics API natively here, but basic ops via MongoDB suffice for quick stats
    
    return {
        "total_queries": total_queries,
        "avg_councillor_feedback": round(avg_feedback, 2),
        "recent_queries": total_queries # Placeholder
    }
