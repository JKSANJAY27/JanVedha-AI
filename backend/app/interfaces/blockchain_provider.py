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
    async def anchor_batch(self, batch_id: str, data_hash: str) -> BlockchainRecord:
        """Anchor a batch to the blockchain. Returns transaction reference."""
        raise NotImplementedError

    @abstractmethod
    async def verify_batch(self, batch_id: str, data_hash: str) -> bool:
        """Verify a batch hash exists on chain."""
        raise NotImplementedError

    @abstractmethod
    def get_transaction_url(self, tx_hash: str) -> str:
        """Return the block explorer URL for a given transaction hash."""
        raise NotImplementedError
