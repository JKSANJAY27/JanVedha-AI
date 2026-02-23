"""
Repository: DepartmentRepo

Async data-access layer for the departments collection.
"""
from typing import List, Optional

from app.mongodb.models.department import DepartmentMongo


class DepartmentRepo:
    """Read + upsert operations for departments (mostly static reference data)."""

    @staticmethod
    async def get_by_id(dept_id: str) -> Optional[DepartmentMongo]:
        """Fetch a department by its natural dept_id key (e.g. 'PWD')."""
        return await DepartmentMongo.find_one(DepartmentMongo.dept_id == dept_id)

    @staticmethod
    async def list_all() -> List[DepartmentMongo]:
        """Return all departments sorted by name."""
        return await DepartmentMongo.find_all().sort(+DepartmentMongo.dept_name).to_list()

    @staticmethod
    async def upsert(dept: DepartmentMongo) -> DepartmentMongo:
        """
        Insert or replace a department document by dept_id.
        Used during seeding / migrations.
        """
        existing = await DepartmentMongo.find_one(DepartmentMongo.dept_id == dept.dept_id)
        if existing:
            existing.dept_name = dept.dept_name
            existing.handles = dept.handles
            existing.sla_days = dept.sla_days
            existing.is_external = dept.is_external
            existing.parent_body = dept.parent_body
            existing.escalation_role = dept.escalation_role
            await existing.save()
            return existing
        await dept.insert()
        return dept
