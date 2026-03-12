"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { officerApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { formatRelative, parseUtc } from "@/lib/formatters";
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

interface FieldStaff {
    id: string;
    name: string;
    email: string;
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

// Valid statuses after removing deprecated ones
const STATUS_FILTERS = ["ALL", "OPEN", "ASSIGNED", "SCHEDULED", "IN_PROGRESS", "CLOSED"];

// ─── Ticket List Sub-component ────────────────────────────────────────────────

function TicketList({ tickets, showAssign, onStatusUpdate, onOpenAssignModal }: {
    tickets: Ticket[];
    showAssign?: boolean;
    onStatusUpdate?: (id: string, status: string) => void;
    onOpenAssignModal?: (ticket: Ticket) => void;
}) {
    const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({ CRITICAL: true });
    const [statusFilter, setStatusFilter] = useState("ALL");

    const filtered = statusFilter === "ALL"
        ? tickets
        : tickets.filter(t => t.status === statusFilter);

    const grouped = PRIORITY_ORDER.reduce<Record<string, Ticket[]>>((acc, p) => {
        acc[p] = filtered.filter(t => t.priority_label === p);
        return acc;
    }, {});

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
                {STATUS_FILTERS.map(s => (
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
                                                const canAssign = showAssign && ["OPEN", "ASSIGNED", "SCHEDULED"].includes(ticket.status) && onOpenAssignModal;
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
                                                            {canAssign && (
                                                                <button onClick={() => onOpenAssignModal(ticket)} className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 rounded px-2.5 py-1.5 font-medium transition-colors hover:bg-emerald-100">
                                                                    {ticket.status === "SCHEDULED" ? "Assign Technician" : "Schedule & Assign"}
                                                                </button>
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

            {/* Full ticket list — no assign actions for supervisor */}
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

    // Modal state: step 1 = set deadline, step 2 = assign technician
    const [modalStep, setModalStep] = useState<1 | 2>(1);
    const [completionDate, setCompletionDate] = useState("");
    const [settingDeadline, setSettingDeadline] = useState(false);

    // Step 2: technician selection
    const [fieldStaff, setFieldStaff] = useState<FieldStaff[]>([]);
    const [loadingStaff, setLoadingStaff] = useState(false);
    const [selectedTechId, setSelectedTechId] = useState("");
    const [assigningTech, setAssigningTech] = useState(false);

    // AI Smart Schedule — fills the date picker inline
    const [smartSchedule, setSmartSchedule] = useState<any>(null);
    const [gettingSmartSchedule, setGettingSmartSchedule] = useState(false);

    const refreshTickets = useCallback(() => {
        officerApi.getTickets(100).then(res => {
            const deptTickets = user.dept_id ? res.data.filter((t: Ticket) => t.dept_id === user.dept_id) : res.data;
            setTickets(deptTickets);
        });
    }, [user.dept_id]);

    useEffect(() => {
        officerApi.getTickets(100)
            .then(res => {
                const deptTickets = user.dept_id ? res.data.filter((t: Ticket) => t.dept_id === user.dept_id) : res.data;
                setTickets(deptTickets);
            })
            .catch(() => toast.error("Failed to load tickets"))
            .finally(() => setLoading(false));
    }, [user.dept_id]);

    const handleStatusUpdate = (id: string, status: string) => {
        setTickets(prev => prev.map(t => t.id === id ? { ...t, status } : t));
    };

    const handleOpenAssign = (ticket: Ticket) => {
        setAssignModalTicket(ticket);
        setSmartSchedule(null);
        setCompletionDate("");
        setSelectedTechId("");
        // If already SCHEDULED (deadline was set), jump to step 2 directly
        if (ticket.status === "SCHEDULED") {
            setModalStep(2);
            loadFieldStaff();
        } else {
            setModalStep(1);
        }
    };

    const closeModal = () => {
        setAssignModalTicket(null);
        setSmartSchedule(null);
        setCompletionDate("");
        setModalStep(1);
    };

    // Step 1: Set completion deadline → auto SCHEDULED
    const handleSetDeadline = async () => {
        if (!assignModalTicket || !completionDate) return;
        setSettingDeadline(true);
        try {
            await officerApi.setCompletionDeadline(assignModalTicket.id, completionDate, false);
            toast.success("Completion date set — ticket is now SCHEDULED");
            handleStatusUpdate(assignModalTicket.id, "SCHEDULED");
            setAssignModalTicket(prev => prev ? { ...prev, status: "SCHEDULED" } : null);
            setModalStep(2);
            loadFieldStaff();
        } catch (err: any) {
            const msg = err?.response?.data?.detail?.message || err?.response?.data?.detail || "Failed to set deadline";
            toast.error(msg);
        } finally {
            setSettingDeadline(false);
        }
    };

    const loadFieldStaff = async () => {
        setLoadingStaff(true);
        try {
            const res = await officerApi.getFieldStaff();
            setFieldStaff(res.data);
        } catch {
            toast.error("Could not load field staff");
        } finally {
            setLoadingStaff(false);
        }
    };

    // Step 2: Assign technician → auto IN_PROGRESS
    const handleAssignTechnician = async () => {
        if (!assignModalTicket || !selectedTechId || !completionDate) return;
        setAssigningTech(true);
        try {
            await officerApi.assignFieldStaff(assignModalTicket.id, selectedTechId, completionDate);
            toast.success("Technician assigned — ticket is now IN PROGRESS");
            handleStatusUpdate(assignModalTicket.id, "IN_PROGRESS");
            closeModal();
            refreshTickets();
        } catch (error: any) {
            toast.error(error.response?.data?.detail || "Failed to assign technician");
        } finally {
            setAssigningTech(false);
        }
    };

    // AI Smart Schedule — fetches a suggestion and fills the date picker inline
    const handleGetSmartSchedule = async () => {
        if (!assignModalTicket) return;
        setGettingSmartSchedule(true);
        try {
            const res = await officerApi.getSmartSchedule(assignModalTicket.id);
            setSmartSchedule(res.data);
            // Auto-fill the date picker with the AI-suggested date (safely parsing UTC)
            const utcDate = parseUtc(res.data.suggested_date);
            const suggestedDateStr = utcDate.toISOString().split("T")[0];
            setCompletionDate(suggestedDateStr);
            toast.success("AI suggested a date — you can edit it if needed.");
        } catch (error: any) {
            toast.error(error.response?.data?.detail || "Failed to get smart schedule");
        } finally {
            setGettingSmartSchedule(false);
        }
    };

    const stats = {
        total: tickets.length,
        scheduled: tickets.filter(t => t.status === "SCHEDULED").length,
        inProgress: tickets.filter(t => t.status === "IN_PROGRESS").length,
        critical: tickets.filter(t => t.priority_label === "CRITICAL").length,
    };

    if (loading) return <div className="flex justify-center py-20"><div className="w-10 h-10 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" /></div>;

    // Today's min date for the date picker
    const todayStr = new Date().toISOString().split("T")[0];

    return (
        <div className="space-y-8">

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <StatCard label="My Tickets" value={stats.total} icon="📋" color="blue" />
                <StatCard label="Scheduled" value={stats.scheduled} icon="📅" color="purple" />
                <StatCard label="In Progress" value={stats.inProgress} icon="⚡" color="orange" />
                <StatCard label="Critical" value={stats.critical} icon="🚨" color="red" />
            </div>

            <TicketList tickets={tickets} showAssign onStatusUpdate={handleStatusUpdate} onOpenAssignModal={handleOpenAssign} />

            {/* ── Schedule & Assign Modal ── */}
            <AnimatePresence>
                {assignModalTicket && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
                        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="bg-white rounded-2xl w-full max-w-lg shadow-xl overflow-hidden">
                            {/* Header */}
                            <div className="bg-teal-700 text-white p-5 flex justify-between items-start">
                                <div>
                                    <h3 className="font-bold text-lg">📋 Schedule & Assign Ticket</h3>
                                    <p className="text-teal-200 text-xs font-mono mt-0.5">{assignModalTicket.ticket_code} — {assignModalTicket.priority_label}</p>
                                    {/* Step progress */}
                                    <div className="flex items-center gap-2 mt-3">
                                        {[
                                            { n: 1, label: "Set Date" },
                                            { n: 2, label: "Assign Technician" },
                                        ].map(s => (
                                            <div key={s.n} className="flex items-center gap-1.5">
                                                <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${modalStep >= s.n ? "bg-white text-teal-800" : "bg-teal-600 text-teal-300"}`}>{s.n}</span>
                                                <span className={`text-xs font-medium ${modalStep >= s.n ? "text-white" : "text-teal-400"}`}>{s.label}</span>
                                                {s.n < 2 && <span className="text-teal-500 text-xs mx-1">→</span>}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                                <button onClick={closeModal} className="p-1 hover:bg-teal-600 rounded-full transition-colors">
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>
                                </button>
                            </div>

                            <div className="p-5">
                                {/* ── Step 1: Set Completion Date (unified view) ── */}
                                {modalStep === 1 && (
                                    <div className="space-y-4">
                                        <div>
                                            <p className="text-sm font-semibold text-gray-800 mb-1">Set Completion Deadline</p>
                                            <p className="text-xs text-gray-500 mb-3">Pick a date manually or let AI suggest one. The ticket will move to <strong>SCHEDULED</strong>.</p>

                                            {/* Date input + AI button side by side */}
                                            <label className="block text-xs font-medium text-gray-600 mb-1.5">Completion Date *</label>
                                            <div className="flex gap-2">
                                                <input
                                                    type="date"
                                                    min={todayStr}
                                                    value={completionDate}
                                                    onChange={e => { setCompletionDate(e.target.value); setSmartSchedule(null); }}
                                                    className={`flex-1 border rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 transition-colors ${
                                                        smartSchedule ? "border-purple-300 bg-purple-50" : "border-gray-200"
                                                    }`}
                                                />
                                                <button
                                                    onClick={handleGetSmartSchedule}
                                                    disabled={gettingSmartSchedule}
                                                    title="Let AI suggest the best date"
                                                    className="shrink-0 px-3 py-2 bg-gradient-to-br from-purple-600 to-indigo-700 text-white rounded-xl text-sm font-semibold hover:opacity-90 disabled:opacity-60 transition-all flex items-center gap-1.5"
                                                >
                                                    {gettingSmartSchedule
                                                        ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                                        : <span>✨</span>}
                                                    <span className="hidden sm:inline">{gettingSmartSchedule ? "Analyzing…" : "AI Suggest"}</span>
                                                </button>
                                            </div>

                                            {/* SLA warning */}
                                            {assignModalTicket.sla_deadline && (
                                                <p className="text-xs text-amber-600 mt-1.5">⚠️ SLA deadline: {parseUtc(assignModalTicket.sla_deadline).toLocaleDateString("en-IN", { dateStyle: "medium" })}</p>
                                            )}
                                        </div>

                                        {/* AI suggestion banner — shown inline when AI fills the date */}
                                        {smartSchedule && (
                                            <div className="bg-purple-50 border border-purple-200 rounded-xl p-3 space-y-1.5">
                                                <p className="text-xs font-bold text-purple-700 uppercase tracking-wide flex items-center gap-1.5">✨ AI Recommendation</p>
                                                <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                                                    <span className="text-gray-600">Technician: <span className="font-semibold text-gray-800">{smartSchedule.technician_name}</span></span>
                                                    <span className="text-gray-600">Date: <span className="font-semibold text-purple-800">{parseUtc(smartSchedule.suggested_date).toLocaleDateString("en-IN", { dateStyle: "long" })}</span></span>
                                                </div>
                                                <p className="text-[10px] text-purple-500">Date auto-filled above — edit freely or confirm as-is.</p>
                                                {smartSchedule.postponed_tickets?.length > 0 && (
                                                    <div className="bg-orange-50 border border-orange-200 rounded-lg p-2 mt-1">
                                                        <p className="text-xs font-bold text-orange-700 mb-1">⚠️ AI will also reschedule:</p>
                                                        <div className="space-y-0.5">
                                                            {smartSchedule.postponed_tickets.map((pt: any) => (
                                                                <p key={pt.ticket_id} className="text-xs text-orange-700 font-mono">
                                                                    {pt.ticket_code} → {parseUtc(pt.new_date).toLocaleDateString("en-IN")}
                                                                </p>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        <button
                                            onClick={handleSetDeadline}
                                            disabled={!completionDate || settingDeadline}
                                            className="w-full bg-teal-600 hover:bg-teal-700 text-white rounded-xl py-3 font-semibold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                                        >
                                            {settingDeadline ? <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Setting…</> : "Confirm Date → Next Step"}
                                        </button>
                                    </div>
                                )}

                                {/* ── Step 2: Pick Technician ── */}
                                {modalStep === 2 && (
                                    <div className="space-y-4">
                                        <div>
                                            <p className="text-sm font-semibold text-gray-800 mb-1">Assign Field Technician</p>
                                            <p className="text-xs text-gray-500 mb-4">Select a technician from your department. Once assigned, ticket status becomes <strong>IN PROGRESS</strong>.</p>
                                        </div>

                                        {loadingStaff ? (
                                            <div className="flex justify-center py-8"><div className="w-8 h-8 border-2 border-teal-200 border-t-teal-600 rounded-full animate-spin" /></div>
                                        ) : fieldStaff.length === 0 ? (
                                            <div className="text-center py-6 bg-amber-50 rounded-xl border border-amber-200">
                                                <p className="text-sm font-semibold text-amber-800 mb-1">No Field Staff Found</p>
                                                <p className="text-xs text-amber-600">No technicians are seeded for your ward/dept yet.</p>
                                            </div>
                                        ) : (
                                            <div className="space-y-2 max-h-60 overflow-y-auto">
                                                {fieldStaff.map(staff => (
                                                    <button
                                                        key={staff.id}
                                                        onClick={() => setSelectedTechId(staff.id)}
                                                        className={`w-full flex items-center gap-3 p-3 rounded-xl border text-left transition-all ${selectedTechId === staff.id ? "border-teal-500 bg-teal-50 shadow-sm" : "border-gray-200 hover:border-teal-300 hover:bg-gray-50"}`}
                                                    >
                                                        <div className="w-9 h-9 rounded-full bg-teal-100 text-teal-700 flex items-center justify-center font-bold text-sm shrink-0">
                                                            {staff.name.charAt(0).toUpperCase()}
                                                        </div>
                                                        <div>
                                                            <p className="text-sm font-semibold text-gray-800">{staff.name}</p>
                                                            <p className="text-xs text-gray-400">{staff.email}</p>
                                                        </div>
                                                        {selectedTechId === staff.id && <span className="ml-auto text-teal-600 text-lg">✓</span>}
                                                    </button>
                                                ))}
                                            </div>
                                        )}

                                        <div className="flex gap-3 pt-2 border-t border-gray-100">
                                            <button onClick={() => { setModalStep(1); setSelectedTechId(""); }} className="flex-1 bg-gray-100 text-gray-700 py-3 rounded-xl font-semibold hover:bg-gray-200 transition-colors">← Back</button>
                                            <button
                                                onClick={handleAssignTechnician}
                                                disabled={!selectedTechId || assigningTech || !completionDate}
                                                className="flex-1 bg-teal-600 text-white py-3 rounded-xl font-semibold hover:bg-teal-700 disabled:opacity-50 flex items-center justify-center gap-2 transition-colors"
                                            >
                                                {assigningTech ? <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Assigning…</> : "Assign → Mark In Progress"}
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
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
