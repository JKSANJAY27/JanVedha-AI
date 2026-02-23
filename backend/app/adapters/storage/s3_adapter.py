from app.interfaces.storage_provider import StorageProvider


class S3Adapter(StorageProvider):
    """Stub implementation of AWS S3 storage provider."""

    async def upload_file(
        self,
        file_bytes: bytes,
        destination_path: str,
        content_type: str = "image/jpeg"
    ) -> str:
        """Stub implementation - returns a mock S3 URL."""
        return f"https://janvedha-bucket.s3.amazonaws.com/{destination_path}"

    async def get_presigned_upload_url(
        self, destination_path: str, content_type: str, expires_in_seconds: int = 300
    ) -> dict:
        """Stub implementation - returns a mock presigned URL."""
        return {
            "url": f"https://janvedha-bucket.s3.amazonaws.com/presign/{destination_path}",
            "fields": {}
        }

    async def get_file_url(self, file_path: str) -> str:
        """Stub implementation - returns a mock S3 file URL."""
        return f"https://janvedha-bucket.s3.amazonaws.com/{file_path}"

    async def delete_file(self, file_path: str) -> bool:
        """Stub implementation - always returns success."""
        return True
