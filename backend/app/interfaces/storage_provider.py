from abc import ABC, abstractmethod

class StorageProvider(ABC):

    @abstractmethod
    async def upload_file(
        self,
        file_bytes: bytes,
        destination_path: str,
        content_type: str = "image/jpeg"
    ) -> str:
        """
        Upload file. Return the public-accessible URL.
        destination_path example: "before_photos/ticket_123/before.jpg"
        """
        pass

    @abstractmethod
    async def get_presigned_upload_url(
        self, destination_path: str, content_type: str, expires_in_seconds: int = 300
    ) -> dict:
        """
        Return a presigned URL for direct browser-to-storage upload.
        Returns: { "url": str, "fields": dict } (S3-style) or { "url": str } (direct PUT)
        """
        pass

    @abstractmethod
    async def get_file_url(self, file_path: str) -> str:
        """Return the CDN/public URL for a stored file."""
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file. Returns True on success."""
        pass
