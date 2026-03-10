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

function TicketList({ tickets, showAssign, onStatusUpdate, onOpenAssignModal }: {
    tickets: Ticket[];
    showAssign?: boolean;
    onStatusUpdate?: (id: string, status: string) => void;
    onOpenAssignModal?: (ticket: Ticket) => void;
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
                                                            {showAssign && ticket.status === "OPEN" && onOpenAssignModal && (
                                                                <button onClick={() => onOpenAssignModal(ticket)} className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 rounded px-2.5 py-1.5 font-medium transition-colors hover:bg-emerald-100">Assign &amp; Schedule</button>
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
    const [assignModalTicket, setAssignModalTicket] = useState<Ticket | null>(null);
    const [smartSchedule, setSmartSchedule] = useState<any>(null);
    const [gettingSmartSchedule, setGettingSmartSchedule] = useState(false);
    const [updating, setUpdating] = useState(false);

    useEffect(() => {
        officerApi.getTickets(100)
            .then(res => {
                // For safety, frontend filter as well, though backend already does it
                const deptTickets = user.dept_id ? res.data.filter((t: Ticket) => t.dept_id === user.dept_id) : res.data;
                setTickets(deptTickets);
            })
            .catch(() => toast.error("Failed to load tickets"))
            .finally(() => setLoading(false));
    }, [user.dept_id]);

    const handleStatusUpdate = (id: string, status: string) => {
        setTickets(prev => prev.map(t => t.id === id ? { ...t, status } : t));
    };

    const handleGetSmartSchedule = async (ticket: Ticket) => {
        setGettingSmartSchedule(true);
        try {
            const res = await officerApi.getSmartSchedule(ticket.id);
            setSmartSchedule(res.data);
            toast.success("AI generated a schedule suggestion.");
        } catch (error: any) {
            toast.error(error.response?.data?.detail || "Failed to get smart schedule");
        } finally {
            setGettingSmartSchedule(false);
        }
    };

    const handleApplySmartSchedule = async () => {
        if (!assignModalTicket || !smartSchedule) return;
        setUpdating(true);
        try {
            const payload = {
                suggested_date: smartSchedule.suggested_date,
                suggested_technician_id: smartSchedule.suggested_technician_id,
                postponed_tickets: smartSchedule.postponed_tickets
            };
            await officerApi.applySmartSchedule(assignModalTicket.id, payload);
            toast.success("Assignment applied successfully!");
            setSmartSchedule(null);
            setAssignModalTicket(null);
            // Refresh tickets
            officerApi.getTickets(100).then(res => {
                const deptTickets = user.dept_id ? res.data.filter((t: Ticket) => t.dept_id === user.dept_id) : res.data;
                setTickets(deptTickets);
            });
        } catch {
            toast.error("Failed to apply schedule");
        } finally {
            setUpdating(false);
        }
    };

    const handleOpenAssign = (ticket: Ticket) => {
        setAssignModalTicket(ticket);
        setSmartSchedule(null);
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
            <TicketList tickets={tickets} showAssign onStatusUpdate={handleStatusUpdate} onOpenAssignModal={handleOpenAssign} />

            {/* Smart Assign Modal */}
            {assignModalTicket && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
                    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="bg-white rounded-2xl w-full max-w-lg shadow-xl overflow-hidden">
                        <div className="flex justify-between items-center p-5 border-b border-gray-100 bg-emerald-50 text-emerald-900">
                            <div>
                                <h3 className="font-bold text-lg flex items-center gap-2">👷 Assign Field Staff</h3>
                                <p className="text-xs text-emerald-700 font-mono mt-1">{assignModalTicket.ticket_code} — {assignModalTicket.priority_label} PRIORITY</p>
                            </div>
                            <button onClick={() => setAssignModalTicket(null)} className="p-1 hover:bg-emerald-200/50 rounded-full transition-colors">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>
                            </button>
                        </div>
                        <div className="p-5">
                            {!smartSchedule ? (
                                <div className="text-center py-6">
                                    <button
                                        onClick={() => handleGetSmartSchedule(assignModalTicket)}
                                        disabled={gettingSmartSchedule}
                                        className="w-full bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white rounded-xl py-3 font-semibold transition-colors disabled:opacity-50 shadow-sm flex items-center justify-center gap-2 text-lg"
                                    >
                                        ✨ {gettingSmartSchedule ? "Analyzing Staff & SLAs..." : "Generate AI Smart Schedule"}
                                    </button>
                                    <p className="text-xs text-gray-500 mt-4">The AI will optimally schedule this issue based on technician availability, existing SLAs, and priority criticalness.</p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    <p className="text-sm font-semibold text-teal-800 uppercase tracking-wide">AI Recommendation</p>
                                    <div className="space-y-2">
                                        <p className="text-sm text-gray-800 border-b border-gray-100 pb-2"><span className="text-gray-500 w-24 inline-block">Technician:</span> <span className="font-semibold text-lg">{smartSchedule.technician_name}</span></p>
                                        <p className="text-sm text-gray-800 border-b border-gray-100 pb-2"><span className="text-gray-500 w-24 inline-block">Date:</span> <span className="font-semibold text-lg">{new Date(smartSchedule.suggested_date).toLocaleDateString("en-IN", { dateStyle: "long" })}</span></p>
                                    </div>
                                    {smartSchedule.postponed_tickets && smartSchedule.postponed_tickets.length > 0 && (
                                        <div className="bg-orange-50 p-4 rounded-xl border border-orange-200 mt-4">
                                            <p className="text-sm font-bold text-orange-800 flex items-center gap-2 mb-2">⚠️ Preemption Warning</p>
                                            <p className="text-xs text-orange-700 mb-3 leading-relaxed">To accommodate an SLA-safe slot for this issue, the AI will postpone the following lower-priority tickets:</p>
                                            <div className="space-y-2 max-h-32 overflow-y-auto">
                                                {smartSchedule.postponed_tickets.map((pt: any) => (
                                                    <div key={pt.ticket_id} className="bg-white/80 p-2 rounded border border-orange-100 text-xs">
                                                        <span className="font-mono font-bold text-gray-700">{pt.ticket_code}</span> moved to <span className="font-semibold text-orange-800">{new Date(pt.new_date).toLocaleDateString("en-IN")}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    <div className="flex gap-3 pt-4 border-t border-gray-100 mt-4">
                                        <button onClick={() => setSmartSchedule(null)} className="flex-1 bg-gray-100 text-gray-700 py-3 rounded-xl font-semibold hover:bg-gray-200 transition-colors">Go Back</button>
                                        <button onClick={handleApplySmartSchedule} disabled={updating} className="flex-1 bg-teal-600 text-white py-3 rounded-xl font-semibold hover:bg-teal-700 transition-colors flex items-center justify-center gap-2">
                                            {updating ? "Applying..." : "Confirm Assignment"}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </motion.div>
                </div>
            )}
        </div>
    );
}



// ─── Main Dashboard Controller ────────────────────────────────────────────────

interface OfficerDashboardProps {
    userOverride?: any;
    forcedRole?: string;
}

export default function OfficerDashboard({ userOverride, forcedRole }: OfficerDashboardProps = {}) {
    const auth = useAuth();
    const user = userOverride || auth.user;
    const role = forcedRole || user?.role;

    const isOfficer = !!user && role !== "PUBLIC_USER";
    const isSupervisor = role === "SUPERVISOR";
    const isJuniorEngineer = role === "JUNIOR_ENGINEER";
    const isFieldStaff = role === "FIELD_STAFF";
    const isCouncillor = role === "COUNCILLOR";
    const isAdmin = role === "SUPER_ADMIN";

    const router = useRouter();

    useEffect(() => {
        if (!isOfficer) router.push("/login");
    }, [isOfficer, router]);

    if (!user) return null;

    const getHeaderColor = () => {
        if (isSupervisor) return "from-blue-800 to-indigo-900";
        if (isCouncillor) return "from-emerald-700 to-teal-800";
        if (isJuniorEngineer) return "from-teal-700 to-cyan-800";
        return "from-slate-700 to-gray-800";
    };

    const getTitle = () => {
        if (isSupervisor) return "Ward Operations Dashboard";
        if (isJuniorEngineer) {
            const deptName = user.dept_id ? (DEPT_NAMES[user.dept_id] || user.dept_id) : "Department";
            return `${deptName} Engineering Dashboard`;
        }
        if (isCouncillor) return "Ward Councillor Dashboard";
        return "Restricted Access";
    };

    const navLinks = () => (
        <div className="flex gap-3 flex-wrap">
            {(isSupervisor || isJuniorEngineer) && (
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
            {isSupervisor && (
                <Link href="/councillor"
                    className="text-sm bg-white/10 border border-white/20 text-white px-4 py-2 rounded-lg hover:bg-white/20 transition-colors">
                    📊 Analytics
                </Link>
            )}
            {(isSupervisor || isAdmin) && (
                <div className="flex gap-2 ml-2">
                    <Link href="/officer/sanitation-dashboard"
                        className="text-xs bg-emerald-500/20 text-emerald-100 border border-emerald-500/30 px-3 py-1.5 rounded-lg hover:bg-emerald-500/40 transition-colors">
                        Sanitation
                    </Link>
                    <Link href="/officer/water-dashboard"
                        className="text-xs bg-blue-500/20 text-blue-100 border border-blue-500/30 px-3 py-1.5 rounded-lg hover:bg-blue-500/40 transition-colors">
                        Water
                    </Link>
                    <Link href="/officer/electrical-dashboard"
                        className="text-xs bg-yellow-500/20 text-yellow-100 border border-yellow-500/30 px-3 py-1.5 rounded-lg hover:bg-yellow-500/40 transition-colors">
                        Electricity
                    </Link>
                </div>
            )}
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
                {isSupervisor && <SupervisorDashboard user={user} />}
                {isJuniorEngineer && <JuniorEngineerDashboard user={user} />}
                {(isAdmin || isFieldStaff || (!isSupervisor && !isJuniorEngineer && !isCouncillor)) && (
                    <div className="text-center py-20 bg-white rounded-3xl border border-gray-100 shadow-sm">
                        <p className="text-5xl mb-4">🔐</p>
                        <h2 className="text-xl font-bold text-gray-800">Restricted Access</h2>
                        <p className="text-gray-500 mt-2">Your account role ({role}) does not have an active operations dashboard.</p>
                        <p className="text-xs text-gray-400 mt-4">Please contact the system administrator if you believe this is an error.</p>
                    </div>
                )}
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
