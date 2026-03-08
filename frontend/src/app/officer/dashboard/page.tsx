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
import dynamic from "next/dynamic";

const IssueMap = dynamic(() => import("@/features/map/IssueMap"), { ssr: false });

interface Ticket {
    id: string;
    ticket_code: string;
    status: string;
    description: string;
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
    after_photo_url?: string;
    lat?: number;
    lng?: number;
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
                            <div className="bg-white overflow-x-auto">
                                {group.length === 0 ? (
                                    <p className="text-sm text-gray-400 px-5 py-4 italic">No {priority.toLowerCase()} tickets</p>
                                ) : (
                                    <table className="min-w-full divide-y divide-gray-200 text-sm">
                                        <thead className="bg-gray-50 text-gray-500 font-medium text-xs">
                                            <tr>
                                                <th className="px-4 py-3 text-left">Ticket ID</th>
                                                <th className="px-4 py-3 text-left">Category</th>
                                                <th className="px-4 py-3 text-left">Location</th>
                                                <th className="px-4 py-3 text-left">Assignee</th>
                                                <th className="px-4 py-3 text-left">Status</th>
                                                <th className="px-4 py-3 text-left">SLA</th>
                                                <th className="px-4 py-3 text-right">Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-100 bg-white">
                                            {group.map((ticket, i) => {
                                                const sla = getSlaCountdown(ticket.sla_deadline);
                                                return (
                                                    <motion.tr key={ticket.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.03 }} className="hover:bg-gray-50 transition-colors">
                                                        <td className="px-4 py-3 font-mono font-bold text-blue-600">{ticket.ticket_code}</td>
                                                        <td className="px-4 py-3 font-medium text-gray-800">{ticket.issue_category || "General Issue"}</td>
                                                        <td className="px-4 py-3 text-gray-500">{ticket.ward_id ? `Ward ${ticket.ward_id}` : "Unspecified"}</td>
                                                        <td className="px-4 py-3 text-gray-500">
                                                            {ticket.technician_id ? `Staff (${ticket.technician_id.slice(-4)})` : ticket.assigned_officer_id ? `JE (${ticket.assigned_officer_id.slice(-4)})` : <span className="text-gray-400 italic">Unassigned</span>}
                                                        </td>
                                                        <td className="px-4 py-3"><StatusBadge status={ticket.status} size="sm" /></td>
                                                        <td className={`px-4 py-3 ${sla ? sla.cls : "text-gray-400"}`}>{sla ? sla.label : "N/A"}</td>
                                                        <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                                                            {showAssign && ticket.status === "IN_PROGRESS" && (
                                                                <button disabled={updatingId === ticket.id} onClick={() => handleQuickStatus(ticket.id, "PENDING_VERIFICATION")} className="text-xs bg-cyan-50 text-cyan-700 border border-cyan-200 rounded px-2.5 py-1.5 font-medium transition-colors disabled:opacity-50">Mark Done</button>
                                                            )}
                                                            {showAssign && ticket.status === "OPEN" && (
                                                                <button disabled={updatingId === ticket.id} onClick={() => handleQuickStatus(ticket.id, "IN_PROGRESS")} className="text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded px-2.5 py-1.5 font-medium transition-colors disabled:opacity-50">Start</button>
                                                            )}
                                                            <Link href={`/officer/tickets/${ticket.id}`} className="text-xs font-medium text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 rounded px-3 py-1.5 transition-colors">View →</Link>
                                                        </td>
                                                    </motion.tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                )}
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}

// ─── Supervisor Operational View ─────────────────────────────────────────────────────

function SupervisorDashboard({ user }: { user: { name: string; ward_id?: number; role: string } }) {
    const router = useRouter();
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
            {/* Map Section */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden h-[450px]">
                <IssueMap
                    issues={tickets as any}
                    onIssueClick={(issue) => router.push(`/officer/tickets/${issue.id}`)}
                />
            </div>

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

// ─── Junior Engineer Operational View ───────────────────────────────────────────

function JuniorEngineerDashboard({ user }: { user: { name: string; dept_id?: string; ward_id?: number; role: string } }) {
    const router = useRouter();
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        officerApi.getMyTickets()
            .then(res => setTickets(res.data))
            .catch(() => toast.error("Failed to load tickets"))
            .finally(() => setLoading(false));
    }, []);

    const handleStatusUpdate = (id: string, status: string) => {
        setTickets(prev => prev.map(t => t.id === id ? { ...t, status } : t));
    };

    const stats = {
        total: tickets.length,
        open: tickets.filter(t => ["ASSIGNED", "SCHEDULED", "IN_PROGRESS"].includes(t.status)).length,
        critical: tickets.filter(t => t.priority_label === "CRITICAL").length,
        awaiting: tickets.filter(t => t.status === "AWAITING_MATERIAL").length,
    };

    if (loading) return <div className="flex justify-center py-20"><div className="w-10 h-10 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" /></div>;

    return (
        <div className="space-y-8">
            {/* Map Section */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden h-[450px]">
                <IssueMap
                    issues={tickets as any}
                    onIssueClick={(issue) => router.push(`/officer/tickets/${issue.id}`)}
                />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <StatCard label="My Tickets" value={stats.total} icon="📋" color="blue" />
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
    const router = useRouter();
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);
    const [proofUploads, setProofUploads] = useState<Record<string, string>>({});
    const [updatingParams, setUpdatingParams] = useState<Record<string, boolean>>({});

    useEffect(() => {
        officerApi.getMyTickets()
            .then(res => setTickets(res.data))
            .catch(() => toast.error("Failed to load your tasks"))
            .finally(() => setLoading(false));
    }, []);

    const handleStatusUpdate = (id: string, status: string, additional?: Partial<Ticket>) => {
        setTickets(prev => prev.map(t => t.id === id ? { ...t, status, ...additional } : t));
    };

    const stats = {
        total: tickets.length,
        inProgress: tickets.filter(t => t.status === "IN_PROGRESS").length,
        pending: tickets.filter(t => ["OPEN", "ASSIGNED", "SCHEDULED"].includes(t.status)).length,
        done: tickets.filter(t => ["PENDING_VERIFICATION", "CLOSED"].includes(t.status)).length,
    };

    const STATUS_FLOW: Record<string, { next: string; label: string; cls: string }> = {
        ASSIGNED: { next: "IN_PROGRESS", label: "▶ Start Work", cls: "bg-blue-600 hover:bg-blue-700 text-white" },
        SCHEDULED: { next: "IN_PROGRESS", label: "▶ Start Work", cls: "bg-blue-600 hover:bg-blue-700 text-white" },
        IN_PROGRESS: { next: "AWAITING_MATERIAL", label: "📦 Need Material", cls: "bg-yellow-500 hover:bg-yellow-600 text-white" },
        AWAITING_MATERIAL: { next: "IN_PROGRESS", label: "✅ Got Material", cls: "bg-emerald-500 hover:bg-emerald-600 text-white" },
    };

    if (loading) return <div className="flex justify-center py-20"><div className="w-10 h-10 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" /></div>;

    return (
        <div className="space-y-6">
            {/* Map Section for Mobile/Field view */}
            {tickets.length > 0 && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden h-[300px]">
                    <IssueMap
                        issues={tickets.filter(t => !["PENDING_VERIFICATION", "CLOSED", "REJECTED"].includes(t.status)) as any}
                        onIssueClick={(issue) => router.push(`/officer/tickets/${issue.id}`)}
                    />
                </div>
            )}

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <StatCard label="My Tasks" value={stats.total} icon="📋" color="blue" />
                <StatCard label="Pending" value={stats.pending} icon="⏳" color="orange" />
                <StatCard label="In Progress" value={stats.inProgress} icon="🔧" color="purple" />
                <StatCard label="Completed" value={stats.done} icon="✅" color="green" />
            </div>

            {tickets.length === 0 ? (
                <div className="text-center py-20 bg-white rounded-2xl border border-gray-100 text-gray-400">
                    <p className="text-5xl mb-3">🎉</p>
                    <p className="text-lg font-medium text-gray-800">No tasks assigned yet!</p>
                    <p className="text-sm mt-1">Check back later for new dispatches.</p>
                </div>
            ) : (
                <div className="space-y-4">
                    {tickets.map((ticket, i) => {
                        const nextAction = STATUS_FLOW[ticket.status];
                        const isCompleting = ticket.status === "IN_PROGRESS";
                        const proofUrl = proofUploads[ticket.id] || "";
                        const isUpdating = updatingParams[ticket.id] || false;

                        return (
                            <motion.div key={ticket.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
                                className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 w-full">
                                <div className="flex flex-col sm:flex-row gap-4">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 flex-wrap mb-2">
                                            <span className="font-mono font-bold text-blue-700">{ticket.ticket_code}</span>
                                            <StatusBadge status={ticket.status} size="sm" />
                                            <PriorityBadge label={ticket.priority_label} score={ticket.priority_score} size="sm" />
                                        </div>
                                        <p className="text-sm font-medium text-gray-900 mb-1">{ticket.issue_category ?? "General Issue"}</p>
                                        <div className="flex gap-x-3 gap-y-1 mt-2 text-xs text-gray-500 flex-wrap">
                                            <span className="flex items-center gap-1">📍 Ward {ticket.ward_id}</span>
                                            {ticket.scheduled_date && (
                                                <span className="flex items-center gap-1 text-purple-600 font-medium bg-purple-50 px-2 py-0.5 rounded-md">
                                                    📅 {new Date(ticket.scheduled_date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                                                </span>
                                            )}
                                        </div>
                                    </div>

                                    {/* Action Buttons Column */}
                                    {["PENDING_VERIFICATION", "CLOSED", "REJECTED"].includes(ticket.status) ? (
                                        <div className="sm:self-center">
                                            <Link href={`/officer/tickets/${ticket.id}`} className="block text-center text-sm font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-xl px-6 py-2 transition-colors">
                                                View Review →
                                            </Link>
                                        </div>
                                    ) : (
                                        <div className="flex flex-col gap-2 min-w-[200px] bg-gray-50 rounded-xl p-3">
                                            {nextAction && (
                                                <button
                                                    disabled={isUpdating}
                                                    onClick={async () => {
                                                        setUpdatingParams(p => ({ ...p, [ticket.id]: true }));
                                                        try {
                                                            await officerApi.updateStatus(ticket.id, nextAction.next);
                                                            handleStatusUpdate(ticket.id, nextAction.next);
                                                            toast.success(`Marked as ${nextAction.next.replace(/_/g, " ")}`);
                                                        } catch { toast.error("Update failed"); }
                                                        finally { setUpdatingParams(p => ({ ...p, [ticket.id]: false })); }
                                                    }}
                                                    className={`w-full text-xs font-semibold px-4 py-2.5 rounded-xl transition-colors disabled:opacity-50 ${nextAction.cls}`}>
                                                    {isUpdating ? "..." : nextAction.label}
                                                </button>
                                            )}

                                            {isCompleting && (
                                                <div className="mt-2 pt-2 border-t border-gray-200">
                                                    <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1 px-1">Proof of Work</p>
                                                    <input
                                                        type="url"
                                                        placeholder="Photo URL (required)"
                                                        value={proofUrl}
                                                        onChange={(e) => setProofUploads(p => ({ ...p, [ticket.id]: e.target.value }))}
                                                        className="w-full text-xs border border-gray-300 rounded-lg px-2 py-2 mb-2 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                                                    />
                                                    <button
                                                        disabled={isUpdating || !proofUrl.trim()}
                                                        onClick={async () => {
                                                            setUpdatingParams(p => ({ ...p, [ticket.id]: true }));
                                                            try {
                                                                await officerApi.uploadProof(ticket.id, proofUrl);
                                                                toast.success("Proof uploaded");
                                                                await officerApi.updateStatus(ticket.id, "PENDING_VERIFICATION");
                                                                handleStatusUpdate(ticket.id, "PENDING_VERIFICATION", { after_photo_url: proofUrl });
                                                                toast.success("Job marked complete!");
                                                            } catch { toast.error("Completion failed"); }
                                                            finally { setUpdatingParams(p => ({ ...p, [ticket.id]: false })); }
                                                        }}
                                                        className="w-full text-xs font-semibold px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white transition-colors disabled:opacity-50">
                                                        {isUpdating ? "Submitting..." : "✓ Submit & Complete"}
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    )}
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
    const { user, isOfficer, isSupervisor, isJuniorEngineer, isFieldStaff, isCouncillor, isAdmin } = useAuth();
    const router = useRouter();

    useEffect(() => {
        if (!isOfficer) router.push("/login");
    }, [isOfficer, router]);

    if (!user) return null;

    const getHeaderColor = () => {
        if (isSupervisor || isAdmin) return "from-blue-800 to-indigo-900";
        if (isCouncillor) return "from-emerald-700 to-teal-800";
        if (isJuniorEngineer) return "from-teal-700 to-cyan-800";
        if (isFieldStaff) return "from-slate-700 to-gray-800";
        return "from-blue-800 to-indigo-900";
    };

    const getTitle = () => {
        if (isSupervisor) return "Ward Supervisor Dashboard";
        if (isJuniorEngineer) return "Junior Engineer Dashboard";
        if (isFieldStaff) return "Field Staff Task Board";
        if (isCouncillor) return "Ward Councillor Dashboard";
        return `${user.role?.replace(/_/g, " ")} Dashboard`;
    };

    const navLinks = () => (
        <div className="flex gap-3 flex-wrap">
            {(isSupervisor || isJuniorEngineer || isAdmin) && (
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
            {(isSupervisor || isAdmin) && (
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
                🗺️ Map (Heatmap)
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
                {(isSupervisor || isAdmin) && <SupervisorDashboard user={user} />}
                {isJuniorEngineer && <JuniorEngineerDashboard user={user} />}
                {isFieldStaff && <TechnicianDashboard />}
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
