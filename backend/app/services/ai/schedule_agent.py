"""
AI Scheduling Agent — priority-based calendar date suggestion.

Logic:
1. Fetch all OPEN/ASSIGNED tickets for a dept+ward, sorted by priority_score DESC.
2. Build a list of workdays (Mon–Sat) for the next 30 days.
3. Assign max DAILY_CAPACITY tickets per day.
4. Critical → days 1-2 | High → days 3-7 | Medium → days 8-15 | Low → 16-30
5. Return {ticket_id, ticket_code, suggested_date, priority_label}
"""
from datetime import datetime, timedelta, date
from typing import List, Dict, Any

from app.mongodb.models.ticket import TicketMongo
from app.enums import TicketStatus, PriorityLabel

DAILY_CAPACITY = 5  # max tickets per day per department

# Priority → earliest allowed scheduling offset (in workdays from today)
PRIORITY_OFFSETS: Dict[str, tuple] = {
    PriorityLabel.CRITICAL: (0, 2),    # days 0–2 (next 1-2 work days)
    PriorityLabel.HIGH:     (2, 7),    # days 2–7
    PriorityLabel.MEDIUM:   (7, 15),   # days 7–15
    PriorityLabel.LOW:      (14, 28),  # days 14–28
}


def _workdays(start: date, count: int) -> List[date]:
    """Return a list of `count` workdays (Mon-Sat) starting from `start`."""
    days = []
    current = start
    while len(days) < count:
        if current.weekday() < 6:  # 0=Mon … 5=Sat; skip Sunday
            days.append(current)
        current += timedelta(days=1)
    return days


async def suggest_schedule(dept_id: str, ward_id: int) -> List[Dict[str, Any]]:
    """
    Generate AI-suggested scheduled dates for all open tickets
    of a given department+ward combination.
    Returns a list of {ticket_id, ticket_code, suggested_date, priority_label}.
    """
    open_statuses = [TicketStatus.OPEN, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]
    query_conditions = [
        TicketMongo.dept_id == dept_id,
        TicketMongo.status.in_(open_statuses),
    ]
    if ward_id:
        query_conditions.append(TicketMongo.ward_id == ward_id)

    tickets = (
        await TicketMongo.find(*query_conditions)
        .sort(-TicketMongo.priority_score)
        .to_list()
    )

    if not tickets:
        return []

    today = datetime.utcnow().date()
    all_workdays = _workdays(today, 35)  # build 35-day window (enough for any bucket)

    # Slot tracker: workday → count of tickets already assigned
    slot_usage: Dict[date, int] = {d: 0 for d in all_workdays}

    results: List[Dict[str, Any]] = []

    for ticket in tickets:
        label = ticket.priority_label or PriorityLabel.LOW
        min_offset, max_offset = PRIORITY_OFFSETS.get(label, (14, 28))

        # Find first workday in the allowed window with available capacity
        suggested: date | None = None
        for wd in all_workdays:
            offset = (wd - today).days
            if min_offset <= offset <= max_offset and slot_usage[wd] < DAILY_CAPACITY:
                suggested = wd
                slot_usage[wd] += 1
                break

        if suggested is None:
            # Overflow: just take the next available workday
            for wd in all_workdays:
                if slot_usage[wd] < DAILY_CAPACITY:
                    suggested = wd
                    slot_usage[wd] += 1
                    break

        if suggested:
            results.append({
                "ticket_id": str(ticket.id),
                "ticket_code": ticket.ticket_code,
                "suggested_date": datetime.combine(suggested, datetime.min.time()),
                "priority_label": label,
                "priority_score": ticket.priority_score,
                "issue_category": ticket.issue_category,
            })

    return results
