"use client";

import OfficerDashboard from "../dashboard/page";

export default function WaterDashboard() {
    const mockUser = {
        name: "Water Supply Head",
        role: "JUNIOR_ENGINEER",
        dept_id: "D01",
        ward_id: 1
    };
    return <OfficerDashboard userOverride={mockUser} forcedRole="JUNIOR_ENGINEER" />;
}
