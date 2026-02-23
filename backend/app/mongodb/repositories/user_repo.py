"""
Repository: UserRepo

Async data-access layer for the users collection.
"""
from typing import Optional
from beanie import PydanticObjectId

from app.mongodb.models.user import UserMongo


class UserRepo:
    """CRUD for the users collection."""

    # ------------------------------------------------------------------ Create
    @staticmethod
    async def create(user: UserMongo) -> UserMongo:
        """Persist a new user and return it with its generated _id."""
        await user.insert()
        return user

    # ------------------------------------------------------------------ Read
    @staticmethod
    async def get_by_id(user_id: str) -> Optional[UserMongo]:
        """Fetch a user by ObjectId string."""
        return await UserMongo.get(PydanticObjectId(user_id))

    @staticmethod
    async def get_by_phone(phone: str) -> Optional[UserMongo]:
        """Fetch a user by phone number (unique)."""
        return await UserMongo.find_one(UserMongo.phone == phone)

    @staticmethod
    async def get_by_email(email: str) -> Optional[UserMongo]:
        """Fetch a user by email address (unique)."""
        return await UserMongo.find_one(UserMongo.email == email)

    # ------------------------------------------------------------------ Update
    @staticmethod
    async def set_active(user: UserMongo, is_active: bool) -> UserMongo:
        """Enable or disable a user account."""
        user.is_active = is_active
        await user.save()
        return user

    @staticmethod
    async def update_password_hash(user: UserMongo, new_hash: str) -> UserMongo:
        """Replace the password hash (e.g. after a password reset)."""
        user.password_hash = new_hash
        await user.save()
        return user
