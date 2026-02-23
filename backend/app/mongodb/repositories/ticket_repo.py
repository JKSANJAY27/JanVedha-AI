"""
Repository: TicketRepo

Async data-access layer for the tickets collection.
All methods are static and use Beanie's query API.
"""
from typing import List, Optional
from datetime import datetime
from beanie import PydanticObjectId

from app.mongodb.models.ticket import TicketMongo
from app.models.ticket import TicketStatus, PriorityLabel


class TicketRepo:
    """CRUD + domain queries for the tickets collection."""

    # ------------------------------------------------------------------ Create
    @staticmethod
    async def create(ticket: TicketMongo) -> TicketMongo:
        """Persist a new ticket and return it with its generated _id."""
        await ticket.insert()
        return ticket

    # ------------------------------------------------------------------ Read
    @staticmethod
    async def get_by_id(ticket_id: str) -> Optional[TicketMongo]:
        """Fetch a ticket by its MongoDB ObjectId string."""
        return await TicketMongo.get(PydanticObjectId(ticket_id))

    @staticmethod
    async def get_by_code(ticket_code: str) -> Optional[TicketMongo]:
        """Fetch a ticket by its human-readable ticket code (e.g. CIV-2024-0001)."""
        return await TicketMongo.find_one(TicketMongo.ticket_code == ticket_code)

    @staticmethod
    async def list_by_dept(dept_id: str, limit: int = 50) -> List[TicketMongo]:
        """Return the most recent tickets for a department."""
        return (
            await TicketMongo.find(TicketMongo.dept_id == dept_id)
            .sort(-TicketMongo.created_at)
            .limit(limit)
            .to_list()
        )

    @staticmethod
    async def list_by_ward(ward_id: int, limit: int = 50) -> List[TicketMongo]:
        """Return the most recent tickets for a ward."""
        return (
            await TicketMongo.find(TicketMongo.ward_id == ward_id)
            .sort(-TicketMongo.created_at)
            .limit(limit)
            .to_list()
        )

    @staticmethod
    async def list_by_status(status: TicketStatus, limit: int = 100) -> List[TicketMongo]:
        """Return tickets filtered by status."""
        return (
            await TicketMongo.find(TicketMongo.status == status)
            .sort(-TicketMongo.created_at)
            .limit(limit)
            .to_list()
        )

    @staticmethod
    async def list_open_critical(limit: int = 50) -> List[TicketMongo]:
        """Return open/assigned CRITICAL tickets — used for escalation dashboards."""
        return (
            await TicketMongo.find(
                TicketMongo.status.in_([TicketStatus.OPEN, TicketStatus.ASSIGNED]),
                TicketMongo.priority_label == PriorityLabel.CRITICAL,
            )
            .sort(-TicketMongo.priority_score)
            .limit(limit)
            .to_list()
        )

    # ------------------------------------------------------------------ Update
    @staticmethod
    async def update_status(
        ticket: TicketMongo,
        new_status: TicketStatus,
    ) -> TicketMongo:
        """Update the status of a ticket in-place."""
        ticket.status = new_status
        if new_status == TicketStatus.CLOSED:
            ticket.resolved_at = datetime.utcnow()
        await ticket.save()
        return ticket

    @staticmethod
    async def assign_officer(
        ticket: TicketMongo,
        officer_id: str,
    ) -> TicketMongo:
        """Assign a ticket to an officer."""
        ticket.assigned_officer_id = officer_id
        ticket.assigned_at = datetime.utcnow()
        ticket.status = TicketStatus.ASSIGNED
        await ticket.save()
        return ticket

    @staticmethod
    async def update_blockchain_hash(
        ticket: TicketMongo, hash_value: str
    ) -> TicketMongo:
        """Persist the blockchain hash after immutable ledger recording."""
        ticket.blockchain_hash = hash_value
        await ticket.save()
        return ticket

    @staticmethod
    async def update_dept(
        ticket: TicketMongo,
        new_dept_id: str,
        new_sla_deadline: datetime,
    ) -> TicketMongo:
        """Reroute ticket to a different department with a fresh SLA deadline."""
        ticket.dept_id = new_dept_id
        ticket.sla_deadline = new_sla_deadline
        await ticket.save()
        return ticket

    # ------------------------------------------------------------------ Count / Aggregate
    @staticmethod
    async def count_total() -> int:
        return await TicketMongo.count()

    @staticmethod
    async def count_by_status(status: TicketStatus) -> int:
        return await TicketMongo.find(TicketMongo.status == status).count()

    @staticmethod
    async def count_active_by_priority(priority: PriorityLabel) -> int:
        return await TicketMongo.find(
            TicketMongo.status.in_([TicketStatus.OPEN, TicketStatus.ASSIGNED]),
            TicketMongo.priority_label == priority,
        ).count()
