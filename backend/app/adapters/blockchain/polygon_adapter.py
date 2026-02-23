from app.interfaces.blockchain_provider import BlockchainProvider, BlockchainRecord
from datetime import datetime


class PolygonAdapter(BlockchainProvider):
    """Stub implementation of Polygon blockchain provider."""

    async def record_hash(self, data_hash: str, event_type: str) -> BlockchainRecord:
        """Stub implementation - returns a mock blockchain record."""
        return BlockchainRecord(
            hash=data_hash,
            transaction_id=f"tx_{data_hash[:16]}",
            block_number=12345,
            recorded_at=datetime.now().isoformat()
        )

    async def verify_hash(self, data_hash: str) -> bool:
        """Stub implementation - always returns True."""
        return True
