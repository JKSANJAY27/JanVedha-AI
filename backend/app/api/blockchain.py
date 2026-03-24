"""
Blockchain API Router
Exposes endpoints for the transparent Web3 audit log system.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import logging

from app.core.dependencies import get_current_user, require_ward_officer
from app.mongodb.models.user import UserMongo
from app.mongodb.models.audit_anchor import AuditAnchorMongo
from app.services.blockchain_service import BlockchainService
from app.core.container import get_blockchain_provider

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/anchor")
async def trigger_anchor_batch(
    current_user: UserMongo = Depends(require_ward_officer)
):
    """
    Manually trigger a blockchain anchor of all pending audit logs.
    Restricted to Commissioners/Admins.
    """
    try:
        result = await BlockchainService.anchor_pending_audit_logs()
        return result
    except Exception as e:
        logger.error(f"Manual batch anchor failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Anchoring failed: {str(e)}")

@router.get("/verify/{batch_id}")
async def verify_batch_integrity(
    batch_id: str,
    current_user: UserMongo = Depends(get_current_user)
):
    """
    Verify the cryptographic integrity of a specific audit batch against the blockchain.
    """
    result = await BlockchainService.verify_batch_integrity(batch_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result

@router.get("/anchors")
async def list_anchor_history(
    limit: int = Query(50, le=100),
    skip: int = Query(0),
    current_user: UserMongo = Depends(get_current_user)
):
    """
    Returns the history of blockchain anchors, including mock block explorer URLs.
    """
    try:
        anchors = await AuditAnchorMongo.find_all().sort(-AuditAnchorMongo.created_at).skip(skip).limit(limit).to_list()
        
        provider = get_blockchain_provider()
        
        return [
            {
                "id": str(a.id),
                "batch_id": a.batch_id,
                "data_hash": a.data_hash,
                "anchor_count": a.anchor_count,
                "tx_hash": a.tx_hash,
                "explorer_url": provider.get_transaction_url(a.tx_hash) if a.tx_hash else None,
                "block_number": a.block_number,
                "status": a.status,
                "anchored_at": a.anchored_at,
            }
            for a in anchors
        ]
    except Exception as e:
        logger.error(f"Failed to list anchors: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load anchor history: {str(e)}")

@router.get("/ticket/{ticket_id}/audit-status")
async def get_ticket_audit_status(
    ticket_id: str,
    current_user: UserMongo = Depends(get_current_user)
):
    """
    Returns the blockchain status of all audit logs for a specific ticket.
    """
    from app.mongodb.models.audit_log import AuditLogMongo
    logs = await AuditLogMongo.find(AuditLogMongo.ticket_id == ticket_id).sort(+AuditLogMongo.created_at).to_list()
    
    provider = get_blockchain_provider()
    
    results = []
    for log in logs:
        results.append({
            "audit_id": str(log.id),
            "action": log.action,
            "created_at": log.created_at,
            "is_anchored": log.blockchain_anchored,
            "batch_id": log.blockchain_batch_id,
            "tx_hash": log.blockchain_tx_hash,
            "explorer_url": provider.get_transaction_url(log.blockchain_tx_hash) if log.blockchain_tx_hash else None,
        })
    
    return results
