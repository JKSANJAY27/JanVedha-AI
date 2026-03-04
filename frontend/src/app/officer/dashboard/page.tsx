"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { officerApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { formatRelative } from "@/lib/formatters";
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
    assigned_officer_id?: string;
    technician_id?: string;
    scheduled_date?: string;
    ai_suggested_date?: string;
}

interface DeptStat {
    dept_id: string;
    open: number;
    closed: number;
    overdue: number;
    critical: number;
}

interface DashboardSummary {
    total: number;
    open: number;
    closed: number;
    overdue: number;
    critical: number;
    avg_satisfaction: number | null;
    by_department: DeptStat[];
}

const PRIORITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const PRIORITY_COLORS: Record<string, string> = {
    CRITICAL: "border-red-300 bg-red-50",
    HIGH: "border-orange-300 bg-orange-50",
    MEDIUM: "border-yellow-300 bg-yellow-50",
    LOW: "border-green-300 bg-green-50",
};
const PRIORITY_ICONS: Record<string, string> = {
    CRITICAL: "🔴", HIGH: "🟠", MEDIUM: "🟡", LOW: "🟢",
};

// ─── Ticket List Sub-component ────────────────────────────────────────────────

function TicketList({ tickets, showAssign, onStatusUpdate }: {
    tickets: Ticket[];
    showAssign?: boolean;
    onStatusUpdate?: (id: string, status: string) => void;
}) {
    const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({ CRITICAL: true });
    const [statusFilter, setStatusFilter] = useState("ALL");
    const [updatingId, setUpdatingId] = useState<string | null>(null);

    const filtered = statusFilter === "ALL"
        ? tickets
        : tickets.filter(t => t.status === statusFilter);

    const grouped = PRIORITY_ORDER.reduce<Record<string, Ticket[]>>((acc, p) => {
        acc[p] = filtered.filter(t => t.priority_label === p);
        return acc;
    }, {});

    const handleQuickStatus = async (ticketId: string, newStatus: string) => {
        setUpdatingId(ticketId);
        try {
            await officerApi.updateStatus(ticketId, newStatus);
            toast.success("Status updated");
            onStatusUpdate?.(ticketId, newStatus);
        } catch {
            toast.error("Update failed");
        } finally {
            setUpdatingId(null);
        }
    };

    const getSlaCountdown = (deadline?: string) => {
        if (!deadline) return null;
        const diff = new Date(deadline).getTime() - Date.now();
        const days = Math.ceil(diff / 86400000);
        if (days < 0) return { label: `${Math.abs(days)}d overdue`, cls: "text-red-600 font-bold" };
        if (days <= 1) return { label: "Due today!", cls: "text-red-500 font-bold" };
        if (days <= 3) return { label: `${days}d left`, cls: "text-orange-500 font-semibold" };
        return { label: `${days}d left`, cls: "text-gray-400" };
    };

    return (
        <div className="space-y-4">
            {/* Filter bar */}
            <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-medium text-gray-600">Filter:</p>
                {["ALL", "OPEN", "ASSIGNED", "IN_PROGRESS", "AWAITING_MATERIAL", "PENDING_VERIFICATION", "CLOSED"].map(s => (
                    <button key={s} onClick={() => setStatusFilter(s)}
                        className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all ${statusFilter === s
                            ? "bg-blue-600 text-white shadow-sm" : "bg-white text-gray-600 border border-gray-200 hover:border-blue-300"}`}>
                        {s.replace(/_/g, " ")}
                    </button>
                ))}
            </div>

            {/* Priority groups */}
            {PRIORITY_ORDER.map(priority => {
                const group = grouped[priority] ?? [];
                const isExpanded = expandedGroups[priority];
                return (
                    <div key={priority} className={`rounded-2xl border-l-4 ${PRIORITY_COLORS[priority]} border shadow-sm overflow-hidden`}>
                        <button className="w-full flex items-center justify-between px-5 py-4 hover:bg-black/5 transition-colors"
                            onClick={() => setExpandedGroups(prev => ({ ...prev, [priority]: !prev[priority] }))}>
                            <div className="flex items-center gap-3">
                                <span className="text-xl">{PRIORITY_ICONS[priority]}</span>
                                <h3 className="font-bold text-gray-800 text-sm">{priority} — {group.length} ticket{group.length !== 1 ? "s" : ""}</h3>
                            </div>
                            <span className="text-gray-500 text-sm">{isExpanded ? "▲" : "▼"}</span>
                        </button>

                        {isExpanded && (
                            <div className="divide-y divide-white/60">
                                {group.length === 0 ? (
                                    <p className="text-sm text-gray-400 px-5 py-4 italic">No {priority.toLowerCase()} tickets</p>
                                ) : (
                                    group.map((ticket, i) => {
                                        const sla = getSlaCountdown(ticket.sla_deadline);
                                        return (
                                            <motion.div key={ticket.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.03 }}
                                                className="px-5 py-4 bg-white hover:bg-gray-50 transition-colors">
                                                <div className="flex flex-wrap items-start justify-between gap-3">
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                                                            <span className="font-mono text-sm font-bold text-blue-700">{ticket.ticket_code}</span>
                                                            <StatusBadge status={ticket.status} size="sm" />
                                                            {ticket.seasonal_alert && (
                                                                <span className="text-xs bg-orange-100 text-orange-700 rounded-full px-2 py-0.5">🌤️ Seasonal</span>
                                                            )}
                                                            {ticket.scheduled_date && (
                                                                <span className="text-xs bg-purple-100 text-purple-700 rounded-full px-2 py-0.5">
                                                                    📅 {new Date(ticket.scheduled_date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                                                                </span>
                                                            )}
                                                        </div>
                                                        <p className="text-sm text-gray-700 font-medium truncate">{ticket.issue_category || "General Issue"}</p>
                                                        <div className="flex gap-3 mt-1 flex-wrap text-xs text-gray-400">
                                                            <span>Dept: {DEPT_NAMES[ticket.dept_id] ?? ticket.dept_id}</span>
                                                            {ticket.ward_id && <span>Ward {ticket.ward_id}</span>}
                                                            <span>{formatRelative(ticket.created_at)}</span>
                                                            {sla && <span className={sla.cls}>⏱ {sla.label}</span>}
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        <PriorityBadge label={ticket.priority_label} score={ticket.priority_score} size="sm" />
                                                        {showAssign && ticket.status === "IN_PROGRESS" && (
                                                            <button
                                                                disabled={updatingId === ticket.id}
                                                                onClick={() => handleQuickStatus(ticket.id, "PENDING_VERIFICATION")}
                                                                className="text-xs bg-cyan-50 hover:bg-cyan-100 text-cyan-700 border border-cyan-200 rounded-lg px-2.5 py-1.5 font-medium transition-colors disabled:opacity-50">
                                                                Mark Done →
                                                            </button>
                                                        )}
                                                        {showAssign && ticket.status === "OPEN" && (
                                                            <button
                                                                disabled={updatingId === ticket.id}
                                                                onClick={() => handleQuickStatus(ticket.id, "IN_PROGRESS")}
                                                                className="text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded-lg px-2.5 py-1.5 font-medium transition-colors disabled:opacity-50">
                                                                Start →
                                                            </button>
                                                        )}
                                                        <Link href={`/officer/tickets/${ticket.id}`}
                                                            className="text-sm font-medium text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 rounded-lg px-3 py-1.5 transition-colors">
                                                            View →
                                                        </Link>
                                                    </div>
                                                </div>
                                            </motion.div>
                                        );
                                    })
                                )}
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}

// ─── PGO Supervisory View ─────────────────────────────────────────────────────

function PGODashboard({ user }: { user: { name: string; ward_id?: number; role: string } }) {
    const [summary, setSummary] = useState<DashboardSummary | null>(null);
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([officerApi.getDashboardSummary(), officerApi.getTickets(200)])
            .then(([s, t]) => { setSummary(s.data); setTickets(t.data); })
            .catch(() => toast.error("Failed to load dashboard"))
            .finally(() => setLoading(false));
    }, []);

    const overdue = tickets.filter(t =>
        t.sla_deadline && new Date(t.sla_deadline) < new Date() &&
        !["CLOSED", "REJECTED"].includes(t.status)
    );

    if (loading) return <div className="flex justify-center py-20"><div className="w-10 h-10 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" /></div>;

    return (
        <div className="space-y-8">
            {/* Stats Row */}
            {summary && (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                    <StatCard label="Total" value={summary.total} icon="📋" color="blue" />
                    <StatCard label="Open" value={summary.open} icon="⚡" color="orange" />
                    <StatCard label="Closed" value={summary.closed} icon="✅" color="green" />
                    <StatCard label="Overdue" value={summary.overdue} icon="⚠️" color="red" />
                    <StatCard label="Critical" value={summary.critical} icon="🚨" color="red" />
                    <StatCard label="Satisfaction" value={summary.avg_satisfaction !== null ? `${summary.avg_satisfaction}/5` : "N/A"} icon="⭐" color="purple" />
                </div>
            )}

            {/* Dept breakdown */}
            {summary && summary.by_department.length > 0 && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                    <div className="px-5 py-4 border-b border-gray-100">
                        <h2 className="font-bold text-gray-800 text-sm flex items-center gap-2">🏢 Department Overview</h2>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 p-4">
                        {summary.by_department.map(d => (
                            <div key={d.dept_id} className={`rounded-xl border p-3 text-xs ${d.overdue > 0 ? "border-red-200 bg-red-50" : "border-gray-100 bg-gray-50"}`}>
                                <p className="font-bold text-gray-700 mb-2">{DEPT_NAMES[d.dept_id] ?? d.dept_id}</p>
                                <div className="grid grid-cols-2 gap-1">
                                    <div><p className="text-gray-400">Open</p><p className="font-bold text-orange-600">{d.open}</p></div>
                                    <div><p className="text-gray-400">Closed</p><p className="font-bold text-green-600">{d.closed}</p></div>
                                    <div><p className="text-gray-400">Overdue</p><p className={`font-bold ${d.overdue > 0 ? "text-red-600" : "text-gray-400"}`}>{d.overdue}</p></div>
                                    <div><p className="text-gray-400">Critical</p><p className={`font-bold ${d.critical > 0 ? "text-red-700" : "text-gray-400"}`}>{d.critical}</p></div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Overdue alert */}
            {overdue.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-2xl p-4">
                    <h3 className="font-bold text-red-800 text-sm mb-3 flex items-center gap-2">
                        ⚠️ SLA Breached — {overdue.length} tickets require immediate attention
                    </h3>
                    <div className="space-y-2">
                        {overdue.slice(0, 5).map(t => (
                            <div key={t.id} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 text-xs shadow-sm">
                                <div>
                                    <span className="font-mono font-bold text-red-700">{t.ticket_code}</span>
                                    <span className="ml-2 text-gray-500">{t.issue_category ?? "Issue"}</span>
                                    <span className="ml-2 text-gray-400">{DEPT_NAMES[t.dept_id] ?? t.dept_id}</span>
                                </div>
                                <Link href={`/officer/tickets/${t.id}`} className="text-red-600 hover:text-red-800 font-semibold">Review →</Link>
                            </div>
                        ))}
                        {overdue.length > 5 && <p className="text-xs text-red-500 pl-1">+{overdue.length - 5} more overdue</p>}
                    </div>
                </div>
            )}

            {/* Full ticket list */}
            <TicketList tickets={tickets} />
        </div>
    );
}

// ─── Dept Officer Operational View ───────────────────────────────────────────

function DeptOfficerDashboard({ user }: { user: { name: string; dept_id?: string; ward_id?: number } }) {
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        officerApi.getTickets(200)
            .then(res => setTickets(res.data))
            .catch(() => toast.error("Failed to load tickets"))
            .finally(() => setLoading(false));
    }, []);

    const handleStatusUpdate = (id: string, status: string) => {
        setTickets(prev => prev.map(t => t.id === id ? { ...t, status } : t));
    };

    const stats = {
        total: tickets.length,
        open: tickets.filter(t => ["OPEN", "ASSIGNED", "IN_PROGRESS"].includes(t.status)).length,
        critical: tickets.filter(t => t.priority_label === "CRITICAL").length,
        awaiting: tickets.filter(t => t.status === "AWAITING_MATERIAL").length,
    };

    if (loading) return <div className="flex justify-center py-20"><div className="w-10 h-10 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" /></div>;

    return (
        <div className="space-y-8">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <StatCard label="Dept Tickets" value={stats.total} icon="📋" color="blue" />
                <StatCard label="Active" value={stats.open} icon="⚡" color="orange" />
                <StatCard label="Critical" value={stats.critical} icon="🚨" color="red" />
                <StatCard label="Awaiting Material" value={stats.awaiting} icon="📦" color="purple" />
            </div>
            <TicketList tickets={tickets} showAssign onStatusUpdate={handleStatusUpdate} />
        </div>
    );
}

// ─── Technician Task Board ────────────────────────────────────────────────────

function TechnicianDashboard() {
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        officerApi.getMyTickets()
            .then(res => setTickets(res.data))
            .catch(() => toast.error("Failed to load your tasks"))
            .finally(() => setLoading(false));
    }, []);

    const handleStatusUpdate = (id: string, status: string) => {
        setTickets(prev => prev.map(t => t.id === id ? { ...t, status } : t));
    };

    const stats = {
        total: tickets.length,
        inProgress: tickets.filter(t => t.status === "IN_PROGRESS").length,
        pending: tickets.filter(t => ["OPEN", "ASSIGNED"].includes(t.status)).length,
        done: tickets.filter(t => t.status === "PENDING_VERIFICATION").length,
    };

    const STATUS_FLOW: Record<string, { next: string; label: string; cls: string }> = {
        OPEN: { next: "IN_PROGRESS", label: "▶ Start Work", cls: "bg-blue-600 text-white" },
        ASSIGNED: { next: "IN_PROGRESS", label: "▶ Start Work", cls: "bg-blue-600 text-white" },
        IN_PROGRESS: { next: "AWAITING_MATERIAL", label: "📦 Need Material", cls: "bg-yellow-500 text-white" },
        AWAITING_MATERIAL: { next: "IN_PROGRESS", label: "✅ Got Material", cls: "bg-green-500 text-white" },
    };

    if (loading) return <div className="flex justify-center py-20"><div className="w-10 h-10 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" /></div>;

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <StatCard label="My Tasks" value={stats.total} icon="📋" color="blue" />
                <StatCard label="Pending" value={stats.pending} icon="⏳" color="orange" />
                <StatCard label="In Progress" value={stats.inProgress} icon="🔧" color="purple" />
                <StatCard label="Awaiting Check" value={stats.done} icon="✅" color="green" />
            </div>

            {tickets.length === 0 ? (
                <div className="text-center py-20 text-gray-400">
                    <p className="text-5xl mb-3">🎉</p>
                    <p className="text-lg font-medium">No tasks assigned yet!</p>
                    <p className="text-sm mt-1">Check back with your supervisor.</p>
                </div>
            ) : (
                <div className="space-y-4">
                    {tickets.map((ticket, i) => {
                        const nextAction = STATUS_FLOW[ticket.status];
                        const slaMs = ticket.sla_deadline ? new Date(ticket.sla_deadline).getTime() - Date.now() : null;
                        const slaDays = slaMs !== null ? Math.ceil(slaMs / 86400000) : null;
                        return (
                            <motion.div key={ticket.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
                                className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div>
                                        <div className="flex items-center gap-2 flex-wrap mb-1">
                                            <span className="font-mono font-bold text-blue-700">{ticket.ticket_code}</span>
                                            <StatusBadge status={ticket.status} size="sm" />
                                            <PriorityBadge label={ticket.priority_label} score={ticket.priority_score} size="sm" />
                                        </div>
                                        <p className="text-sm font-medium text-gray-800">{ticket.issue_category ?? "General Issue"}</p>
                                        <div className="flex gap-3 mt-1 text-xs text-gray-400 flex-wrap">
                                            <span>Dept: {DEPT_NAMES[ticket.dept_id] ?? ticket.dept_id}</span>
                                            {ticket.scheduled_date && (
                                                <span className="text-purple-600 font-medium">
                                                    📅 {new Date(ticket.scheduled_date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                                                </span>
                                            )}
                                            {slaDays !== null && (
                                                <span className={slaDays < 0 ? "text-red-600 font-bold" : slaDays <= 2 ? "text-orange-500 font-semibold" : ""}>
                                                    {slaDays < 0 ? `⚠️ ${Math.abs(slaDays)}d overdue` : `⏱ ${slaDays}d left`}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {nextAction && (
                                            <button
                                                onClick={async () => {
                                                    try {
                                                        await officerApi.updateStatus(ticket.id, nextAction.next);
                                                        handleStatusUpdate(ticket.id, nextAction.next);
                                                        toast.success("Status updated");
                                                    } catch { toast.error("Update failed"); }
                                                }}
                                                className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors ${nextAction.cls}`}>
                                                {nextAction.label}
                                            </button>
                                        )}
                                        {ticket.status === "IN_PROGRESS" && (
                                            <button
                                                onClick={async () => {
                                                    try {
                                                        await officerApi.updateStatus(ticket.id, "PENDING_VERIFICATION");
                                                        handleStatusUpdate(ticket.id, "PENDING_VERIFICATION");
                                                        toast.success("Marked for verification!");
                                                    } catch { toast.error("Update failed"); }
                                                }}
                                                className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-green-600 text-white transition-colors">
                                                Work Done ✓
                                            </button>
                                        )}
                                        <Link href={`/officer/tickets/${ticket.id}`}
                                            className="text-sm font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg px-3 py-1.5 transition-colors">
                                            View →
                                        </Link>
                                    </div>
                                </div>
                            </motion.div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

// ─── Main Dashboard Controller ────────────────────────────────────────────────

export default function OfficerDashboard() {
    const { user, isOfficer, isWardPGO, isDeptOfficer, isTechnician, isCouncillor, isAdmin } = useAuth();
    const router = useRouter();

    useEffect(() => {
        if (!isOfficer) router.push("/login");
    }, [isOfficer, router]);

    if (!user) return null;

    const getHeaderColor = () => {
        if (isWardPGO || isAdmin) return "from-blue-800 to-indigo-900";
        if (isDeptOfficer) return "from-teal-700 to-cyan-800";
        if (isTechnician) return "from-slate-700 to-gray-800";
        if (isCouncillor) return "from-emerald-700 to-teal-800";
        return "from-blue-800 to-indigo-900";
    };

    const getTitle = () => {
        if (isWardPGO) return "Ward PGO — Supervisory Dashboard";
        if (isDeptOfficer) return `${DEPT_NAMES[user.dept_id ?? ""] ?? "Department"} — Operational Dashboard`;
        if (isTechnician) return "My Task Board";
        if (isCouncillor) return "Ward Dashboard";
        return `${user.role?.replace(/_/g, " ")} Dashboard`;
    };

    const navLinks = () => (
        <div className="flex gap-3 flex-wrap">
            {(isWardPGO || isDeptOfficer || isAdmin) && (
                <Link href="/officer/calendar"
                    className="text-sm bg-white/10 border border-white/20 text-white px-4 py-2 rounded-lg hover:bg-white/20 transition-colors">
                    📅 Calendar
                </Link>
            )}
            {isCouncillor && (
                <Link href="/councillor"
                    className="text-sm bg-white/10 border border-white/20 text-white px-4 py-2 rounded-lg hover:bg-white/20 transition-colors">
                    🏛️ Ward Insights
                </Link>
            )}
            {(isWardPGO || isAdmin) && (
                <Link href="/councillor"
                    className="text-sm bg-white/10 border border-white/20 text-white px-4 py-2 rounded-lg hover:bg-white/20 transition-colors">
                    📊 Analytics
                </Link>
            )}
            <Link href="/officer/reports"
                className="text-sm bg-white/10 border border-white/20 text-white px-4 py-2 rounded-lg hover:bg-white/20 transition-colors">
                📄 Reports
            </Link>
            <Link href="/map"
                className="text-sm bg-white/10 border border-white/20 text-white px-4 py-2 rounded-lg hover:bg-white/20 transition-colors">
                🗺️ Map
            </Link>
        </div>
    );

    return (
        <div className="min-h-screen bg-slate-50">
            {/* Header */}
            <div className={`bg-gradient-to-r ${getHeaderColor()} text-white px-6 py-6`}>
                <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
                    <div>
                        <p className="text-blue-300 text-sm">
                            {user.role?.replace(/_/g, " ")}
                            {user.ward_id && ` — Ward ${user.ward_id}`}
                            {user.dept_id && ` · ${DEPT_NAMES[user.dept_id] ?? user.dept_id}`}
                        </p>
                        <h1 className="text-2xl font-bold mt-0.5">Welcome, {user.name} 👋</h1>
                        <p className="text-blue-300/80 text-xs mt-0.5">{getTitle()}</p>
                    </div>
                    {navLinks()}
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
                {(isWardPGO || isAdmin) && <PGODashboard user={user} />}
                {isDeptOfficer && <DeptOfficerDashboard user={user} />}
                {isTechnician && <TechnicianDashboard />}
                {isCouncillor && (
                    <div className="text-center py-10">
                        <p className="text-gray-500 mb-4">As a Councillor, use the dedicated insights dashboard.</p>
                        <Link href="/councillor" className="inline-block bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-6 py-3 rounded-xl transition-colors">
                            Go to Ward Insights →
                        </Link>
                    </div>
                )}
            </div>
        </div>
    );
}
