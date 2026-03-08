"use client";

import OfficerDashboard from "../dashboard/page";

export default function SanitationDashboard() {
    const mockUser = {
        name: "Sanitation Dept Head",
        role: "JUNIOR_ENGINEER",
        dept_id: "D08",
        ward_id: 1
    };
    return <OfficerDashboard userOverride={mockUser} forcedRole="JUNIOR_ENGINEER" />;
}
