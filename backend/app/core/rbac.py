from app.enums import UserRole

ROLE_PERMISSIONS = {
    UserRole.WARD_OFFICER: {
        "can_view_all_wards": False,
        "can_override_priority": False,
        "can_approve_budget_max": 10_000,
        "can_close_ticket": False,         # only via verification flow
        "can_approve_announcements": True,
        "can_view_predictions": False,
    },
    UserRole.ZONAL_OFFICER: {
        "can_view_all_wards": False,       # only their zone
        "can_override_priority": False,
        "can_approve_budget_max": 1_00_000,
        "can_close_ticket": False,
        "can_approve_announcements": True,
        "can_view_predictions": False,
    },
    UserRole.DEPT_HEAD: {
        "can_view_all_wards": True,        # but only own dept
        "can_override_priority": False,
        "can_approve_budget_max": 10_00_000,
        "can_close_ticket": False,
        "can_approve_announcements": True,
        "can_view_predictions": False,
    },
    UserRole.COMMISSIONER: {
        "can_view_all_wards": True,
        "can_override_priority": True,     # LOGGED IN AUDIT_LOG
        "can_approve_budget_max": None,    # no limit
        "can_close_ticket": False,
        "can_approve_announcements": True,
        "can_view_predictions": True,
    },
    UserRole.COUNCILLOR: {
        "can_view_all_wards": False,
        "can_override_priority": False,
        "can_approve_budget_max": 0,
        "can_close_ticket": False,
        "can_approve_announcements": False,
        "can_view_predictions": False,
    },
    UserRole.SUPER_ADMIN: {
        "can_view_all_wards": False,       # no civic data
        "can_override_priority": False,
        "can_approve_budget_max": 0,
        "can_close_ticket": False,
        "can_approve_announcements": False,
        "can_view_predictions": False,
    },
}

def can_view_ward(user_role: str, user_ward_id: int,
                  user_zone_id: int, requested_ward_id: int) -> bool:
    if user_role == UserRole.COMMISSIONER:
        return True
    if user_role == UserRole.DEPT_HEAD:
        return True   # but filtered by dept in query
    if user_role in (UserRole.ZONAL_OFFICER,):
        # Zone ward membership checked via DB — this is a placeholder
        return True   # actual check in service layer via DB
    if user_role in (UserRole.WARD_OFFICER, UserRole.COUNCILLOR):
        return user_ward_id == requested_ward_id
    return False
