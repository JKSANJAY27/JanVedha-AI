"use client";

import OfficerDashboard from "../dashboard/page";

export default function ElectricalDashboard() {
    const mockUser = {
        name: "Electrical Dept Head",
        role: "JUNIOR_ENGINEER",
        dept_id: "D05", // Street Lighting / Electrical
        ward_id: 1
    };
    return <OfficerDashboard userOverride={mockUser} forcedRole="JUNIOR_ENGINEER" />;
}
