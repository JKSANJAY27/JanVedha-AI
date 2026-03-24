// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title AuditAnchor
 * @dev Stores SHA-256 hashes of audit log batches on-chain to guarantee immutability.
 * For JanVedha Civic Platform.
 */
contract AuditAnchor {
    address public owner;

    struct Batch {
        bytes32 dataHash;
        uint256 timestamp;
        uint256 blockNumber;
        bool exists;
    }

    // Mapping from Batch ID (e.g. daily/hourly UUID string converted to bytes32) to Batch details
    mapping(bytes32 => Batch) public batches;

    event BatchAnchored(bytes32 indexed batchId, bytes32 dataHash, uint256 timestamp);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can anchor batches");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @dev Anchors a new batch of audit logs.
     * @param batchId Unique identifier for this batch.
     * @param dataHash SHA-256 hash of the audit log data (Merkle root or simple digest).
     */
    function anchorBatch(bytes32 batchId, bytes32 dataHash) external onlyOwner {
        require(!batches[batchId].exists, "Batch ID already anchored");

        batches[batchId] = Batch({
            dataHash: dataHash,
            timestamp: block.timestamp,
            blockNumber: block.number,
            exists: true
        });

        emit BatchAnchored(batchId, dataHash, block.timestamp);
    }

    /**
     * @dev Verifies if a specific data hash matches the anchored hash for a given batch.
     * @param batchId The batch identifier.
     * @param dataHash The SHA-256 hash to verify.
     * @return bool True if the hash matches and exists, false otherwise.
     */
    function verifyBatch(bytes32 batchId, bytes32 dataHash) external view returns (bool) {
        if (!batches[batchId].exists) {
            return false;
        }
        return batches[batchId].dataHash == dataHash;
    }

    /**
     * @dev Gets details of an anchored batch.
     * @param batchId The batch identifier.
     * @return _dataHash The SHA-256 data hash.
     * @return _timestamp The block timestamp when anchored.
     * @return _blockNumber The block number when anchored.
     */
    function getBatch(bytes32 batchId) external view returns (bytes32 _dataHash, uint256 _timestamp, uint256 _blockNumber) {
        require(batches[batchId].exists, "Batch not found");
        Batch memory b = batches[batchId];
        return (b.dataHash, b.timestamp, b.blockNumber);
    }
}
