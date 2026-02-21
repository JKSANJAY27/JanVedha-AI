from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class BlockchainRecord:
    hash: str
    transaction_id: str | None
    block_number: int | None
    recorded_at: str

class BlockchainProvider(ABC):
    @abstractmethod
    async def record_hash(self, data_hash: str, event_type: str) -> BlockchainRecord:
        """Write a hash to the blockchain. Returns transaction reference."""
        pass

    @abstractmethod
    async def verify_hash(self, data_hash: str) -> bool:
        """Verify a hash exists on chain."""
        pass
