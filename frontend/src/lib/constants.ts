export const DEPT_NAMES: Record<string, string> = {
    D01: "Water Supply",
    D02: "Roads & Bridges",
    D03: "Sewerage & Drainage",
    D04: "Solid Waste Management",
    D05: "Street Lighting",
    D06: "Parks & Recreation",
    D07: "Building & Construction",
    D08: "Health & Sanitation",
    D09: "Traffic & Transport",
    D10: "Fire & Emergency",
};

export const PRIORITY_COLORS: Record<string, string> = {
    CRITICAL: "#DC2626",
    HIGH: "#EA580C",
    MEDIUM: "#CA8A04",
    LOW: "#16A34A",
};

export const PRIORITY_EMOJI: Record<string, string> = {
    CRITICAL: "🔴",
    HIGH: "🟠",
    MEDIUM: "🟡",
    LOW: "🟢",
};

export const STATUS_LABELS: Record<string, string> = {
    OPEN: "Open",
    ASSIGNED: "Assigned",
    IN_PROGRESS: "In Progress",
    PENDING_VERIFICATION: "Pending Verification",
    CLOSED: "Closed",
    CLOSED_UNVERIFIED: "Closed (Unverified)",
    REOPENED: "Reopened",
    REJECTED: "Rejected",
};

export const USER_ROLES: Record<string, string> = {
    SUPER_ADMIN: "Super Admin",
    COMMISSIONER: "Commissioner",
    ZONAL_OFFICER: "Zonal Officer",
    WARD_OFFICER: "Ward Officer",
    DEPT_HEAD: "Department Head",
    COUNCILLOR: "Councillor",
    TECHNICIAN: "Technician",
    PUBLIC_USER: "Public User",
};

export const GRADE_COLORS: Record<string, string> = {
    EXCELLENT: "text-green-700 bg-green-100",
    GOOD: "text-blue-700 bg-blue-100",
    SATISFACTORY: "text-yellow-700 bg-yellow-100",
    NEEDS_IMPROVEMENT: "text-orange-700 bg-orange-100",
    POOR: "text-red-700 bg-red-100",
};

export const CHENNAI_CENTER: [number, number] = [13.0827, 80.2707];
