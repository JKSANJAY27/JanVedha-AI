"use client";

import { useAuth } from "@/context/AuthContext";
import CitizenDashboardPage from "./CitizenDashboard";
import CouncillorDashboard from "./CouncillorDashboard";
import OfficerDashboard from "./OfficerDashboard";

export default function UnifiedDashboard() {
    const { user, isOfficer } = useAuth();
    if (!user) return null;

    if (user.role === "PUBLIC_USER") {
        return <CitizenDashboardPage />;
    }

    if (user.role === "COUNCILLOR") {
        return <CouncillorDashboard />;
    }

    if (isOfficer) {
        return <OfficerDashboard />;
    }

    return null;
}
