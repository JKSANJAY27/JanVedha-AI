"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { publicApi } from "@/lib/api";
import { formatDate, formatRelative } from "@/lib/formatters";
import StatusBadge from "@/components/StatusBadge";
import Timeline from "@/components/Timeline";
import NotificationTimeline from "@/components/NotificationTimeline";
import { DEPT_NAMES } from "@/lib/constants";

interface Ticket {
    id: string;
    ticket_code: string;
    status: string;
    description: string;
    dept_id: string;
    issue_category: string | null;
    priority_label: string;
    priority_score: number;
    location_text: string | null;
    created_at: string;
    sla_deadline: string | null;
    withdrawal_reason: string | null;
    withdrawal_description: string | null;
    withdrawn_at: string | null;
}

interface TicketDetail {
    ticket_code: string;
    status: string;
    description: string;
    department: string;
    issue_category?: string;
    created_at: string;
    sla_deadline?: string;
    location_text?: string;
    seasonal_alert?: string;
    work_verified?: boolean | null;
    work_verification_explanation?: string | null;
    work_verification_confidence?: number | null;
    after_photo_url?: string | null;
    work_verified_at?: string | null;
    timeline?: Array<{
        event: string;
        timestamp: string;
        actor?: string;
        reason?: string;
    }>;
}

const STATUS_STEPS = ["OPEN", "ASSIGNED", "SCHEDULED", "IN_PROGRESS", "CLOSED"];
const STATUS_LABELS: Record<string, string> = {
    OPEN: "Submitted",
    ASSIGNED: "Officer Assigned",
    SCHEDULED: "Work Scheduled",
    IN_PROGRESS: "On-site Work",
    CLOSED: "Completed",
    REJECTED: "Rejected",
    WITHDRAWN: "Withdrawn",
};

const WITHDRAWAL_REASONS: Record<string, string> = {
    already_resolved: "Issue already resolved",
    submitted_by_mistake: "Complaint submitted by mistake",
    duplicate: "Duplicate complaint",
    no_longer_relevant: "No longer relevant",
    other: "Other",
};

const WITHDRAWAL_ICONS: Record<string, string> = {
    already_resolved: "✅",
    submitted_by_mistake: "🙏",
    duplicate: "📋",
    no_longer_relevant: "🕐",
    other: "💬",
};

function ProgressTracker({ status }: { status: string }) {
    if (status === "WITHDRAWN" || status === "REJECTED") {
        return (
            <div className={`rounded-xl px-4 py-3 text-sm font-semibold flex items-center gap-2 mb-6 ${
                status === "WITHDRAWN"
                    ? "bg-gray-100 text-gray-600 border border-gray-200"
                    : "bg-red-50 text-red-700 border border-red-200"
            }`}>
                <span>{status === "WITHDRAWN" ? "🚫" : "❌"}</span>
                {status === "WITHDRAWN" ? "You withdrew this complaint" : "This complaint was rejected"}
            </div>
        );
    }
    const currentIdx = STATUS_STEPS.indexOf(status);
    return (
        <div className="flex items-center gap-0 w-full mb-6">
            {STATUS_STEPS.map((s, i) => {
                const done = i <= currentIdx;
                const active = i === currentIdx;
                return (
                    <div key={s} className="flex-1 flex flex-col items-center relative">
                        {i < STATUS_STEPS.length - 1 && (
                            <div className={`absolute top-3 left-1/2 w-full h-1 z-0 ${done && i < currentIdx ? "bg-blue-500" : "bg-gray-200"}`} />
                        )}
                        <div className={`w-6 h-6 rounded-full z-10 flex items-center justify-center text-xs font-bold border-2 transition-all ${active ? "bg-blue-600 border-blue-600 text-white scale-125 shadow-md" : done ? "bg-blue-500 border-blue-500 text-white" : "bg-white border-gray-300 text-gray-400"}`}>
                            {done && !active ? "✓" : i + 1}
                        </div>
                        <span className={`text-xs mt-1.5 font-medium text-center leading-tight max-w-[56px] ${active ? "text-blue-700" : done ? "text-blue-500" : "text-gray-400"}`}>
                            {STATUS_LABELS[s]}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}

function DetailPanel({ code, onClose }: { code: string; onClose: () => void }) {
    const [detail, setDetail] = useState<TicketDetail | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetch = async () => {
            try {
                const res = await publicApi.trackTicket(code);
                setDetail(res.data);
            } catch {
                toast.error("Failed to load ticket details.");
            } finally {
                setLoading(false);
            }
        };
        fetch();
    }, [code]);

    return (
        <motion.div
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 40 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="bg-white rounded-2xl border border-blue-100 shadow-xl p-6"
        >
            <div className="flex items-center justify-between mb-4">
                <span className="font-mono text-sm font-bold text-blue-700 bg-blue-50 px-3 py-1 rounded-lg">{code}</span>
                <button
                    onClick={onClose}
                    className="text-gray-400 hover:text-gray-700 transition-colors text-lg leading-none p-1"
                    aria-label="Close"
                >
                    ✕
                </button>
            </div>

            {loading ? (
                <div className="flex items-center justify-center py-10">
                    <div className="w-8 h-8 border-3 border-blue-400 border-t-transparent rounded-full animate-spin" />
                </div>
            ) : !detail ? (
                <p className="text-gray-400 text-sm text-center py-8">Could not load ticket details.</p>
            ) : (
                <div className="space-y-5">
                    <ProgressTracker status={detail.status} />
                    <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-gray-500">Current Status:</span>
                        <StatusBadge status={detail.status} />
                    </div>
                    <div className="bg-gray-50 rounded-xl p-4">
                        <p className="text-xs text-gray-400 mb-1">Issue Description</p>
                        <p className="text-sm text-gray-800 leading-relaxed">{detail.description}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div className="bg-gray-50 rounded-xl p-3">
                            <p className="text-xs text-gray-400 mb-0.5">Department</p>
                            <p className="text-sm font-medium text-gray-800">{DEPT_NAMES[detail.department] ?? detail.department}</p>
                        </div>
                        {detail.issue_category && (
                            <div className="bg-gray-50 rounded-xl p-3">
                                <p className="text-xs text-gray-400 mb-0.5">Category</p>
                                <p className="text-sm font-medium text-gray-800">{detail.issue_category}</p>
                            </div>
                        )}
                        <div className="bg-gray-50 rounded-xl p-3">
                            <p className="text-xs text-gray-400 mb-0.5">Submitted</p>
                            <p className="text-sm font-medium text-gray-800">{formatDate(detail.created_at)}</p>
                            <p className="text-xs text-gray-400">{formatRelative(detail.created_at)}</p>
                        </div>
                        {detail.sla_deadline && (
                            <div className="bg-blue-50 rounded-xl p-3">
                                <p className="text-xs text-blue-500 mb-0.5">Expected Resolution By</p>
                                <p className="text-sm font-semibold text-blue-800">{formatDate(detail.sla_deadline)}</p>
                            </div>
                        )}
                        {detail.location_text && (
                            <div className="bg-gray-50 rounded-xl p-3 col-span-2">
                                <p className="text-xs text-gray-400 mb-0.5">Location</p>
                                <p className="text-sm font-medium text-gray-800">{detail.location_text}</p>
                            </div>
                        )}
                    </div>
                    {detail.seasonal_alert && (
                        <div className="bg-orange-50 border border-orange-200 rounded-xl p-3 text-sm text-orange-800">
                            🌤️ <strong>Seasonal Alert:</strong> {detail.seasonal_alert}
                        </div>
                    )}
                    <div>
                        <p className="text-xs font-semibold text-gray-500 mb-3">📅 Activity Log</p>
                        <Timeline events={detail.timeline || [{ event: "CREATED", timestamp: detail.created_at, actor: "System (AI Pipeline)" }]} />
                        <p className="text-xs text-gray-400 mt-2 text-center italic">Only significant status changes are logged here</p>
                    </div>
                    {detail.work_verified !== undefined && detail.work_verified !== null && (
                        <div className={`rounded-2xl p-4 border-2 ${detail.work_verified ? "bg-emerald-50 border-emerald-300" : "bg-amber-50 border-amber-300"}`}>
                            <div className="flex items-center gap-3">
                                <span className="text-3xl">{detail.work_verified ? "✅" : "🔍"}</span>
                                <div className="flex-1">
                                    <p className={`font-extrabold text-sm ${detail.work_verified ? "text-emerald-700" : "text-amber-700"}`}>
                                        {detail.work_verified ? "AI-Verified Work Complete" : "Verification Pending Review"}
                                    </p>
                                    {detail.work_verification_explanation && (
                                        <p className="text-xs text-gray-600 mt-1 leading-snug">{detail.work_verification_explanation}</p>
                                    )}
                                </div>
                            </div>
                            {detail.after_photo_url && (
                                <div className="mt-3">
                                    <p className="text-xs font-semibold text-gray-500 mb-2">📷 Proof Photo</p>
                                    <img src={detail.after_photo_url} alt="Work proof" className="w-full max-h-48 object-cover rounded-xl border border-emerald-200" />
                                </div>
                            )}
                        </div>
                    )}
                    <NotificationTimeline ticketCode={detail.ticket_code} />
                    {detail.status === "CLOSED" && (
                        <button
                            onClick={() => window.open(`http://localhost:8001/api/v1/public/track/${detail.ticket_code}/apr`, "_blank")}
                            className="w-full text-center px-4 py-3 bg-emerald-600 text-white font-semibold rounded-xl hover:bg-emerald-700 transition-colors flex items-center justify-center gap-2"
                        >
                            📄 Download Resolution Report
                        </button>
                    )}
                </div>
            )}
        </motion.div>
    );
}

// ─── Withdrawal Modal ─────────────────────────────────────────────────────────

type WithdrawStep = "reason" | "confirm";

function WithdrawModal({
    ticket,
    onClose,
    onWithdrawn,
}: {
    ticket: Ticket;
    onClose: () => void;
    onWithdrawn: (code: string) => void;
}) {
    const [step, setStep] = useState<WithdrawStep>("reason");
    const [selectedReason, setSelectedReason] = useState<string>("");
    const [description, setDescription] = useState("");
    const [submitting, setSubmitting] = useState(false);

    const handleConfirm = async () => {
        setSubmitting(true);
        try {
            await publicApi.withdrawTicket(ticket.ticket_code, {
                withdrawal_reason: selectedReason,
                withdrawal_description: description.trim() || undefined,
            });
            toast.success("Complaint withdrawn successfully.");
            onWithdrawn(ticket.ticket_code);
            onClose();
        } catch (err: any) {
            const msg = err?.response?.data?.detail || "Failed to withdraw complaint.";
            toast.error(msg);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4">
            {/* Backdrop */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 bg-black/50 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Modal */}
            <motion.div
                initial={{ opacity: 0, y: 60, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 60, scale: 0.95 }}
                transition={{ type: "spring", stiffness: 400, damping: 35 }}
                className="relative w-full max-w-md bg-white rounded-3xl shadow-2xl overflow-hidden"
            >
                {/* Header */}
                <div className="bg-gradient-to-r from-rose-500 to-rose-600 px-6 py-5">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-rose-100 text-xs font-semibold mb-0.5 uppercase tracking-wide">Withdraw Complaint</p>
                            <p className="text-white font-mono font-bold text-sm">{ticket.ticket_code}</p>
                        </div>
                        <button onClick={onClose} className="text-rose-100 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/10">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                    <p className="text-rose-100/80 text-xs mt-2 line-clamp-2">{ticket.description}</p>
                </div>

                <div className="p-6">
                    <AnimatePresence mode="wait">
                        {step === "reason" && (
                            <motion.div key="reason" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} className="space-y-5">
                                <div>
                                    <p className="text-sm font-bold text-gray-800 mb-1">Why are you withdrawing this complaint?</p>
                                    <p className="text-xs text-gray-500">Select a reason to continue. This will be shared with the authorities.</p>
                                </div>

                                <div className="space-y-2">
                                    {Object.entries(WITHDRAWAL_REASONS).map(([key, label]) => (
                                        <button
                                            key={key}
                                            onClick={() => setSelectedReason(key)}
                                            className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-xl border-2 text-left transition-all ${
                                                selectedReason === key
                                                    ? "border-rose-400 bg-rose-50 text-rose-800"
                                                    : "border-gray-100 bg-gray-50 hover:border-gray-200 hover:bg-gray-100 text-gray-700"
                                            }`}
                                        >
                                            <span className="text-xl shrink-0">{WITHDRAWAL_ICONS[key]}</span>
                                            <span className="text-sm font-medium">{label}</span>
                                            {selectedReason === key && (
                                                <span className="ml-auto text-rose-500 shrink-0">
                                                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                                    </svg>
                                                </span>
                                            )}
                                        </button>
                                    ))}
                                </div>

                                {/* Optional comments */}
                                <div>
                                    <label className="text-xs font-semibold text-gray-600 block mb-1.5">Additional details (optional)</label>
                                    <textarea
                                        value={description}
                                        onChange={(e) => setDescription(e.target.value)}
                                        placeholder="e.g. The road was repaired yesterday by another team…"
                                        rows={3}
                                        maxLength={500}
                                        className="w-full text-sm border border-gray-200 rounded-xl px-3 py-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-rose-300 focus:border-rose-300 text-gray-700 placeholder-gray-400"
                                    />
                                    <p className="text-xs text-gray-400 text-right mt-1">{description.length}/500</p>
                                </div>

                                <button
                                    disabled={!selectedReason}
                                    onClick={() => setStep("confirm")}
                                    className="w-full py-3 bg-rose-500 hover:bg-rose-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all text-sm"
                                >
                                    Continue →
                                </button>
                            </motion.div>
                        )}

                        {step === "confirm" && (
                            <motion.div key="confirm" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-5">
                                <div className="text-center">
                                    <div className="w-16 h-16 bg-rose-100 rounded-full flex items-center justify-center mx-auto mb-3">
                                        <span className="text-3xl">🚫</span>
                                    </div>
                                    <p className="text-lg font-bold text-gray-800">Are you sure?</p>
                                    <p className="text-sm text-gray-500 mt-1">This complaint will be marked as withdrawn. The civic team will be notified.</p>
                                </div>

                                <div className="bg-gray-50 rounded-xl p-4 space-y-2">
                                    <div>
                                        <p className="text-xs text-gray-400 font-semibold uppercase tracking-wide">Reason</p>
                                        <p className="text-sm font-medium text-gray-800 mt-0.5 flex items-center gap-2">
                                            <span>{WITHDRAWAL_ICONS[selectedReason]}</span>
                                            {WITHDRAWAL_REASONS[selectedReason]}
                                        </p>
                                    </div>
                                    {description.trim() && (
                                        <div>
                                            <p className="text-xs text-gray-400 font-semibold uppercase tracking-wide mt-2">Your note</p>
                                            <p className="text-sm text-gray-700 mt-0.5 italic">&ldquo;{description}&rdquo;</p>
                                        </div>
                                    )}
                                </div>

                                <div className="flex gap-3">
                                    <button
                                        onClick={() => setStep("reason")}
                                        className="flex-1 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-xl transition-colors text-sm"
                                    >
                                        ← Go Back
                                    </button>
                                    <button
                                        onClick={handleConfirm}
                                        disabled={submitting}
                                        className="flex-1 py-3 bg-rose-500 hover:bg-rose-600 disabled:opacity-60 text-white font-semibold rounded-xl transition-colors text-sm flex items-center justify-center gap-2"
                                    >
                                        {submitting ? (
                                            <>
                                                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                                Withdrawing…
                                            </>
                                        ) : "Confirm Withdrawal"}
                                    </button>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </motion.div>
        </div>
    );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

const TERMINAL_STATUSES = ["CLOSED", "RESOLVED", "REJECTED", "WITHDRAWN"];

export default function MyTicketsPage() {
    const { user, token } = useAuth();
    const router = useRouter();
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedCode, setSelectedCode] = useState<string | null>(null);
    const [withdrawTicket, setWithdrawTicket] = useState<Ticket | null>(null);
    const [showWithdrawn, setShowWithdrawn] = useState(false);

    useEffect(() => {
        if (!token) {
            router.push("/user-login");
            return;
        }
        fetchTickets();
    }, [token]);

    const fetchTickets = async () => {
        try {
            const res = await publicApi.getMyTickets();
            setTickets(res.data);
        } catch (err: any) {
            if (err?.response?.status === 401) {
                router.push("/user-login");
                return;
            }
            toast.error("Failed to load your tickets.");
        } finally {
            setLoading(false);
        }
    };

    const handleWithdrawn = (code: string) => {
        setTickets(prev => prev.map(t =>
            t.ticket_code === code
                ? { ...t, status: "WITHDRAWN" }
                : t
        ));
        if (selectedCode === code) setSelectedCode(null);
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin" />
                    <p className="text-sm text-gray-500">Loading your tickets…</p>
                </div>
            </div>
        );
    }

    const activeTickets = tickets.filter(t => t.status !== "WITHDRAWN");
    const withdrawnTickets = tickets.filter(t => t.status === "WITHDRAWN");
    const openCount = activeTickets.filter(t => !["CLOSED", "RESOLVED"].includes(t.status)).length;
    const resolvedCount = activeTickets.filter(t => ["CLOSED", "RESOLVED"].includes(t.status)).length;

    const canWithdraw = (t: Ticket) => !TERMINAL_STATUSES.includes(t.status);

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
            {/* Header */}
            <section className="bg-gradient-to-br from-blue-700 via-blue-800 to-indigo-900 text-white py-10 px-4">
                <div className="max-w-5xl mx-auto">
                    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
                        <h1 className="text-3xl md:text-4xl font-extrabold mb-2">My Complaints</h1>
                        <p className="text-blue-200">
                            {user?.name ? `${user.name}'s` : "Your"} submitted complaints
                        </p>
                        <div className="flex gap-4 mt-5 flex-wrap">
                            <div className="bg-white/10 rounded-xl px-4 py-2.5 backdrop-blur-sm border border-white/20">
                                <p className="text-xs text-blue-200">Total</p>
                                <p className="text-2xl font-bold">{activeTickets.length}</p>
                            </div>
                            <div className="bg-white/10 rounded-xl px-4 py-2.5 backdrop-blur-sm border border-white/20">
                                <p className="text-xs text-blue-200">Active</p>
                                <p className="text-2xl font-bold">{openCount}</p>
                            </div>
                            <div className="bg-white/10 rounded-xl px-4 py-2.5 backdrop-blur-sm border border-white/20">
                                <p className="text-xs text-blue-200">Resolved</p>
                                <p className="text-2xl font-bold">{resolvedCount}</p>
                            </div>
                            {withdrawnTickets.length > 0 && (
                                <div className="bg-white/10 rounded-xl px-4 py-2.5 backdrop-blur-sm border border-white/20">
                                    <p className="text-xs text-blue-200">Withdrawn</p>
                                    <p className="text-2xl font-bold">{withdrawnTickets.length}</p>
                                </div>
                            )}
                        </div>
                    </motion.div>
                </div>
            </section>

            <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
                {activeTickets.length === 0 && withdrawnTickets.length === 0 ? (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="text-center py-20"
                    >
                        <div className="text-6xl mb-4">📭</div>
                        <h2 className="text-2xl font-bold text-gray-800 mb-2">No complaints yet</h2>
                        <p className="text-gray-500 mb-6">
                            You haven&apos;t submitted any complaints. Report a civic issue to get started!
                        </p>
                        <Link
                            href="/"
                            className="inline-flex items-center gap-2 bg-blue-600 text-white px-6 py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors shadow-md"
                        >
                            🚀 Submit a Complaint
                        </Link>
                    </motion.div>
                ) : (
                    <>
                        {/* Active Tickets */}
                        {activeTickets.length > 0 && (
                            <div>
                                <div className={`flex gap-6 ${selectedCode ? "flex-col lg:flex-row" : ""}`}>
                                    <div className={`space-y-3 ${selectedCode ? "lg:w-2/5 flex-shrink-0" : "w-full"}`}>
                                        {activeTickets.map((t, i) => {
                                            const isSelected = selectedCode === t.ticket_code;
                                            return (
                                                <motion.div
                                                    key={t.id}
                                                    initial={{ opacity: 0, y: 10 }}
                                                    animate={{ opacity: 1, y: 0 }}
                                                    transition={{ delay: i * 0.04 }}
                                                >
                                                    <div className={`bg-white rounded-2xl border transition-all p-5 group ${isSelected ? "border-blue-400 shadow-md ring-2 ring-blue-100" : "border-gray-100 shadow-sm hover:shadow-md"}`}>
                                                        {/* Ticket card header */}
                                                        <button
                                                            onClick={() => setSelectedCode(isSelected ? null : t.ticket_code)}
                                                            className="w-full text-left"
                                                        >
                                                            <div className="flex items-start justify-between mb-2">
                                                                <div>
                                                                    <span className="text-xs font-mono font-bold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-lg">
                                                                        {t.ticket_code}
                                                                    </span>
                                                                    <span className="text-xs text-gray-400 ml-3">
                                                                        {formatDate(t.created_at)}
                                                                    </span>
                                                                </div>
                                                                <StatusBadge status={t.status} />
                                                            </div>
                                                            <p className="text-sm text-gray-700 mb-2.5 line-clamp-2 group-hover:text-gray-900 transition-colors">
                                                                {t.description}
                                                            </p>
                                                            <div className="flex items-center gap-3 text-xs text-gray-500">
                                                                <span className="flex items-center gap-1">
                                                                    🏛️ {DEPT_NAMES[t.dept_id] ?? t.dept_id}
                                                                </span>
                                                                {t.issue_category && (
                                                                    <span className="flex items-center gap-1">
                                                                        🏷️ {t.issue_category}
                                                                    </span>
                                                                )}
                                                            </div>
                                                            <div className="mt-3 text-xs font-medium text-blue-500">
                                                                {isSelected ? "▲ Hide details" : "▼ View details"}
                                                            </div>
                                                        </button>

                                                        {/* Withdraw button */}
                                                        {canWithdraw(t) && (
                                                            <div className="mt-3 pt-3 border-t border-gray-100">
                                                                <button
                                                                    onClick={() => setWithdrawTicket(t)}
                                                                    className="text-xs font-semibold text-rose-500 hover:text-rose-700 hover:bg-rose-50 px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5"
                                                                >
                                                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                                                    </svg>
                                                                    Withdraw Complaint
                                                                </button>
                                                            </div>
                                                        )}
                                                    </div>
                                                </motion.div>
                                            );
                                        })}
                                    </div>

                                    <AnimatePresence>
                                        {selectedCode && (
                                            <div className="lg:flex-1 lg:min-w-0">
                                                <DetailPanel
                                                    key={selectedCode}
                                                    code={selectedCode}
                                                    onClose={() => setSelectedCode(null)}
                                                />
                                            </div>
                                        )}
                                    </AnimatePresence>
                                </div>
                            </div>
                        )}

                        {/* Withdrawn Tickets Section */}
                        {withdrawnTickets.length > 0 && (
                            <div>
                                <button
                                    onClick={() => setShowWithdrawn(v => !v)}
                                    className="flex items-center gap-2 text-sm font-semibold text-gray-500 hover:text-gray-800 transition-colors mb-4 group"
                                >
                                    <span className={`text-lg transition-transform ${showWithdrawn ? "rotate-90" : ""}`}>▶</span>
                                    <span>Withdrawn Complaints</span>
                                    <span className="bg-gray-200 text-gray-600 text-xs font-bold px-2 py-0.5 rounded-full">{withdrawnTickets.length}</span>
                                </button>

                                <AnimatePresence>
                                    {showWithdrawn && (
                                        <motion.div
                                            initial={{ opacity: 0, height: 0 }}
                                            animate={{ opacity: 1, height: "auto" }}
                                            exit={{ opacity: 0, height: 0 }}
                                            className="space-y-3 overflow-hidden"
                                        >
                                            {withdrawnTickets.map((t, i) => (
                                                <motion.div
                                                    key={t.id}
                                                    initial={{ opacity: 0, y: 8 }}
                                                    animate={{ opacity: 1, y: 0 }}
                                                    transition={{ delay: i * 0.05 }}
                                                    className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 opacity-80"
                                                >
                                                    <div className="flex items-start justify-between mb-2">
                                                        <div>
                                                            <span className="text-xs font-mono font-bold text-gray-500 bg-gray-100 px-2.5 py-1 rounded-lg">
                                                                {t.ticket_code}
                                                            </span>
                                                            <span className="text-xs text-gray-400 ml-3">{formatDate(t.created_at)}</span>
                                                        </div>
                                                        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full border border-gray-200">
                                                            🚫 Withdrawn
                                                        </span>
                                                    </div>
                                                    <p className="text-sm text-gray-500 mb-3 line-clamp-2">{t.description}</p>
                                                    {/* Withdrawal reason callout */}
                                                    <div className="bg-gray-50 border border-gray-100 rounded-xl p-3">
                                                        <p className="text-xs font-semibold text-gray-400 mb-1">You withdrew this complaint</p>
                                                        <p className="text-sm text-gray-700 flex items-center gap-2">
                                                            <span>{t.withdrawal_reason ? WITHDRAWAL_ICONS[t.withdrawal_reason] : "💬"}</span>
                                                            <span className="font-medium">{t.withdrawal_reason ? WITHDRAWAL_REASONS[t.withdrawal_reason] : "No reason provided"}</span>
                                                        </p>
                                                        {t.withdrawal_description && (
                                                            <p className="text-xs text-gray-500 mt-1.5 italic border-t border-gray-100 pt-1.5">
                                                                &ldquo;{t.withdrawal_description}&rdquo;
                                                            </p>
                                                        )}
                                                        {t.withdrawn_at && (
                                                            <p className="text-xs text-gray-400 mt-1.5">{formatRelative(t.withdrawn_at)}</p>
                                                        )}
                                                    </div>
                                                </motion.div>
                                            ))}
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* Withdraw Modal */}
            <AnimatePresence>
                {withdrawTicket && (
                    <WithdrawModal
                        ticket={withdrawTicket}
                        onClose={() => setWithdrawTicket(null)}
                        onWithdrawn={handleWithdrawn}
                    />
                )}
            </AnimatePresence>
        </div>
    );
}
