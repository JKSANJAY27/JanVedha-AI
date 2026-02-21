from app.interfaces.blockchain_provider import BlockchainProvider, BlockchainRecord
from datetime import datetime

class StubBlockchainAdapter(BlockchainProvider):
    async def record_hash(self, data_hash, event_type):
        # Just logs — no real blockchain
        return BlockchainRecord(
            hash=data_hash, transaction_id=None,
            block_number=None, recorded_at=datetime.utcnow().isoformat()
        )
    async def verify_hash(self, data_hash):
        return True  # Always true in stub
