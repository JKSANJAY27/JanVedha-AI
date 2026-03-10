from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Tuple
from beanie import PydanticObjectId

from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.user import UserMongo
from app.enums import UserRole, PriorityLabel, TicketStatus

DAILY_CAPACITY = 1

def priority_to_int(label: Optional[PriorityLabel]) -> int:
    if label == PriorityLabel.CRITICAL: return 4
    if label == PriorityLabel.HIGH: return 3
    if label == PriorityLabel.MEDIUM: return 2
    if label == PriorityLabel.LOW: return 1
    return 0

def get_workdays(start_date: date, count: int) -> List[date]:
    """Get next `count` workdays (Mon-Sat)."""
    days = []
    current = start_date
    while len(days) < count:
        if current.weekday() < 6: # skip Sunday
            days.append(current)
        current += timedelta(days=1)
    return days

async def generate_smart_schedule(ticket_id: str) -> Optional[Dict[str, Any]]:
    """
    Finds the optimal date and technician for a ticket.
    Capacity: 1 ticket per day per technician.
    CRITICAL issues can preempt LOW/MEDIUM issues if no tech is available.
    """
    target_ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not target_ticket or not target_ticket.dept_id or target_ticket.ward_id is None:
        return None

    technicians = await UserMongo.find(
        UserMongo.role == UserRole.FIELD_STAFF,
        UserMongo.dept_id == target_ticket.dept_id,
        UserMongo.ward_id == target_ticket.ward_id
    ).to_list()

    if not technicians:
        return None

    tech_dict = {str(t.id): t.name for t in technicians}
    tech_ids = list(tech_dict.keys())

    from beanie.operators import In

    # Get all active scheduled tickets for these techs
    scheduled_tickets = await TicketMongo.find(
        In(TicketMongo.technician_id, tech_ids),
        In(TicketMongo.status, [TicketStatus.SCHEDULED, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]),
        TicketMongo.scheduled_date != None,
        TicketMongo.id != target_ticket.id
    ).to_list()

    # Build calendar map: date -> {tech_id: ticket}
    # For simplicity, strip time info.
    calendar: Dict[date, Dict[str, TicketMongo]] = {}
    for t in scheduled_tickets:
        if t.scheduled_date and t.technician_id:
            d = t.scheduled_date.date()
            if d not in calendar:
                calendar[d] = {}
            calendar[d][t.technician_id] = t

    start_date = (datetime.utcnow() + timedelta(days=1)).date() # default start tomorrow
    workdays = get_workdays(start_date, 30)

    max_date = start_date + timedelta(days=30)
    if target_ticket.sla_deadline:
        sla_d = target_ticket.sla_deadline.date()
        if sla_d >= start_date:
            max_date = sla_d

    target_pri_val = priority_to_int(target_ticket.priority_label)

    # 1. Find the earliest naturally free slot
    earliest_free_wd = None
    earliest_free_tech = None
    for wd in workdays:
        cal_day = calendar.get(wd, {})
        for tid in tech_ids:
            if tid not in cal_day:
                earliest_free_wd = wd
                earliest_free_tech = tid
                break
        if earliest_free_wd:
            break

    # 2. Find the earliest possible preemption slot before earliest_free_wd
    earliest_preempt_wd = None
    earliest_preempt_tech = None
    preempt_candidate = None

    if target_pri_val > 1:
        for wd in workdays:
            if earliest_free_wd and wd >= earliest_free_wd:
                break  # No point in preempting if we already found a free slot earlier or on the same day
            
            cal_day = calendar.get(wd, {})
            best_candidate = None
            best_tech = None
            
            for tid, tick in cal_day.items():
                tick_pri_val = priority_to_int(tick.priority_label)
                if tick_pri_val < target_pri_val:
                    if not best_candidate or tick_pri_val < priority_to_int(best_candidate.priority_label):
                        best_candidate = tick
                        best_tech = tid
            
            if best_candidate and best_tech:
                # We found a day where we can preempt a lower priority ticket!
                earliest_preempt_wd = wd
                earliest_preempt_tech = best_tech
                preempt_candidate = best_candidate
                break
    
    # If we found a preemption slot, we take it and move the preempted ticket to the earliest free slot.
    if earliest_preempt_wd and preempt_candidate and earliest_free_wd:
        # Check if moving the preempted ticket to earliest_free_wd breaches its SLA
        can_reschedule = True
        if preempt_candidate.sla_deadline and earliest_free_wd > preempt_candidate.sla_deadline.date():
            can_reschedule = False
            
        if can_reschedule:
            return {
                "suggested_date": datetime.combine(earliest_preempt_wd, datetime.min.time()),
                "suggested_technician_id": earliest_preempt_tech,
                "technician_name": tech_dict[earliest_preempt_tech],
                "postponed_tickets": [
                    {
                        "ticket_id": str(preempt_candidate.id),
                        "ticket_code": preempt_candidate.ticket_code,
                        "old_date": preempt_candidate.scheduled_date,
                        "new_date": datetime.combine(earliest_free_wd, datetime.min.time()),
                        "new_technician_id": earliest_free_tech,
                        "new_technician_name": tech_dict[earliest_free_tech]
                    }
                ]
            }

    # Otherwise, if we at least found a naturally free slot, use it.
    if earliest_free_wd:
        return {
            "suggested_date": datetime.combine(earliest_free_wd, datetime.min.time()),
            "suggested_technician_id": earliest_free_tech,
            "technician_name": tech_dict[earliest_free_tech],
            "postponed_tickets": []
        }

    return None

