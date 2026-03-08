import hashlib
import bcrypt

def get_hash(password: str) -> str:
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")
    return bcrypt.hashpw(digest, bcrypt.gensalt()).decode("utf-8")

def verify(password: str, hashed: str) -> bool:
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")
    return bcrypt.checkpw(digest, hashed.encode("utf-8"))

p = "password123"
h = get_hash(p)
print(f"Password: {p}")
print(f"Hash: {h}")
print(f"Verify: {verify(p, h)}")
