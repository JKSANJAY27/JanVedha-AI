"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { officerApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { formatDate, formatRelative, slaStatus } from "@/lib/formatters";
import PriorityBadge from "@/components/PriorityBadge";
import StatusBadge from "@/components/StatusBadge";
import Timeline from "@/components/Timeline";
import { DEPT_NAMES } from "@/lib/constants";

interface TicketDetail {
    id: string;
    ticket_code: string;
    status: string;
    description: string;
    dept_id: string;
    issue_category?: string;
    priority_label: string;
    priority_score: number;
    priority_source?: string;
    ai_routing_reason?: string;
    suggestions?: string[];
    seasonal_alert?: string;
    reporter_name?: string;
    ward_id?: number;
    sla_deadline?: string;
    created_at: string;
    assigned_officer_id?: string;
}

const STATUSES = ["OPEN", "ASSIGNED", "IN_PROGRESS", "PENDING_VERIFICATION", "CLOSED", "REJECTED"];

export default function TicketDetailPage() {
    const params = useParams();
    const router = useRouter();
    const { isOfficer } = useAuth();
    const ticketId = params?.id as string;

    const [ticket, setTicket] = useState<TicketDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [updating, setUpdating] = useState(false);
    const [showOverride, setShowOverride] = useState(false);
    const [overrideScore, setOverrideScore] = useState(50);
    const [overrideReason, setOverrideReason] = useState("");
    const [newStatus, setNewStatus] = useState("");

    useEffect(() => {
        if (!isOfficer) { router.push("/login"); return; }
        officerApi.getTicket(ticketId)
            .then((res) => {
                setTicket(res.data);
                setNewStatus(res.data.status);
            })
            .catch(() => toast.error("Ticket not found"))
            .finally(() => setLoading(false));
    }, [ticketId]);

    const handleStatusUpdate = async () => {
        if (!ticket || newStatus === ticket.status) return;
        setUpdating(true);
        try {
            await officerApi.updateStatus(ticket.id, newStatus);
            setTicket((prev) => prev ? { ...prev, status: newStatus } : prev);
            toast.success(`Status updated to ${newStatus.replace(/_/g, " ")}`);
        } catch {
            toast.error("Failed to update status");
        } finally {
            setUpdating(false);
        }
    };

    const handleOverride = async () => {
        if (!ticket || !overrideReason.trim()) { toast.error("Please provide a reason"); return; }
        setUpdating(true);
        try {
            const res = await officerApi.overridePriority(ticket.id, overrideScore, overrideReason);
            setTicket((prev) => prev ? { ...prev, priority_score: res.data.priority_score, priority_label: res.data.priority_label } : prev);
            setShowOverride(false);
            toast.success("Priority overridden successfully");
        } catch {
            toast.error("Override failed");
        } finally {
            setUpdating(false);
        }
    };

    const sla = slaStatus(ticket?.sla_deadline);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
            </div>
        );
    }

    if (!ticket) {
        return (
            <div className="flex items-center justify-center min-h-screen text-center">
                <div>
                    <div className="text-5xl mb-4">❌</div>
                    <h2 className="text-xl font-bold text-gray-800">Ticket not found</h2>
                    <button onClick={() => router.back()} className="mt-4 text-blue-600 hover:underline">← Go back</button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-4 py-4 sticky top-16 z-30">
                <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                        <button onClick={() => router.back()} className="text-gray-500 hover:text-gray-800 transition-colors">← Back</button>
                        <span className="text-gray-300">|</span>
                        <span className="font-mono font-bold text-blue-700 text-lg">{ticket.ticket_code}</span>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                        <PriorityBadge label={ticket.priority_label} score={ticket.priority_score} />
                        <StatusBadge status={ticket.status} />
                    </div>
                </div>
            </div>

            <div className="max-w-6xl mx-auto px-4 py-8">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left column — main info */}
                    <div className="lg:col-span-2 space-y-5">
                        {/* Issue details */}
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                            <h2 className="font-bold text-gray-900 mb-4">Issue Details</h2>
                            <div className="space-y-3">
                                <div className="bg-gray-50 rounded-xl p-4">
                                    <p className="text-xs text-gray-400 mb-1">Description</p>
                                    <p className="text-sm text-gray-800 leading-relaxed">{ticket.description}</p>
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                    <div className="bg-gray-50 rounded-xl p-3">
                                        <p className="text-xs text-gray-400 mb-0.5">Department</p>
                                        <p className="text-sm font-medium text-gray-800">{DEPT_NAMES[ticket.dept_id] ?? ticket.dept_id}</p>
                                    </div>
                                    {ticket.issue_category && (
                                        <div className="bg-gray-50 rounded-xl p-3">
                                            <p className="text-xs text-gray-400 mb-0.5">Category</p>
                                            <p className="text-sm font-medium text-gray-800">{ticket.issue_category}</p>
                                        </div>
                                    )}
                                    {ticket.reporter_name && (
                                        <div className="bg-gray-50 rounded-xl p-3">
                                            <p className="text-xs text-gray-400 mb-0.5">Reporter</p>
                                            <p className="text-sm font-medium text-gray-800">{ticket.reporter_name}</p>
                                        </div>
                                    )}
                                    {ticket.ward_id && (
                                        <div className="bg-gray-50 rounded-xl p-3">
                                            <p className="text-xs text-gray-400 mb-0.5">Ward</p>
                                            <p className="text-sm font-medium text-gray-800">Ward {ticket.ward_id}</p>
                                        </div>
                                    )}
                                    <div className="bg-gray-50 rounded-xl p-3">
                                        <p className="text-xs text-gray-400 mb-0.5">Submitted</p>
                                        <p className="text-sm font-medium text-gray-800">{formatDate(ticket.created_at)}</p>
                                    </div>
                                    {ticket.sla_deadline && (
                                        <div className="bg-gray-50 rounded-xl p-3">
                                            <p className="text-xs text-gray-400 mb-0.5">SLA Deadline</p>
                                            <p className={`text-sm font-medium ${sla.label.includes("Breached") ? "text-red-600" : "text-gray-800"}`}>
                                                {formatDate(ticket.sla_deadline)}
                                            </p>
                                        </div>
                                    )}
                                </div>

                                {/* SLA bar */}
                                {ticket.sla_deadline && (
                                    <div>
                                        <div className="flex justify-between text-xs text-gray-500 mb-1">
                                            <span>SLA Status</span>
                                            <span className={sla.label.includes("Breached") ? "text-red-600 font-semibold" : ""}>{sla.label}</span>
                                        </div>
                                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                            <div className={`h-full rounded-full ${sla.color}`} style={{ width: `${sla.pct}%` }} />
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Priority analysis */}
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="font-bold text-gray-900">Priority Analysis</h2>
                                <button
                                    onClick={() => setShowOverride(!showOverride)}
                                    className="text-xs text-indigo-600 border border-indigo-200 rounded-lg px-3 py-1.5 hover:bg-indigo-50 transition-colors"
                                >
                                    ⚡ Override Priority
                                </button>
                            </div>

                            <div className="flex items-center gap-4 mb-4">
                                <PriorityBadge label={ticket.priority_label} score={ticket.priority_score} size="lg" />
                                {ticket.priority_source && (
                                    <span className="text-xs text-gray-400 bg-gray-50 rounded-full px-3 py-1">
                                        Source: {ticket.priority_source.replace(/_/g, " ")}
                                    </span>
                                )}
                            </div>

                            {/* Score bar */}
                            <div className="mb-4">
                                <div className="flex justify-between text-xs text-gray-400 mb-1">
                                    <span>Score: {ticket.priority_score}/100</span>
                                    <span>Threshold: 80 = Critical</span>
                                </div>
                                <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all duration-700 ${ticket.priority_score >= 80 ? "bg-gradient-to-r from-red-400 to-red-600" :
                                                ticket.priority_score >= 60 ? "bg-gradient-to-r from-orange-400 to-orange-600" :
                                                    ticket.priority_score >= 35 ? "bg-gradient-to-r from-yellow-400 to-yellow-600" : "bg-gradient-to-r from-green-400 to-green-600"
                                            }`}
                                        style={{ width: `${ticket.priority_score}%` }}
                                    />
                                </div>
                            </div>

                            {ticket.ai_routing_reason && (
                                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                                    <p className="text-xs font-semibold text-amber-700 mb-1">🤖 AI Routing Reason</p>
                                    <p className="text-sm text-amber-800">{ticket.ai_routing_reason}</p>
                                </div>
                            )}

                            {/* Override form */}
                            {showOverride && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: "auto" }}
                                    className="mt-4 border-t border-gray-100 pt-4"
                                >
                                    <p className="text-sm font-medium text-gray-700 mb-3">Override Priority Score</p>
                                    <div className="flex items-center gap-3 mb-3">
                                        <input
                                            type="range"
                                            min="0"
                                            max="100"
                                            value={overrideScore}
                                            onChange={(e) => setOverrideScore(Number(e.target.value))}
                                            className="flex-1"
                                        />
                                        <span className="text-sm font-bold text-gray-800 w-8">{overrideScore}</span>
                                    </div>
                                    <input
                                        type="text"
                                        value={overrideReason}
                                        onChange={(e) => setOverrideReason(e.target.value)}
                                        placeholder="Reason for override (required)…"
                                        className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                    />
                                    <div className="flex gap-2">
                                        <button
                                            onClick={handleOverride}
                                            disabled={updating}
                                            className="flex-1 bg-indigo-600 text-white rounded-lg py-2 text-sm font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-60"
                                        >
                                            {updating ? "Saving…" : "Apply Override"}
                                        </button>
                                        <button onClick={() => setShowOverride(false)} className="text-sm text-gray-500 px-4">Cancel</button>
                                    </div>
                                </motion.div>
                            )}
                        </div>

                        {/* AI Suggestions */}
                        {ticket.suggestions && ticket.suggestions.length > 0 && (
                            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                                <h2 className="font-bold text-gray-900 mb-4">💡 AI Action Suggestions</h2>
                                <ol className="space-y-2">
                                    {ticket.suggestions.map((s, i) => (
                                        <li key={i} className="flex gap-3 text-sm">
                                            <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 font-bold flex items-center justify-center flex-shrink-0 text-xs">
                                                {i + 1}
                                            </span>
                                            <span className="text-gray-700 pt-0.5">{s}</span>
                                        </li>
                                    ))}
                                </ol>
                            </div>
                        )}
                    </div>

                    {/* Right column — actions, timeline */}
                    <div className="space-y-5">
                        {/* Status update */}
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                            <h3 className="font-bold text-gray-900 mb-3">Update Status</h3>
                            <select
                                value={newStatus}
                                onChange={(e) => setNewStatus(e.target.value)}
                                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            >
                                {STATUSES.map((s) => (
                                    <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
                                ))}
                            </select>
                            <button
                                onClick={handleStatusUpdate}
                                disabled={updating || newStatus === ticket.status}
                                className="w-full bg-blue-600 text-white rounded-xl py-2.5 text-sm font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50"
                            >
                                {updating ? "Updating…" : "Save Status"}
                            </button>
                        </div>

                        {/* Seasonal alert */}
                        {ticket.seasonal_alert && (
                            <div className="bg-orange-50 border border-orange-200 rounded-2xl p-4 text-sm text-orange-800">
                                <p className="font-semibold mb-1">🌤️ Seasonal Alert</p>
                                <p>{ticket.seasonal_alert}</p>
                            </div>
                        )}

                        {/* Timeline */}
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                            <h3 className="font-bold text-gray-900 mb-4">📅 Timeline</h3>
                            <Timeline
                                events={[
                                    { event: "CREATED", timestamp: ticket.created_at, actor: "AI Pipeline" },
                                    ...(ticket.assigned_officer_id ? [{ event: "ASSIGNED", actor: `Officer ${ticket.assigned_officer_id.substring(0, 8)}…` }] : []),
                                    { event: ticket.status === "CLOSED" ? "CLOSED" : "STATUS_CHANGED", actor: "Officer" },
                                ]}
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
