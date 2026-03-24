"""
BlockchainService
Orchestrates creating batches of un-anchored audit logs, calculating their SHA-256 hash,
and anchoring them to the blockchain via PolygonAdapter.
"""
import logging
import hashlib
import json
from uuid import uuid4
from datetime import datetime
from typing import Dict, Any

from app.mongodb.models.audit_log import AuditLogMongo
from app.mongodb.models.audit_anchor import AuditAnchorMongo
from app.core.container import get_blockchain_provider

logger = logging.getLogger(__name__)

def _compute_sha256(data: list[dict]) -> str:
    """Computes a deterministic SHA-256 digest of a JSON-serializable list."""
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

class BlockchainService:
    @staticmethod
    async def anchor_pending_audit_logs() -> Dict[str, Any]:
        """
        Finds all un-anchored audit logs in MongoDB, batches them,
        computes their SHA-256 hash, and writes it to the blockchain.
        Returns the batch information.
        """
        unanchored_logs = await AuditLogMongo.find(
            AuditLogMongo.blockchain_anchored == False
        ).to_list()

        if not unanchored_logs:
            return {"status": "no_logs", "count": 0}

        batch_id = str(uuid4())
        
        # Prepare deterministic data subset for hashing
        # We must include the _id to ensure uniqueness and verifiable content
        hashable_data = []
        for log in unanchored_logs:
            record = {
                "id": str(log.id),
                "ticket_id": log.ticket_id,
                "action": log.action,
                "actor_id": log.actor_id,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "created_at": log.created_at.isoformat()
            }
            hashable_data.append(record)

        # 1. Compute Hash
        data_hash = _compute_sha256(hashable_data)
        
        # 2. Save pending anchor record in Mongo
        anchor_record = AuditAnchorMongo(
            batch_id=batch_id,
            data_hash=data_hash,
            anchor_count=len(unanchored_logs),
            status="pending"
        )
        await anchor_record.insert()

        try:
            # 3. Anchor to EVM
            provider = get_blockchain_provider()
            receipt = await provider.anchor_batch(batch_id, data_hash)

            # 4. Update Anchor Record
            anchor_record.status = "confirmed"
            anchor_record.tx_hash = receipt.transaction_id
            anchor_record.block_number = receipt.block_number
            anchor_record.anchored_at = datetime.fromisoformat(receipt.recorded_at) if 'T' in receipt.recorded_at else datetime.utcnow()
            await anchor_record.save()

            # 5. Mark logs as anchored
            for log in unanchored_logs:
                log.blockchain_anchored = True
                log.blockchain_batch_id = batch_id
                log.blockchain_tx_hash = receipt.transaction_id
                await log.save()

            logger.info(f"Successfully anchored batch {batch_id} to blockchain. Tx: {receipt.transaction_id}")
            return {
                "status": "success",
                "batch_id": batch_id,
                "tx_hash": receipt.transaction_id,
                "count": len(unanchored_logs),
                "data_hash": data_hash
            }

        except Exception as e:
            # Mark anchor as failed
            anchor_record.status = "failed"
            await anchor_record.save()
            logger.error(f"Failed to anchor batch {batch_id}: {str(e)}")
            return {"status": "error", "message": str(e), "count": len(unanchored_logs)}

    @staticmethod
    async def verify_batch_integrity(batch_id: str) -> Dict[str, Any]:
        """
        Verifies that the data in MongoDB matches what's stored on the blockchain.
        """
        anchor = await AuditAnchorMongo.find_one(AuditAnchorMongo.batch_id == batch_id)
        if not anchor:
            return {"status": "error", "message": "Batch not found"}

        if anchor.status != "confirmed":
            return {"status": "pending", "message": "Batch is not yet confirmed on-chain"}

        # Fetch logs
        logs = await AuditLogMongo.find(AuditLogMongo.blockchain_batch_id == batch_id).to_list()
        
        # Recompute hash
        hashable_data = []
        for log in logs:
            record = {
                "id": str(log.id),
                "ticket_id": log.ticket_id,
                "action": log.action,
                "actor_id": log.actor_id,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "created_at": log.created_at.isoformat()
            }
            hashable_data.append(record)
            
        current_hash = _compute_sha256(hashable_data)
        
        # 1. Does it match our Mongo record?
        db_match = (current_hash == anchor.data_hash)
        
        # 2. Does it match the blockchain?
        provider = get_blockchain_provider()
        chain_match = await provider.verify_batch(batch_id, current_hash)
        
        if db_match and chain_match:
            is_valid = True
            msg = "Valid: Data perfectly matches blockchain record."
        elif not db_match:
            is_valid = False
            msg = "Tampered: MongoDB logs have been maliciously altered or deleted since anchoring."
        else:
            is_valid = False
            msg = "Tampered: Blockchain hash mismatch."

        return {
            "status": "success",
            "is_valid": is_valid,
            "message": msg,
            "batch_id": batch_id,
            "expected_hash": anchor.data_hash,
            "current_hash": current_hash,
            "tx_hash": anchor.tx_hash,
            "chain_match": chain_match
        }
