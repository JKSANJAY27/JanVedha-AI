"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { officerApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { formatRelative, parseUtc } from "@/lib/formatters";
import PriorityBadge from "@/components/PriorityBadge";
import StatusBadge from "@/components/StatusBadge";
import StatCard from "@/components/StatCard";
import Link from "next/link";
import { DEPT_NAMES, getWardLabel } from "@/lib/constants";
import ResourceHealthCard from "@/components/ResourceHealthCard";
import ResolveWithProofModal from "@/components/ResolveWithProofModal";

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

function TicketList({ tickets, showAssign, onStatusUpdate, onOpenAssignModal, onOpenResolveModal }: {
    tickets: Ticket[];
    showAssign?: boolean;
    onStatusUpdate?: (id: string, status: string) => void;
    onOpenAssignModal?: (ticket: Ticket) => void;
    onOpenResolveModal?: (ticket: Ticket) => void;
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
                                                        <td className="px-4 py-3 text-gray-500">{ticket.ward_id ? getWardLabel(ticket.ward_id) : "Unspecified"}</td>
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
                                                            {onOpenResolveModal && ticket.status === "IN_PROGRESS" && (
                                                                <button onClick={() => onOpenResolveModal(ticket)} className="text-xs bg-purple-50 text-purple-700 border border-purple-200 rounded px-2.5 py-1.5 font-medium transition-colors hover:bg-purple-100">
                                                                    Upload Proof & Resolve
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

// ─── Speedometer Gauge Component ─────────────────────────────────────────────

function SpeedometerGauge({
    value, label, icon, sublabel, status, onClick, active
}: {
    value: number; label: string; icon: string; sublabel: string;
    status: "good" | "warn" | "critical"; onClick: () => void; active: boolean;
}) {
    const R = 54;
    const cx = 70;
    const cy = 72;
    // Arc spans 210° total, from 210° to -30° (clockwise via left side)
    const startAngle = 210;
    const endAngle = -30;
    const totalDeg = 240;
    const safeValue = (typeof value === 'number' && !isNaN(value)) ? value : 0;
    const clampedVal = Math.max(0, Math.min(100, safeValue));

    function polarToCartesian(angle: number) {
        const rad = (angle * Math.PI) / 180;
        return {
            x: cx + R * Math.cos(rad),
            y: cy - R * Math.sin(rad),
        };
    }

    function buildArcPath(fromDeg: number, toDeg: number) {
        const s = polarToCartesian(fromDeg);
        const e = polarToCartesian(toDeg);
        const large = fromDeg - toDeg > 180 ? 1 : 0;
        return `M ${s.x} ${s.y} A ${R} ${R} 0 ${large} 1 ${e.x} ${e.y}`;
    }

    // Track arc (full 240°)
    const trackPath = buildArcPath(startAngle, endAngle);

    // Value arc: map value [0,100] to angle
    const valueDeg = startAngle - (clampedVal / 100) * totalDeg;
    const valuePath = clampedVal > 0 ? buildArcPath(startAngle, valueDeg) : "";

    // Needle
    const needleRad = (valueDeg * Math.PI) / 180;
    const needleTip = { x: cx + (R - 8) * Math.cos(needleRad), y: cy - (R - 8) * Math.sin(needleRad) };
    const needleBase = { x: cx + 8 * Math.cos(needleRad + Math.PI), y: cy - 8 * Math.sin(needleRad + Math.PI) };

    const colorMap = { good: "#22c55e", warn: "#f59e0b", critical: "#ef4444" };
    const glowMap = { good: "rgba(34,197,94,0.3)", warn: "rgba(245,158,11,0.3)", critical: "rgba(239,68,68,0.3)" };
    const bgMap = { good: "from-emerald-950 to-emerald-900", warn: "from-amber-950 to-amber-900", critical: "from-red-950 to-red-900" };
    const arcColor = colorMap[status];

    return (
        <button
            onClick={onClick}
            className={`relative group flex flex-col items-center p-5 rounded-3xl border-2 transition-all duration-300 w-full text-left
                bg-gradient-to-br ${bgMap[status]}
                ${active ? "border-white/40 shadow-2xl scale-[1.03]" : "border-white/10 hover:border-white/30 hover:scale-[1.02]"}
            `}
            style={active ? { boxShadow: `0 0 40px ${glowMap[status]}` } : {}}
        >
            {/* Active indicator */}
            {active && <div className="absolute top-3 right-3 w-2 h-2 rounded-full animate-pulse" style={{ background: arcColor }} />}

            {/* Gauge SVG */}
            <svg width="140" height="90" viewBox="0 0 140 90" className="overflow-visible">
                {/* Track */}
                <path d={trackPath} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="8" strokeLinecap="round" />

                {/* Zone ticks */}
                {[0, 40, 70, 100].map(v => {
                    const deg = startAngle - (v / 100) * totalDeg;
                    const inner = { x: cx + (R - 14) * Math.cos((deg * Math.PI) / 180), y: cy - (R - 14) * Math.sin((deg * Math.PI) / 180) };
                    const outer = { x: cx + (R - 8) * Math.cos((deg * Math.PI) / 180), y: cy - (R - 8) * Math.sin((deg * Math.PI) / 180) };
                    return <line key={v} x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y} stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" />;
                })}

                {/* Value arc */}
                {valuePath && (
                    <path d={valuePath} fill="none" stroke={arcColor} strokeWidth="8" strokeLinecap="round"
                        style={{ filter: `drop-shadow(0 0 6px ${arcColor})` }} />
                )}

                {/* Needle */}
                <line x1={needleBase.x} y1={needleBase.y} x2={needleTip.x} y2={needleTip.y}
                    stroke="white" strokeWidth="2" strokeLinecap="round"
                    style={{ filter: "drop-shadow(0 0 4px rgba(255,255,255,0.8))" }} />
                <circle cx={cx} cy={cy} r="5" fill="white" style={{ filter: "drop-shadow(0 0 4px rgba(255,255,255,0.6))" }} />

                {/* Value text */}
                <text x={cx} y={cy - 18} textAnchor="middle" fill="white" fontSize="18" fontWeight="bold" fontFamily="monospace">
                    {clampedVal === 0 && value === 0 ? "N/A" : `${Math.round(clampedVal)}%`}
                </text>
            </svg>

            {/* Label */}
            <div className="text-center mt-1">
                <p className="text-sm font-bold text-white flex items-center gap-1.5 justify-center">
                    <span>{icon}</span> {label}
                </p>
                <p className="text-[11px] mt-0.5 font-medium" style={{ color: arcColor }}>{sublabel}</p>
            </div>

            {/* Click hint */}
            <p className="text-[10px] text-white/30 mt-2 group-hover:text-white/60 transition-colors">
                {active ? "Click to close" : "Click to inspect"}
            </p>
        </button>
    );
}

// ─── Metric Detail Panel ──────────────────────────────────────────────────────

function MetricDetailPanel({
    metricId, summary, tickets, onClose
}: {
    metricId: string;
    summary: DashboardSummary;
    tickets: Ticket[];
    onClose: () => void;
}) {
    const router = useRouter();
    const [showTickets, setShowTickets] = useState(false);
    const [statusFilter, setStatusFilter] = useState("ALL");

    const now = new Date();
    const overdue = tickets.filter(t => t.sla_deadline && new Date(t.sla_deadline) < now && !["CLOSED", "REJECTED"].includes(t.status));
    const criticalTickets = tickets.filter(t => t.priority_label === "CRITICAL" && !["CLOSED", "RESOLVED"].includes(t.status));
    const openTickets = tickets.filter(t => t.status === "OPEN");
    const assignedTickets = tickets.filter(t => t.assigned_officer_id || t.technician_id);
    const closedTickets = tickets.filter(t => ["CLOSED", "RESOLVED"].includes(t.status));

    const METRIC_CONFIG: Record<string, {
        title: string; icon: string; color: string;
        rows: { label: string; value: string | number; highlight?: "good" | "warn" | "bad" }[];
        ticketFilter: Ticket[];
        insight: string;
    }> = {
        completion: {
            title: "Completion Rate", icon: "✅", color: "emerald",
            rows: [
                { label: "Total Tickets", value: summary.total },
                { label: "Resolved / Closed", value: summary.closed, highlight: summary.closed > 0 ? "good" : "warn" },
                { label: "Still Open", value: summary.open, highlight: summary.open > summary.closed ? "warn" : "good" },
                { label: "Completion Rate", value: `${summary.total > 0 ? Math.round((summary.closed / summary.total) * 100) : 0}%`, highlight: summary.total > 0 && summary.closed / summary.total >= 0.7 ? "good" : "bad" },
            ],
            ticketFilter: closedTickets,
            insight: summary.total > 0 && summary.closed / summary.total < 0.5
                ? "More than half the tickets are unresolved. Prioritise closing older open tickets."
                : "Completion rate is healthy. Keep monitoring the backlog.",
        },
        sla: {
            title: "SLA Compliance", icon: "⏱️", color: "blue",
            rows: [
                { label: "Total Active Tickets", value: summary.open },
                { label: "SLA Breached", value: overdue.length, highlight: overdue.length > 0 ? "bad" : "good" },
                { label: "Within SLA", value: summary.open - overdue.length, highlight: "good" },
                { label: "Compliance Rate", value: `${summary.open > 0 ? Math.round(((summary.open - overdue.length) / summary.open) * 100) : 100}%`, highlight: overdue.length === 0 ? "good" : overdue.length > 3 ? "bad" : "warn" },
            ],
            ticketFilter: overdue,
            insight: overdue.length === 0
                ? "All active tickets are within their SLA window."
                : `${overdue.length} ticket(s) have breached SLA. Immediate escalation required.`,
        },
        critical: {
            title: "Critical Load", icon: "🚨", color: "red",
            rows: [
                { label: "Total Tickets", value: summary.total },
                { label: "Critical Priority", value: summary.critical, highlight: summary.critical > 0 ? "bad" : "good" },
                { label: "High Priority", value: tickets.filter(t => t.priority_label === "HIGH").length, highlight: "warn" },
                { label: "Critical Ratio", value: `${summary.total > 0 ? Math.round((summary.critical / summary.total) * 100) : 0}%`, highlight: summary.critical === 0 ? "good" : summary.critical > 5 ? "bad" : "warn" },
            ],
            ticketFilter: criticalTickets,
            insight: summary.critical === 0
                ? "No critical issues — maintain regular patrolling to keep it this way."
                : `${summary.critical} critical issue(s) need urgent attention. Do not let these age.`,
        },
        assignment: {
            title: "Assignment Rate", icon: "👷", color: "violet",
            rows: [
                { label: "Open Tickets", value: summary.open },
                { label: "Assigned (JE / Technician)", value: assignedTickets.filter(t => !["CLOSED", "RESOLVED"].includes(t.status)).length, highlight: "good" },
                { label: "Unassigned / Waiting", value: openTickets.length, highlight: openTickets.length > 0 ? "warn" : "good" },
                { label: "Assignment Rate", value: `${summary.open > 0 ? Math.round((assignedTickets.filter(t => !["CLOSED", "RESOLVED"].includes(t.status)).length / summary.open) * 100) : 100}%`, highlight: openTickets.length === 0 ? "good" : "warn" },
            ],
            ticketFilter: openTickets,
            insight: openTickets.length === 0
                ? "All open tickets have been assigned to engineers or technicians."
                : `${openTickets.length} ticket(s) are still unassigned. Forward them to the appropriate junior engineer.`,
        },
        satisfaction: {
            title: "Citizen Satisfaction", icon: "⭐", color: "amber",
            rows: [
                { label: "Average Score", value: summary.avg_satisfaction !== null ? `${summary.avg_satisfaction} / 5` : "No ratings yet", highlight: summary.avg_satisfaction !== null ? (summary.avg_satisfaction >= 4 ? "good" : summary.avg_satisfaction >= 3 ? "warn" : "bad") : undefined },
                { label: "Closed Tickets", value: summary.closed },
                { label: "Rated Tickets", value: closedTickets.filter(t => t.after_photo_url).length },  // proxy
                { label: "Score Band", value: summary.avg_satisfaction !== null ? (summary.avg_satisfaction >= 4 ? "Excellent" : summary.avg_satisfaction >= 3 ? "Acceptable" : "Needs Improvement") : "No data" },
            ],
            ticketFilter: closedTickets,
            insight: summary.avg_satisfaction === null
                ? "No citizen ratings collected yet. Ensure resolved tickets prompt for feedback."
                : summary.avg_satisfaction < 3
                ? "Satisfaction is low. Review how resolved tickets were handled and follow up with disgruntled citizens."
                : "Citizen satisfaction is at an acceptable level.",
        },
    };

    const cfg = METRIC_CONFIG[metricId];
    if (!cfg) return null;

    const colorClasses: Record<string, { bg: string; border: string; badge: string; text: string; btn: string }> = {
        emerald: { bg: "bg-emerald-50", border: "border-emerald-200", badge: "bg-emerald-100 text-emerald-800", text: "text-emerald-700", btn: "bg-emerald-600 hover:bg-emerald-700" },
        blue: { bg: "bg-blue-50", border: "border-blue-200", badge: "bg-blue-100 text-blue-800", text: "text-blue-700", btn: "bg-blue-600 hover:bg-blue-700" },
        red: { bg: "bg-red-50", border: "border-red-200", badge: "bg-red-100 text-red-800", text: "text-red-700", btn: "bg-red-600 hover:bg-red-700" },
        violet: { bg: "bg-violet-50", border: "border-violet-200", badge: "bg-violet-100 text-violet-800", text: "text-violet-700", btn: "bg-violet-600 hover:bg-violet-700" },
        amber: { bg: "bg-amber-50", border: "border-amber-200", badge: "bg-amber-100 text-amber-800", text: "text-amber-700", btn: "bg-amber-600 hover:bg-amber-700" },
    };
    const c = colorClasses[cfg.color];

    const highlightCls = { good: "text-emerald-600 font-bold", warn: "text-amber-600 font-bold", bad: "text-red-600 font-bold" };

    const filteredTickets = showTickets
        ? (statusFilter === "ALL" ? cfg.ticketFilter : cfg.ticketFilter.filter(t => t.status === statusFilter))
        : [];

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className={`${c.bg} ${c.border} border-2 rounded-3xl p-6 shadow-xl`}
        >
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-2xl ${c.badge} flex items-center justify-center text-xl`}>
                        {cfg.icon}
                    </div>
                    <div>
                        <h3 className={`font-extrabold text-lg ${c.text}`}>{cfg.title}</h3>
                        <p className="text-xs text-gray-500">Metric deep-dive</p>
                    </div>
                </div>
                <button onClick={onClose} className="w-8 h-8 rounded-full bg-white/80 border border-gray-200 flex items-center justify-center text-gray-400 hover:text-gray-700 transition-colors">
                    ✕
                </button>
            </div>

            {/* Metrics grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
                {cfg.rows.map(row => (
                    <div key={row.label} className="bg-white rounded-2xl p-4 border border-white/60 shadow-sm">
                        <p className="text-xs text-gray-400 mb-1">{row.label}</p>
                        <p className={`text-xl font-extrabold ${row.highlight ? highlightCls[row.highlight] : "text-gray-800"}`}>{row.value}</p>
                    </div>
                ))}
            </div>

            {/* Insight callout */}
            <div className={`flex items-start gap-3 ${c.bg} border ${c.border} rounded-2xl p-4 mb-5`}>
                <span className="text-2xl mt-0.5">💡</span>
                <p className={`text-sm font-medium ${c.text}`}>{cfg.insight}</p>
            </div>

            {/* Dept breakdown for this metric */}
            {summary.by_department.length > 0 && (
                <div className="mb-5">
                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-3">Department Breakdown</p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                        {summary.by_department.map(d => {
                            const dTotal = d.open + d.closed;
                            const pct = dTotal > 0 ? Math.round((d.closed / dTotal) * 100) : 0;
                            const isProblematic = metricId === "sla" ? d.overdue > 0 : metricId === "critical" ? d.critical > 0 : metricId === "completion" ? pct < 50 : false;
                            return (
                                <div key={d.dept_id} className={`bg-white rounded-xl p-3 border text-xs ${isProblematic ? "border-red-200 bg-red-50" : "border-gray-100"}`}>
                                    <p className="font-bold text-gray-700 mb-1.5 truncate">{DEPT_NAMES[d.dept_id] ?? d.dept_id}</p>
                                    <div className="flex justify-between text-gray-500">
                                        <span>Open <span className="font-bold text-orange-600">{d.open}</span></span>
                                        <span>SLA <span className={`font-bold ${d.overdue > 0 ? "text-red-600" : "text-green-600"}`}>{d.overdue > 0 ? `${d.overdue} ⚠️` : "✓"}</span></span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Ticket viewer toggle */}
            <div className="flex items-center gap-3">
                <button
                    onClick={() => setShowTickets(v => !v)}
                    className={`${c.btn} text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors flex items-center gap-2`}
                >
                    {showTickets ? "▲ Hide Tickets" : `🎫 View Relevant Tickets (${cfg.ticketFilter.length})`}
                </button>
                {showTickets && cfg.ticketFilter.length > 0 && (
                    <div className="flex gap-2 flex-wrap">
                        {["ALL", "OPEN", "ASSIGNED", "IN_PROGRESS", "CLOSED"].map(s => (
                            <button key={s} onClick={() => setStatusFilter(s)}
                                className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all
                                    ${statusFilter === s ? "bg-gray-800 text-white" : "bg-white border border-gray-200 text-gray-600 hover:border-gray-400"}`}>
                                {s.replace(/_/g, " ")}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {/* Ticket table */}
            <AnimatePresence>
                {showTickets && (
                    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mt-4 overflow-hidden">
                        {filteredTickets.length === 0 ? (
                            <p className="text-sm text-gray-400 italic text-center py-6 bg-white rounded-2xl border border-gray-100">
                                No tickets matching this filter.
                            </p>
                        ) : (
                            <div className="bg-white rounded-2xl border border-gray-100 overflow-x-auto shadow-sm">
                                <table className="min-w-full divide-y divide-gray-100 text-sm">
                                    <thead className="bg-gray-50 text-gray-500 text-xs font-semibold uppercase tracking-wide">
                                        <tr>
                                            <th className="px-4 py-3 text-left">Ticket</th>
                                            <th className="px-4 py-3 text-left">Category</th>
                                            <th className="px-4 py-3 text-left">Ward</th>
                                            <th className="px-4 py-3 text-left">Priority</th>
                                            <th className="px-4 py-3 text-left">Status</th>
                                            <th className="px-4 py-3 text-left">SLA</th>
                                            <th className="px-4 py-3 text-right"></th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-50">
                                        {filteredTickets.slice(0, 20).map(t => {
                                            const isOverdue = t.sla_deadline && new Date(t.sla_deadline) < new Date() && !["CLOSED", "RESOLVED"].includes(t.status);
                                            return (
                                                <tr key={t.id} className="hover:bg-gray-50 transition-colors">
                                                    <td className="px-4 py-3 font-mono font-bold text-blue-600 whitespace-nowrap">{t.ticket_code}</td>
                                                    <td className="px-4 py-3 text-gray-700 font-medium max-w-[140px] truncate">{t.issue_category || "General"}</td>
                                                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{t.ward_id ? getWardLabel(t.ward_id) : "—"}</td>
                                                    <td className="px-4 py-3">
                                                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                                                            t.priority_label === "CRITICAL" ? "bg-red-100 text-red-700" :
                                                            t.priority_label === "HIGH" ? "bg-orange-100 text-orange-700" :
                                                            t.priority_label === "MEDIUM" ? "bg-yellow-100 text-yellow-700" :
                                                            "bg-green-100 text-green-700"
                                                        }`}>{t.priority_label}</span>
                                                    </td>
                                                    <td className="px-4 py-3"><StatusBadge status={t.status} size="sm" /></td>
                                                    <td className={`px-4 py-3 text-xs font-semibold ${isOverdue ? "text-red-600" : "text-gray-400"}`}>
                                                        {isOverdue ? "⚠️ Overdue" : t.sla_deadline ? "Within SLA" : "—"}
                                                    </td>
                                                    <td className="px-4 py-3 text-right">
                                                        <Link href={`/officer/tickets/${t.id}`}
                                                            className="text-xs font-semibold text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition-colors">
                                                            View →
                                                        </Link>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                                {filteredTickets.length > 20 && (
                                    <p className="text-xs text-gray-400 text-center py-3 border-t border-gray-100">
                                        Showing 20 of {filteredTickets.length} tickets.
                                        <Link href="/officer/tickets" className="text-blue-500 hover:underline ml-1">View all →</Link>
                                    </p>
                                )}
                            </div>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}

// ─── Supervisor Operational View ─────────────────────────────────────────────────────

function SupervisorDashboard({ user }: { user: { name: string; ward_id?: number; role: string } }) {
    const searchParams = useSearchParams();
    const [summary, setSummary] = useState<DashboardSummary | null>(null);
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeMetric, setActiveMetric] = useState<string | null>(null);

    useEffect(() => {
        Promise.all([officerApi.getDashboardSummary(), officerApi.getTickets(200)])
            .then(([s, t]) => { setSummary(s.data); setTickets(t.data); })
            .catch(() => toast.error("Failed to load dashboard"))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return (
        <div className="flex justify-center py-20">
            <div className="flex flex-col items-center gap-4">
                <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin" />
                <p className="text-sm text-blue-300 font-medium">Loading operations dashboard…</p>
            </div>
        </div>
    );

    if (!summary) return null;

    const now = new Date();
    const overdueCount = tickets.filter(t => t.sla_deadline && new Date(t.sla_deadline) < now && !["CLOSED", "REJECTED"].includes(t.status)).length;
    const assignedActive = tickets.filter(t => (t.assigned_officer_id || t.technician_id) && !["CLOSED", "RESOLVED"].includes(t.status)).length;

    // Compute metric scores [0-100]
    const completionScore = summary.total > 0 ? Math.round((summary.closed / summary.total) * 100) : 0;
    const slaScore = summary.open > 0 ? Math.round(((summary.open - overdueCount) / summary.open) * 100) : 100;
    const criticalScore = summary.total > 0 ? Math.round((1 - summary.critical / summary.total) * 100) : 100;
    const assignmentScore = summary.open > 0 ? Math.round((assignedActive / summary.open) * 100) : 100;
    const satisfactionScore = summary.avg_satisfaction !== null ? Math.round((summary.avg_satisfaction / 5) * 100) : 0;

    const getStatus = (score: number): "good" | "warn" | "critical" =>
        score >= 70 ? "good" : score >= 40 ? "warn" : "critical";

    const metrics = [
        {
            id: "completion", label: "Completion Rate", icon: "✅", value: completionScore,
            status: getStatus(completionScore),
            sublabel: `${summary.closed} of ${summary.total} closed`,
        },
        {
            id: "sla", label: "SLA Compliance", icon: "⏱️", value: slaScore,
            status: getStatus(slaScore),
            sublabel: overdueCount === 0 ? "All within SLA" : `${overdueCount} breached`,
        },
        {
            id: "critical", label: "Critical Load", icon: "🚨", value: criticalScore,
            status: getStatus(criticalScore),
            sublabel: summary.critical === 0 ? "No critical issues" : `${summary.critical} critical`,
        },
        {
            id: "assignment", label: "Assignment Rate", icon: "👷", value: assignmentScore,
            status: getStatus(assignmentScore),
            sublabel: `${assignedActive} of ${summary.open} assigned`,
        },
        {
            id: "satisfaction", label: "Satisfaction", icon: "⭐",
            value: satisfactionScore,
            status: summary.avg_satisfaction === null ? "warn" as const : getStatus(satisfactionScore),
            sublabel: summary.avg_satisfaction !== null ? `${summary.avg_satisfaction}/5 avg` : "No data yet",
        },
    ];

    const unsatisfied = metrics.filter(m => m.status !== "good");
    const deptFilter = searchParams.get('dept')?.toUpperCase();

    // Map standard D-codes to legacy acronyms used by seed_demo_tickets.py
    const legacyDeptMap: Record<string, string[]> = {
        "D01": ["D01", "PWD", "ROADS"],
        "D03": ["D03", "WATER"],
        "D04": ["D04", "DRAINAGE", "SEWAGE"],
        "D05": ["D05", "SWM", "WASTE"],
        "D06": ["D06", "ELEC", "LIGHTING"],
    };

    if (deptFilter && DEPT_NAMES[deptFilter]) {
        const allowedIds = legacyDeptMap[deptFilter] || [deptFilter];
        const filteredTickets = tickets.filter(t => allowedIds.includes(t.dept_id.toUpperCase()));
        return (
            <div className="space-y-6">
                <div>
                    <div className="flex items-center gap-3 mb-2">
                        <Link href="/officer/dashboard" className="text-sm font-medium text-slate-500 hover:text-indigo-600 transition-colors bg-white hover:bg-indigo-50 border border-slate-200 hover:border-indigo-200 px-4 py-2 rounded-xl inline-flex items-center gap-2 shadow-sm">
                            <span className="text-lg leading-none">←</span> Back to Overview
                        </Link>
                    </div>
                    <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-3 mt-4">
                        <span className="bg-indigo-100 text-indigo-700 w-10 h-10 flex items-center justify-center rounded-xl text-sm font-black border border-indigo-200 shrink-0">
                            {DEPT_NAMES[deptFilter].charAt(0)}
                        </span>
                        {DEPT_NAMES[deptFilter]}
                    </h2>
                    <p className="text-sm text-slate-500 mt-1.5 ml-14">Showing {filteredTickets.length} active issue{filteredTickets.length !== 1 ? 's' : ''} ranked by criticality level.</p>
                </div>
                <div className="bg-white rounded-3xl p-6 shadow-sm border border-slate-200">
                    <TicketList tickets={filteredTickets} />
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            {/* Header banner */}
            <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-7 border border-white/10 shadow-xl relative overflow-hidden">
                <div className="absolute inset-0 opacity-5" style={{ backgroundImage: "radial-gradient(circle at 20% 50%, #6366f1 0%, transparent 50%), radial-gradient(circle at 80% 50%, #06b6d4 0%, transparent 50%)" }} />
                <div className="relative z-10">
                    <div className="flex items-center justify-between flex-wrap gap-4 mb-6">
                        <div>
                            <p className="text-xs text-slate-400 font-semibold uppercase tracking-widest mb-1">Operations Control Center</p>
                            <h2 className="text-2xl font-extrabold text-white">Performance Overview</h2>
                            <p className="text-slate-400 text-sm mt-1">
                                {user.ward_id ? getWardLabel(user.ward_id) : "All Wards"} · Click any gauge to drill down
                            </p>
                        </div>
                        {unsatisfied.length > 0 ? (
                            <div className="bg-red-500/10 border border-red-400/30 rounded-2xl px-5 py-3">
                                <p className="text-red-300 text-xs font-semibold mb-0.5">⚠️ Attention Required</p>
                                <p className="text-white font-bold text-sm">{unsatisfied.length} metric{unsatisfied.length > 1 ? "s" : ""} below threshold</p>
                                <p className="text-slate-400 text-xs mt-0.5">{unsatisfied.map(m => m.label).join(" · ")}</p>
                            </div>
                        ) : (
                            <div className="bg-emerald-500/10 border border-emerald-400/30 rounded-2xl px-5 py-3">
                                <p className="text-emerald-300 text-xs font-semibold mb-0.5">✓ All Systems Nominal</p>
                                <p className="text-white font-bold text-sm">All metrics in good standing</p>
                            </div>
                        )}
                    </div>

                    {/* Gauge row */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                        {metrics.map(m => (
                            <SpeedometerGauge
                                key={m.id}
                                value={m.value}
                                label={m.label}
                                icon={m.icon}
                                sublabel={m.sublabel}
                                status={m.status}
                                active={activeMetric === m.id}
                                onClick={() => setActiveMetric(prev => prev === m.id ? null : m.id)}
                            />
                        ))}
                    </div>
                </div>
            </div>

            {/* Detail panel — shown when a metric is clicked */}
            <AnimatePresence mode="wait">
                {activeMetric && (
                    <MetricDetailPanel
                        key={activeMetric}
                        metricId={activeMetric}
                        summary={summary}
                        tickets={tickets}
                        onClose={() => setActiveMetric(null)}
                    />
                )}
            </AnimatePresence>

            {/* Quick count strip */}
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                {[
                    { label: "Total", value: summary.total, icon: "📋", cls: "text-slate-700" },
                    { label: "Open", value: summary.open, icon: "⚡", cls: "text-orange-600" },
                    { label: "Closed", value: summary.closed, icon: "✅", cls: "text-emerald-600" },
                    { label: "Overdue", value: overdueCount, icon: "⚠️", cls: overdueCount > 0 ? "text-red-600" : "text-gray-400" },
                    { label: "Critical", value: summary.critical, icon: "🚨", cls: summary.critical > 0 ? "text-red-700" : "text-gray-400" },
                    { label: "Satisfaction", value: summary.avg_satisfaction !== null ? `${summary.avg_satisfaction}/5` : "N/A", icon: "⭐", cls: "text-amber-600" },
                ].map(s => (
                    <div key={s.label} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 text-center">
                        <p className="text-xl mb-1">{s.icon}</p>
                        <p className={`text-2xl font-extrabold ${s.cls}`}>{s.value}</p>
                        <p className="text-xs text-gray-400 font-medium mt-0.5">{s.label}</p>
                    </div>
                ))}
            </div>

            {/* No active metric: show a hint */}
            {!activeMetric && (
                <div className="bg-slate-50 border border-slate-200 rounded-3xl p-8 text-center">
                    <p className="text-4xl mb-3">☝️</p>
                    <h3 className="text-base font-bold text-slate-700 mb-1">Select a metric gauge above to inspect it</h3>
                    <p className="text-sm text-slate-400">Each gauge reveals detailed breakdowns and lets you view the relevant tickets in context.</p>
                </div>
            )}

            {/* ── Resource Health & Optimizer ── */}
            <div className="pt-2">
                <ResourceHealthCard wardId={user.ward_id} />
            </div>
        </div>
    );
}

// ─── Junior Engineer Operational View ───────────────────────────────────────────

function JuniorEngineerDashboard({ user }: { user: { name: string; dept_id?: string; ward_id?: number; role: string } }) {
    const router = useRouter();
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);
    const [assignModalTicket, setAssignModalTicket] = useState<Ticket | null>(null);
    const [resolveModalTicket, setResolveModalTicket] = useState<Ticket | null>(null);

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

            <TicketList tickets={tickets} showAssign onStatusUpdate={handleStatusUpdate} onOpenAssignModal={handleOpenAssign} onOpenResolveModal={setResolveModalTicket} />

            {/* ── Feature 1: Resolve With Proof Modal ── */}
            {resolveModalTicket && (
                <ResolveWithProofModal
                    ticketId={resolveModalTicket.id}
                    ticketCode={resolveModalTicket.ticket_code}
                    issueType={resolveModalTicket.issue_category || "General"}
                    technicianId={user.name} // JE or Technician name
                    onSuccess={() => {
                        handleStatusUpdate(resolveModalTicket.id, "CLOSED");
                        // We could fetch again, but status update is fast enough
                    }}
                    onClose={() => setResolveModalTicket(null)}
                />
            )}

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
                <div className="flex gap-2 ml-2 relative group">
                    <button className="text-sm bg-indigo-600/90 border border-indigo-400/50 text-white font-medium px-4 py-2 rounded-xl hover:bg-indigo-600 transition-all flex items-center gap-2 shadow-lg hover:shadow-indigo-500/20">
                        <span className="text-base">🏢</span> Select Department ▾
                    </button>
                    {/* Flyout Menu Container with padding to bridge the hover gap */}
                    <div className="absolute top-full right-0 pt-2 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-300 z-50 transform group-hover:translate-y-0 translate-y-3 pointer-events-none group-hover:pointer-events-auto origin-top-right">
                        <div className="w-72 bg-slate-900/95 backdrop-blur-xl border border-slate-700/50 rounded-2xl shadow-2xl overflow-hidden p-3">
                            <p className="text-[10px] font-extrabold text-slate-500 uppercase tracking-widest mb-3 px-3">Department Operations</p>
                            <div className="max-h-[50vh] overflow-y-auto rounded-xl space-y-1 pr-1 custom-scrollbar">
                                {Object.entries(DEPT_NAMES).map(([id, name]) => (
                                    <Link key={id} href={`?dept=${id.toLowerCase()}`}
                                        className="group/item block px-3 py-2.5 rounded-xl text-sm text-slate-300 hover:bg-white/10 hover:text-white transition-all flex items-center justify-between"
                                    >
                                        <div className="flex items-center gap-3 truncate">
                                            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-300 flex items-center justify-center text-xs font-bold border border-indigo-500/20 group-hover/item:border-indigo-400/40 group-hover/item:text-indigo-200 transition-colors shrink-0">
                                                {name.charAt(0)}
                                            </div>
                                            <span className="truncate font-medium">{name}</span>
                                        </div>
                                        <span className="text-slate-600 group-hover/item:text-slate-400 group-hover/item:translate-x-1 transition-transform">→</span>
                                    </Link>
                                ))}
                            </div>
                        </div>
                    </div>
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
