"""
Repository: AnnouncementRepo

Async data-access layer for the announcements collection.
"""
from typing import List, Optional
from datetime import datetime
from beanie import PydanticObjectId

from app.mongodb.models.announcement import AnnouncementMongo


class AnnouncementRepo:
    """CRUD for announcements."""

    # ------------------------------------------------------------------ Create
    @staticmethod
    async def create(announcement: AnnouncementMongo) -> AnnouncementMongo:
        """Persist a new (unapproved) announcement draft."""
        await announcement.insert()
        return announcement

    # ------------------------------------------------------------------ Read
    @staticmethod
    async def get_by_id(announcement_id: str) -> Optional[AnnouncementMongo]:
        """Fetch an announcement by ObjectId string."""
        return await AnnouncementMongo.get(PydanticObjectId(announcement_id))

    @staticmethod
    async def list_published(limit: int = 20) -> List[AnnouncementMongo]:
        """Return the most recently published announcements."""
        return (
            await AnnouncementMongo.find(AnnouncementMongo.approved == True)
            .sort(-AnnouncementMongo.published_at)
            .limit(limit)
            .to_list()
        )

    @staticmethod
    async def list_pending_approval() -> List[AnnouncementMongo]:
        """Return announcements awaiting approval."""
        return (
            await AnnouncementMongo.find(AnnouncementMongo.approved == False)
            .sort(-AnnouncementMongo.created_at)
            .to_list()
        )

    # ------------------------------------------------------------------ Update
    @staticmethod
    async def approve(
        announcement: AnnouncementMongo,
        approver_id: str,
    ) -> AnnouncementMongo:
        """Mark an announcement as approved and set the publish timestamp."""
        announcement.approved = True
        announcement.approved_by = approver_id
        announcement.published_at = datetime.utcnow()
        await announcement.save()
        return announcement
