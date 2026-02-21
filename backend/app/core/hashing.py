import hashlib, json

def hash_ticket_creation(ticket_id: int, dept_id: str,
                          ward_id: int, created_at: str) -> str:
    data = json.dumps({
        "ticket_id": ticket_id, "dept_id": dept_id,
        "ward_id": ward_id, "created_at": created_at
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()

def hash_status_transition(ticket_id: int, old_status: str,
                            new_status: str, actor_id: int,
                            timestamp: str) -> str:
    data = json.dumps({
        "ticket_id": ticket_id, "old_status": old_status,
        "new_status": new_status, "actor_id": actor_id,
        "timestamp": timestamp
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()

def hash_photo_evidence(before_bytes: bytes, after_bytes: bytes) -> str:
    before_hash = hashlib.sha256(before_bytes).hexdigest()
    after_hash = hashlib.sha256(after_bytes).hexdigest()
    return hashlib.sha256(f"{before_hash}{after_hash}".encode()).hexdigest()

def hash_citizen_verification(ticket_id: int, response: str,
                               timestamp: str) -> str:
    data = json.dumps({
        "ticket_id": ticket_id, "response": response,
        "timestamp": timestamp
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()
