"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { officerApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { formatDate, formatRelative } from "@/lib/formatters";
import PriorityBadge from "@/components/PriorityBadge";
import StatusBadge from "@/components/StatusBadge";
import StatCard from "@/components/StatCard";
import Link from "next/link";
import { DEPT_NAMES } from "@/lib/constants";

interface Ticket {
    id: string;
    ticket_code: string;
    status: string;
    dept_id: string;
    issue_category?: string;
    priority_label: string;
    priority_score: number;
    created_at: string;
    sla_deadline?: string;
    ward_id?: number;
    seasonal_alert?: string;
}

const PRIORITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const PRIORITY_COLORS: Record<string, string> = {
    CRITICAL: "border-red-300 bg-red-50",
    HIGH: "border-orange-300 bg-orange-50",
    MEDIUM: "border-yellow-300 bg-yellow-50",
    LOW: "border-green-300 bg-green-50",
};
const PRIORITY_ICONS: Record<string, string> = {
    CRITICAL: "🔴",
    HIGH: "🟠",
    MEDIUM: "🟡",
    LOW: "🟢",
};

export default function OfficerDashboard() {
    const { user, isOfficer } = useAuth();
    const router = useRouter();
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({ CRITICAL: true });
    const [statusFilter, setStatusFilter] = useState("ALL");

    useEffect(() => {
        if (!isOfficer) { router.push("/login"); return; }
        officerApi.getTickets(200)
            .then((res) => setTickets(res.data))
            .catch(() => toast.error("Failed to load tickets"))
            .finally(() => setLoading(false));
    }, []);

    const filtered = statusFilter === "ALL"
        ? tickets
        : tickets.filter((t) => t.status === statusFilter);

    const grouped = PRIORITY_ORDER.reduce<Record<string, Ticket[]>>((acc, p) => {
        acc[p] = filtered.filter((t) => t.priority_label === p);
        return acc;
    }, {});

    const stats = {
        total: tickets.length,
        open: tickets.filter((t) => ["OPEN", "ASSIGNED", "IN_PROGRESS"].includes(t.status)).length,
        critical: tickets.filter((t) => t.priority_label === "CRITICAL").length,
        closed: tickets.filter((t) => t.status === "CLOSED").length,
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-center">
                    <div className="w-14 h-14 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-gray-500 font-medium">Loading your dashboard…</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50">
            {/* Header */}
            <div className="bg-gradient-to-r from-blue-800 to-indigo-900 text-white px-6 py-6">
                <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
                    <div>
                        <p className="text-blue-300 text-sm">
                            {user?.role?.replace(/_/g, " ")}
                            {user?.ward_id && ` — Ward ${user.ward_id}`}
                        </p>
                        <h1 className="text-2xl font-bold mt-0.5">Welcome, {user?.name} 👋</h1>
                    </div>
                    <div className="flex gap-3">
                        <Link
                            href="/officer/reports"
                            className="text-sm bg-white/10 border border-white/20 text-white px-4 py-2 rounded-lg hover:bg-white/20 transition-colors"
                        >
                            📊 Reports
                        </Link>
                        <Link
                            href="/map"
                            className="text-sm bg-white/10 border border-white/20 text-white px-4 py-2 rounded-lg hover:bg-white/20 transition-colors"
                        >
                            🗺️ Issue Map
                        </Link>
                    </div>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">
                {/* Stats */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <StatCard label="Total Tickets" value={stats.total} icon="📋" color="blue" />
                    <StatCard label="Active" value={stats.open} icon="⚡" color="orange" />
                    <StatCard label="Critical" value={stats.critical} icon="🚨" color="red" />
                    <StatCard label="Resolved" value={stats.closed} icon="✅" color="green" />
                </div>

                {/* Filter bar */}
                <div className="flex items-center gap-3 flex-wrap">
                    <p className="text-sm font-medium text-gray-600">Filter by status:</p>
                    {["ALL", "OPEN", "ASSIGNED", "IN_PROGRESS", "PENDING_VERIFICATION", "CLOSED"].map((s) => (
                        <button
                            key={s}
                            onClick={() => setStatusFilter(s)}
                            className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all ${statusFilter === s
                                    ? "bg-blue-600 text-white shadow-sm"
                                    : "bg-white text-gray-600 border border-gray-200 hover:border-blue-300"
                                }`}
                        >
                            {s.replace(/_/g, " ")}
                        </button>
                    ))}
                </div>

                {/* Priority groups */}
                {PRIORITY_ORDER.map((priority) => {
                    const group = grouped[priority] ?? [];
                    const isExpanded = expandedGroups[priority];
                    return (
                        <div key={priority} className={`rounded-2xl border-l-4 ${PRIORITY_COLORS[priority]} border shadow-sm overflow-hidden`}>
                            <button
                                className="w-full flex items-center justify-between px-5 py-4 hover:bg-black/5 transition-colors"
                                onClick={() => setExpandedGroups((prev) => ({ ...prev, [priority]: !prev[priority] }))}
                            >
                                <div className="flex items-center gap-3">
                                    <span className="text-xl">{PRIORITY_ICONS[priority]}</span>
                                    <h3 className="font-bold text-gray-800 text-sm">
                                        {priority} — {group.length} ticket{group.length !== 1 ? "s" : ""}
                                    </h3>
                                </div>
                                <span className="text-gray-500 text-sm">{isExpanded ? "▲" : "▼"}</span>
                            </button>

                            {isExpanded && (
                                <div className="divide-y divide-white/60">
                                    {group.length === 0 ? (
                                        <p className="text-sm text-gray-400 px-5 py-4 italic">No {priority.toLowerCase()} tickets</p>
                                    ) : (
                                        group.map((ticket, i) => (
                                            <motion.div
                                                key={ticket.id}
                                                initial={{ opacity: 0 }}
                                                animate={{ opacity: 1 }}
                                                transition={{ delay: i * 0.03 }}
                                                className="px-5 py-4 bg-white hover:bg-gray-50 transition-colors"
                                            >
                                                <div className="flex flex-wrap items-center justify-between gap-3">
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                                                            <span className="font-mono text-sm font-bold text-blue-700">{ticket.ticket_code}</span>
                                                            <StatusBadge status={ticket.status} size="sm" />
                                                            {ticket.seasonal_alert && (
                                                                <span className="text-xs bg-orange-100 text-orange-700 rounded-full px-2 py-0.5">🌤️ Seasonal Alert</span>
                                                            )}
                                                        </div>
                                                        <p className="text-sm text-gray-700 font-medium truncate">
                                                            {ticket.issue_category || "General Issue"}
                                                        </p>
                                                        <div className="flex gap-4 mt-1 flex-wrap">
                                                            <span className="text-xs text-gray-400">Dept: {DEPT_NAMES[ticket.dept_id] ?? ticket.dept_id}</span>
                                                            {ticket.ward_id && <span className="text-xs text-gray-400">Ward {ticket.ward_id}</span>}
                                                            <span className="text-xs text-gray-400">{formatRelative(ticket.created_at)}</span>
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <PriorityBadge label={ticket.priority_label} score={ticket.priority_score} size="sm" />
                                                        <Link
                                                            href={`/officer/tickets/${ticket.id}`}
                                                            className="text-sm font-medium text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 rounded-lg px-3 py-1.5 transition-colors"
                                                        >
                                                            View →
                                                        </Link>
                                                    </div>
                                                </div>
                                            </motion.div>
                                        ))
                                    )}
                                </div>
                            )}
                        </div>
                    );
                })}

                {filtered.length === 0 && !loading && (
                    <div className="text-center py-16 text-gray-400">
                        <div className="text-5xl mb-3">🎉</div>
                        <p className="text-lg font-medium">No tickets found!</p>
                        <p className="text-sm mt-1">All clear for this filter.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
