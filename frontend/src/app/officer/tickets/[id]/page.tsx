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
    technician_id?: string;
    scheduled_date?: string;
    ai_suggested_date?: string;
    completion_deadline?: string;
    after_photo_url?: string;
    is_validated?: boolean;
}

const STATUSES = ["OPEN", "ASSIGNED", "SCHEDULED", "IN_PROGRESS", "AWAITING_MATERIAL", "PENDING_VERIFICATION", "CLOSED", "REJECTED"];

export default function TicketDetailPage() {
    const params = useParams();
    const router = useRouter();
    const { isOfficer, isSupervisor, isJuniorEngineer, isFieldStaff } = useAuth();
    const ticketId = params?.id as string;

    const [ticket, setTicket] = useState<TicketDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [updating, setUpdating] = useState(false);
    const [showOverride, setShowOverride] = useState(false);
    const [overrideScore, setOverrideScore] = useState(50);
    const [overrideReason, setOverrideReason] = useState("");
    const [newStatus, setNewStatus] = useState("");

    const [engineers, setEngineers] = useState<{ id: string; name: string; email: string }[]>([]);
    const [selectedEngineer, setSelectedEngineer] = useState("");
    const [validating, setValidating] = useState(false);
    const [valCat, setValCat] = useState(true);
    const [valDup, setValDup] = useState(false);
    const [valWard, setValWard] = useState(true);

    const [fieldStaffList, setFieldStaffList] = useState<{ id: string; name: string; email: string }[]>([]);
    const [selectedFieldStaff, setSelectedFieldStaff] = useState("");
    const [scheduledDate, setScheduledDate] = useState("");

    const [locationHistory, setLocationHistory] = useState<any[]>([]);

    const [proofUrl, setProofUrl] = useState("");
    const [uploadingProof, setUploadingProof] = useState(false);
    const [showProofUpload, setShowProofUpload] = useState(false);

    // Completion deadline workflow
    const [deadlineDate, setDeadlineDate] = useState("");
    const [settingDeadline, setSettingDeadline] = useState(false);
    const [showDeadlinePicker, setShowDeadlinePicker] = useState(false);

    useEffect(() => {
        if (!isOfficer) { router.push("/login"); return; }
        officerApi.getTicket(ticketId)
            .then((res) => {
                setTicket(res.data);
                setNewStatus(res.data.status);
            })
            .catch(() => toast.error("Ticket not found"))
            .finally(() => setLoading(false));

        if (isSupervisor) {
            officerApi.getJuniorEngineers().then(res => setEngineers(res.data)).catch(console.error);
        }

        if (isJuniorEngineer) {
            officerApi.getFieldStaff().then(res => setFieldStaffList(res.data)).catch(console.error);
        }

        officerApi.getLocationHistory(ticketId).then(res => setLocationHistory(res.data)).catch(console.error);
    }, [ticketId, isOfficer, isSupervisor, isJuniorEngineer, router]);

    const handleStatusUpdate = async () => {
        if (!ticket || newStatus === ticket.status) return;
        setUpdating(true);
        try {
            await officerApi.updateStatus(ticket.id, newStatus);
            setTicket((prev) => prev ? { ...prev, status: newStatus } : prev);
            toast.success(`Status updated to ${newStatus.replace(/_/g, " ")}`);
            setShowProofUpload(false);
        } catch {
            toast.error("Failed to update status");
        } finally {
            setUpdating(false);
        }
    };

    const handleQuickStatus = async (status: string) => {
        setUpdating(true);
        try {
            await officerApi.updateStatus(ticketId, status);
            setTicket((prev) => prev ? { ...prev, status } : prev);
            setNewStatus(status);
            toast.success(`Status updated to ${status.replace(/_/g, " ")}`);
        } catch {
            toast.error("Failed to update status");
        } finally {
            setUpdating(false);
        }
    };

    const handleValidate = async () => {
        setValidating(true);
        try {
            await officerApi.validateTicket(ticketId, {
                category_confirmed: valCat,
                is_duplicate: valDup,
                ward_confirmed: valWard
            });
            setTicket(prev => prev ? { ...prev, is_validated: true } : prev);
            toast.success("Ticket validated!");
        } catch {
            toast.error("Validation failed");
        } finally {
            setValidating(false);
        }
    };

    const handleAssign = async () => {
        if (!selectedEngineer) return;
        setUpdating(true);
        try {
            await officerApi.assignTicket(ticketId, selectedEngineer);
            setTicket(prev => prev ? { ...prev, assigned_officer_id: selectedEngineer, status: "ASSIGNED" } : prev);
            setNewStatus("ASSIGNED");
            toast.success("Assigned to Junior Engineer");
        } catch {
            toast.error("Assignment failed");
        } finally {
            setUpdating(false);
        }
    };

    const handleAssignField = async () => {
        if (!selectedFieldStaff || !scheduledDate) {
            toast.error("Select staff and date");
            return;
        }
        setUpdating(true);
        try {
            await officerApi.assignFieldStaff(ticketId, selectedFieldStaff, scheduledDate);
            setTicket(prev => prev ? { ...prev, technician_id: selectedFieldStaff, scheduled_date: scheduledDate, status: "SCHEDULED" } : prev);
            setNewStatus("SCHEDULED");
            toast.success("Assigned to Field Staff!");
        } catch {
            toast.error("Field assignment failed");
        } finally {
            setUpdating(false);
        }
    };

    const handleProofUpload = async () => {
        if (!proofUrl.trim()) { toast.error("Please enter a photo URL"); return; }
        setUploadingProof(true);
        try {
            await officerApi.uploadProof(ticketId, proofUrl);
            setTicket(prev => prev ? { ...prev, after_photo_url: proofUrl } : prev);
            await handleQuickStatus("PENDING_VERIFICATION");
        } catch {
            toast.error("Proof upload failed");
        } finally {
            setUploadingProof(false);
            setShowProofUpload(false);
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

    const handleSetDeadline = async (useAiSuggestion: boolean) => {
        if (!ticket) return;
        const dateToUse = useAiSuggestion
            ? ticket.ai_suggested_date
            : deadlineDate;
        if (!dateToUse) { toast.error("No date selected"); return; }

        // Client-side SLA guard
        if (ticket.sla_deadline && new Date(dateToUse) > new Date(ticket.sla_deadline)) {
            toast.error(`Deadline cannot breach SLA (${new Date(ticket.sla_deadline).toLocaleDateString("en-IN")})`);
            return;
        }

        setSettingDeadline(true);
        try {
            const isoDate = new Date(dateToUse).toISOString();
            await officerApi.setCompletionDeadline(ticket.id, isoDate, useAiSuggestion);
            setTicket(prev => prev ? { ...prev, completion_deadline: isoDate } : prev);
            setShowDeadlinePicker(false);
            setDeadlineDate("");
            toast.success(`⏰ Completion deadline set to ${new Date(dateToUse).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}. Calendar reminder added!`);
        } catch (err: unknown) {
            const e = err as { response?: { data?: { detail?: { message?: string } | string } } };
            const detail = e?.response?.data?.detail;
            if (typeof detail === "object" && detail?.message) {
                toast.error(`SLA breach: ${detail.message}`);
            } else {
                toast.error("Failed to set deadline");
            }
        } finally {
            setSettingDeadline(false);
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

                                {/* Proof Image (If Complete) */}
                                {ticket.after_photo_url && (
                                    <div className="bg-gray-50 rounded-xl p-4 mt-4">
                                        <p className="text-xs text-gray-400 mb-2">Resolution Proof</p>
                                        <img src={ticket.after_photo_url} alt="Proof" className="w-full rounded-lg border border-gray-200 object-cover max-h-64" />
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

                        {/* Location History */}
                        {locationHistory.length > 0 && (
                            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mt-6">
                                <h2 className="font-bold text-gray-900 mb-4">📍 Location History (Recurring Issues)</h2>
                                <div className="space-y-3">
                                    {locationHistory.map((t) => (
                                        <div key={t.id} className="bg-gray-50 border border-gray-100 rounded-xl p-3 flex justify-between items-center">
                                            <div>
                                                <p className="font-mono font-bold text-blue-700 text-sm">{t.ticket_code}</p>
                                                <p className="text-xs text-gray-500 mt-0.5">{t.description.substring(0, 50)}...</p>
                                            </div>
                                            <div className="text-right">
                                                <StatusBadge status={t.status} size="sm" />
                                                <p className="text-xs text-gray-400 mt-1">{formatRelative(t.created_at)}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Right column — actions, timeline */}
                    <div className="space-y-5">
                        {/* Validation & Assignment logic for Supervisors */}
                        {isSupervisor && (
                            <>
                                {/* Validation Block */}
                                {!ticket.is_validated && (
                                    <div className="bg-yellow-50 border border-yellow-200 rounded-2xl shadow-sm p-5">
                                        <h3 className="font-bold text-yellow-800 mb-3 flex items-center gap-2">✔️ Validate Ticket</h3>
                                        <div className="space-y-2 mb-4">
                                            <label className="flex items-center gap-2 text-sm text-yellow-900 cursor-pointer">
                                                <input type="checkbox" checked={valCat} onChange={e => setValCat(e.target.checked)} className="rounded text-yellow-600 focus:ring-yellow-500" />
                                                Category confirmed
                                            </label>
                                            <label className="flex items-center gap-2 text-sm text-yellow-900 cursor-pointer">
                                                <input type="checkbox" checked={valWard} onChange={e => setValWard(e.target.checked)} className="rounded text-yellow-600 focus:ring-yellow-500" />
                                                Ward jurisdiction confirmed
                                            </label>
                                            <label className="flex items-center gap-2 text-sm text-yellow-900 cursor-pointer">
                                                <input type="checkbox" checked={valDup} onChange={e => setValDup(e.target.checked)} className="rounded text-yellow-600 focus:ring-yellow-500" />
                                                Flag as duplicate
                                            </label>
                                        </div>
                                        <button
                                            onClick={handleValidate}
                                            disabled={validating}
                                            className="w-full bg-yellow-500 hover:bg-yellow-600 text-white rounded-xl py-2 text-sm font-semibold transition-colors disabled:opacity-50"
                                        >
                                            {validating ? "Validating..." : "Confirm & Validate"}
                                        </button>
                                    </div>
                                )}

                                {/* ─── COMPLETION DEADLINE CARD ─────────────────── */}
                                <div className="bg-white border border-pink-200 rounded-2xl shadow-sm p-5">
                                    <h3 className="font-bold text-gray-900 mb-1 flex items-center gap-2">
                                        ⏰ Completion Deadline
                                    </h3>
                                    <p className="text-xs text-gray-400 mb-4">Set a deadline before which the work must be completed. Must not breach the SLA.</p>

                                    {/* Already confirmed */}
                                    {ticket.completion_deadline && (
                                        <div className="bg-pink-50 border border-pink-200 rounded-xl p-3 mb-4">
                                            <p className="text-xs text-pink-500 font-semibold mb-0.5">✅ Deadline Confirmed</p>
                                            <p className="text-sm font-bold text-pink-700">
                                                {new Date(ticket.completion_deadline).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}
                                            </p>
                                            <p className="text-xs text-pink-400 mt-1">🔔 A calendar reminder has been added</p>
                                        </div>
                                    )}

                                    {/* AI Suggestion */}
                                    {ticket.ai_suggested_date && (
                                        <div className="bg-purple-50 border border-purple-200 rounded-xl p-3 mb-3">
                                            <p className="text-xs text-purple-600 font-semibold mb-1">✨ AI Suggested Date</p>
                                            <p className="text-sm font-bold text-purple-800">
                                                {new Date(ticket.ai_suggested_date).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}
                                            </p>
                                            {ticket.sla_deadline && (
                                                <p className="text-xs text-purple-400 mt-1">
                                                    SLA: {new Date(ticket.sla_deadline).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                                                </p>
                                            )}
                                            <button
                                                onClick={() => handleSetDeadline(true)}
                                                disabled={settingDeadline}
                                                className="mt-2 w-full bg-purple-600 hover:bg-purple-700 text-white rounded-lg py-2 text-xs font-semibold transition-colors disabled:opacity-50"
                                            >
                                                {settingDeadline ? "Saving…" : "✅ Accept AI Suggestion"}
                                            </button>
                                        </div>
                                    )}

                                    {/* Manual Override */}
                                    {!showDeadlinePicker ? (
                                        <button
                                            onClick={() => setShowDeadlinePicker(true)}
                                            className="w-full border border-pink-300 text-pink-700 rounded-xl py-2 text-xs font-semibold hover:bg-pink-50 transition-colors"
                                        >
                                            📅 {ticket.completion_deadline ? "Change Deadline" : "Set Manual Deadline"}
                                        </button>
                                    ) : (
                                        <motion.div
                                            initial={{ opacity: 0, height: 0 }}
                                            animate={{ opacity: 1, height: "auto" }}
                                            className="space-y-2"
                                        >
                                            <p className="text-xs text-gray-600 font-medium">Pick a date (before SLA deadline):</p>
                                            <input
                                                type="date"
                                                value={deadlineDate}
                                                onChange={e => setDeadlineDate(e.target.value)}
                                                min={new Date().toISOString().split("T")[0]}
                                                max={ticket.sla_deadline ? new Date(ticket.sla_deadline).toISOString().split("T")[0] : undefined}
                                                className="w-full border border-pink-200 bg-pink-50 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400"
                                            />
                                            <div className="flex gap-2">
                                                <button
                                                    onClick={() => handleSetDeadline(false)}
                                                    disabled={settingDeadline || !deadlineDate}
                                                    className="flex-1 bg-pink-600 hover:bg-pink-700 text-white rounded-xl py-2 text-xs font-semibold transition-colors disabled:opacity-50"
                                                >
                                                    {settingDeadline ? "Saving…" : "Confirm Deadline"}
                                                </button>
                                                <button onClick={() => { setShowDeadlinePicker(false); setDeadlineDate(""); }} className="text-xs text-gray-500 px-3">
                                                    Cancel
                                                </button>
                                            </div>
                                        </motion.div>
                                    )}
                                </div>

                                {/* Assignment Block */}
                                {ticket.status === "OPEN" && ticket.is_validated && (
                                    <div className="bg-blue-50 border border-blue-200 rounded-2xl shadow-sm p-5">
                                        <h3 className="font-bold text-blue-800 mb-3 flex items-center gap-2">👤 Assign Junior Engineer</h3>
                                        <select
                                            value={selectedEngineer}
                                            onChange={(e) => setSelectedEngineer(e.target.value)}
                                            className="w-full border border-blue-200 bg-white rounded-xl px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        >
                                            <option value="">-- Select Engineer --</option>
                                            {engineers.map(je => (
                                                <option key={je.id} value={je.id}>{je.name} ({je.email})</option>
                                            ))}
                                        </select>
                                        <button
                                            onClick={handleAssign}
                                            disabled={updating || !selectedEngineer}
                                            className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-xl py-2 text-sm font-semibold transition-colors disabled:opacity-50"
                                        >
                                            {updating ? "Assigning..." : "Assign Ticket"}
                                        </button>
                                    </div>
                                )}
                            </>
                        )}

                        {/* Field Staff Assignment Block */}
                        {isJuniorEngineer && ticket.status === "ASSIGNED" && (
                            <div className="bg-emerald-50 border border-emerald-200 rounded-2xl shadow-sm p-5">
                                <h3 className="font-bold text-emerald-800 mb-3 flex items-center gap-2">👷 Assign Field Staff</h3>
                                <select
                                    value={selectedFieldStaff}
                                    onChange={(e) => setSelectedFieldStaff(e.target.value)}
                                    className="w-full border border-emerald-200 bg-white rounded-xl px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                                >
                                    <option value="">-- Select Field Staff --</option>
                                    {fieldStaffList.map(fs => (
                                        <option key={fs.id} value={fs.id}>{fs.name} ({fs.email})</option>
                                    ))}
                                </select>
                                <input
                                    type="date"
                                    value={scheduledDate}
                                    onChange={(e) => setScheduledDate(e.target.value)}
                                    className="w-full border border-emerald-200 bg-white rounded-xl px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                                    min={new Date().toISOString().split("T")[0]}
                                />
                                <button
                                    onClick={handleAssignField}
                                    disabled={updating || !selectedFieldStaff || !scheduledDate}
                                    className="w-full bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl py-2 text-sm font-semibold transition-colors disabled:opacity-50"
                                >
                                    {updating ? "Assigning..." : "Assign & Schedule"}
                                </button>
                            </div>
                        )}

                        {/* Execution Toolbar */}
                        {(isJuniorEngineer || isFieldStaff) && ["SCHEDULED", "IN_PROGRESS", "AWAITING_MATERIAL"].includes(ticket.status) && (
                            <div className="bg-indigo-50 border border-indigo-200 rounded-2xl shadow-sm p-5 space-y-3">
                                <h3 className="font-bold text-indigo-800 flex items-center gap-2">⚙️ Execution Workflow</h3>

                                {ticket.status === "SCHEDULED" && (
                                    <button onClick={() => handleQuickStatus("IN_PROGRESS")} disabled={updating} className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-xl py-2 text-sm font-semibold transition-colors disabled:opacity-50">
                                        ▶️ Start Work
                                    </button>
                                )}
                                {ticket.status === "AWAITING_MATERIAL" && (
                                    <button onClick={() => handleQuickStatus("IN_PROGRESS")} disabled={updating} className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-xl py-2 text-sm font-semibold transition-colors disabled:opacity-50">
                                        ▶️ Resume Work (Got Material)
                                    </button>
                                )}
                                {ticket.status === "IN_PROGRESS" && (
                                    <>
                                        <button onClick={() => handleQuickStatus("AWAITING_MATERIAL")} disabled={updating} className="w-full bg-yellow-500 hover:bg-yellow-600 text-white rounded-xl py-2 text-sm font-semibold transition-colors disabled:opacity-50">
                                            📦 Awaiting Material
                                        </button>
                                        <button onClick={() => setShowProofUpload(true)} disabled={updating} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl py-2 text-sm font-semibold transition-colors disabled:opacity-50 mt-2">
                                            ✅ Complete Work (Upload Proof)
                                        </button>
                                    </>
                                )}

                                {/* Proof Upload Modal/Block */}
                                {showProofUpload && (
                                    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mt-4 pt-4 border-t border-indigo-200 space-y-3">
                                        <p className="text-sm font-medium text-indigo-900">Upload Photo Evidence</p>
                                        <input
                                            type="url"
                                            value={proofUrl}
                                            onChange={e => setProofUrl(e.target.value)}
                                            placeholder="Valid image URL (e.g. https://imgur.com/...)"
                                            className="w-full border border-indigo-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        />
                                        <div className="flex gap-2">
                                            <button onClick={handleProofUpload} disabled={uploadingProof} className="flex-1 bg-indigo-600 text-white rounded-xl py-2 text-sm font-semibold transition-colors hover:bg-indigo-700">
                                                {uploadingProof ? "Uploading..." : "Submit Proof"}
                                            </button>
                                            <button onClick={() => setShowProofUpload(false)} className="text-sm text-gray-500 px-3 hover:text-gray-800">Cancel</button>
                                        </div>
                                    </motion.div>
                                )}
                            </div>
                        )}

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
