from app.interfaces.blockchain_provider import BlockchainProvider, BlockchainRecord
from datetime import datetime

class StubBlockchainAdapter(BlockchainProvider):
    async def anchor_batch(self, batch_id: str, data_hash: str) -> BlockchainRecord:
        # Just logs — no real blockchain
        return BlockchainRecord(
            hash=data_hash, transaction_id=None,
            block_number=None, recorded_at=datetime.utcnow().isoformat()
        )

    async def verify_batch(self, batch_id: str, data_hash: str) -> bool:
        return True  # Always true in stub

    def get_transaction_url(self, tx_hash: str) -> str:
        return f"stub-explorer://{tx_hash}"
