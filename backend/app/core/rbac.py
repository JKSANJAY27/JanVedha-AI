from app.enums import UserRole

ROLE_PERMISSIONS = {
    UserRole.COUNCILLOR: {
        "can_view_all_wards": False,
        "can_override_priority": False,
        "can_assign_tickets": False,
        "can_close_ticket": False,
        "can_escalate_ticket": True,
        "can_reopen_ticket": True,
        "can_approve_announcements": False,
        "can_view_analytics": True,
    },
    UserRole.SUPERVISOR: {
        "can_view_all_wards": False,
        "can_override_priority": True,
        "can_assign_tickets": True,
        "can_close_ticket": True,
        "can_escalate_ticket": False,
        "can_reopen_ticket": False,
        "can_approve_announcements": True,
        "can_view_analytics": True,
    },
    UserRole.JUNIOR_ENGINEER: {
        "can_view_all_wards": False,
        "can_override_priority": False,
        "can_assign_tickets": True,
        "can_close_ticket": False,
        "can_escalate_ticket": False,
        "can_reopen_ticket": False,
        "can_approve_announcements": False,
        "can_view_analytics": False,
    },
    UserRole.FIELD_STAFF: {
        "can_view_all_wards": False,
        "can_override_priority": False,
        "can_assign_tickets": False,
        "can_close_ticket": False,
        "can_escalate_ticket": False,
        "can_reopen_ticket": False,
        "can_approve_announcements": False,
        "can_view_analytics": False,
    },
    UserRole.SUPER_ADMIN: {
        "can_view_all_wards": True,
        "can_override_priority": True,
        "can_assign_tickets": True,
        "can_close_ticket": True,
        "can_escalate_ticket": True,
        "can_reopen_ticket": True,
        "can_approve_announcements": True,
        "can_view_analytics": True,
    },
}

def can_view_ward(user_role: str, user_ward_id: int,
                  user_zone_id: int, requested_ward_id: int) -> bool:
    if user_role == UserRole.SUPER_ADMIN:
        return True
    if user_role in (UserRole.COUNCILLOR, UserRole.SUPERVISOR, UserRole.JUNIOR_ENGINEER, UserRole.FIELD_STAFF):
        return user_ward_id == requested_ward_id
    return False
