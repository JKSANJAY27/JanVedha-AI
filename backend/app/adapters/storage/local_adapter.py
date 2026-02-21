import os, aiofiles
from app.interfaces.storage_provider import StorageProvider

class LocalStorageAdapter(StorageProvider):
    BASE_PATH = "./uploads"

    async def upload_file(self, file_bytes, destination_path, content_type="image/jpeg"):
        full_path = os.path.join(self.BASE_PATH, destination_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        async with aiofiles.open(full_path, 'wb') as f:
            await f.write(file_bytes)
        return f"http://localhost:8000/uploads/{destination_path}"

    async def get_presigned_upload_url(self, destination_path, content_type, expires_in_seconds=300):
        # For local dev: return a direct upload URL to our own endpoint
        return {"url": f"http://localhost:8000/api/uploads/{destination_path}", "fields": {}}

    async def get_file_url(self, file_path):
        return f"http://localhost:8000/uploads/{file_path}"

    async def delete_file(self, file_path):
        try:
            os.remove(os.path.join(self.BASE_PATH, file_path))
            return True
        except: return False
