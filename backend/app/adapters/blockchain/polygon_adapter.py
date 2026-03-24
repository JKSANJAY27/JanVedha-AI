"""
Polygon / EVM Adapter using web3.py.
Configured for zero-setup local development using EthereumTesterProvider
and py-solc-x for on-the-fly contract compilation.
"""
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any

from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider
import solcx

from app.interfaces.blockchain_provider import BlockchainProvider, BlockchainRecord
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global state to keep the ephemeral chain alive across requests
_web3_instance: Optional[Web3] = None
_contract_instance = None
_owner_account = None

def get_web3_tester() -> tuple[Web3, Any, str]:
    """
    Initialize the ephemeral EthereumTesterProvider, compile the AuditAnchor contract,
    and deploy it using the first pre-funded account.
    """
    global _web3_instance, _contract_instance, _owner_account
    
    if _web3_instance and _contract_instance:
        return _web3_instance, _contract_instance, _owner_account

    logger.info("Initializing EthereumTesterProvider (Zero-Setup Local EVM)")
    tester_provider = EthereumTesterProvider()
    w3 = Web3(tester_provider)
    
    # tester provides 10 pre-funded accounts with 1,000,000 ETH each
    _owner_account = w3.eth.accounts[0]
    w3.eth.default_account = _owner_account

    # Compile the contract
    contract_path = os.path.join(os.path.dirname(__file__), "../../../contracts/AuditAnchor.sol")
    
    # Ensure solc is installed
    solc_version = "0.8.20"
    try:
        solcx.set_solc_version(solc_version)
    except solcx.exceptions.SolcNotInstalled:
        logger.info(f"Installing solcx {solc_version}...")
        solcx.install_solc(solc_version)
        solcx.set_solc_version(solc_version)

    logger.info("Compiling AuditAnchor.sol...")
    compiled_sol = solcx.compile_files(
        [contract_path],
        output_values=['abi', 'bin'],
        solc_version=solc_version
    )
    
    contract_id, contract_interface = compiled_sol.popitem()
    abi = contract_interface['abi']
    bytecode = contract_interface['bin']

    # Deploy the contract
    logger.info("Deploying AuditAnchor contract to local EVM...")
    AuditAnchor = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = AuditAnchor.constructor().transact({'from': _owner_account})
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    _contract_instance = w3.eth.contract(address=tx_receipt.contractAddress, abi=abi)
    _web3_instance = w3
    
    logger.info(f"AuditAnchor deployed at: {tx_receipt.contractAddress}")
    
    return _web3_instance, _contract_instance, _owner_account


class PolygonAdapter(BlockchainProvider):
    """
    EVM Adapter capable of connecting to real networks (Polygon) or local testers.
    Currently hardcoded to use EthereumTesterProvider for zero-setup demo.
    """
    
    def __init__(self):
        self.w3, self.contract, self.owner = get_web3_tester()

    async def anchor_batch(self, batch_id: str, data_hash: str) -> BlockchainRecord:
        """
        Sends a transaction to anchor a SHA-256 hash on-chain.
        (Since we are using eth-tester, it simulates async via synchronous calls).
        """
        try:
            # Convert strings to bytes32 for Solidity
            # Batch ID is typically a 32-char UUID or similar
            b_batch_id = batch_id.encode('utf-8').ljust(32, b'\0')[:32]
            # Data hash is typically a 64-char hex string (SHA256)
            b_data_hash = bytes.fromhex(data_hash) if hasattr(bytes, "fromhex") else bytes.fromhex(data_hash.replace("0x", ""))
            
            # Send transaction
            tx_hash = self.contract.functions.anchorBatch(b_batch_id, b_data_hash).transact({
                'from': self.owner
            })
            
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return BlockchainRecord(
                hash=data_hash,
                transaction_id=receipt.transactionHash.hex(),
                block_number=receipt.blockNumber,
                recorded_at=datetime.utcnow().isoformat()
            )
        except Exception as e:
            logger.error(f"Failed to anchor batch to EVM: {str(e)}")
            raise e

    async def verify_batch(self, batch_id: str, data_hash: str) -> bool:
        """
        Calls the view function `verifyBatch` on the smart contract.
        """
        try:
            b_batch_id = batch_id.encode('utf-8').ljust(32, b'\0')[:32]
            b_data_hash = bytes.fromhex(data_hash.replace("0x", ""))
            
            is_valid = self.contract.functions.verifyBatch(b_batch_id, b_data_hash).call()
            return is_valid
        except Exception as e:
            logger.error(f"Failed to verify EVM batch: {str(e)}")
            return False

    def get_transaction_url(self, tx_hash: str) -> str:
        """
        Returns a mock local explorer URL. If using real Polygon, this would be polygonscan.com.
        """
        return f"http://localhost-evm-explorer/tx/{tx_hash}"
