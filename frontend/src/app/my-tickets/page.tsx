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
}

const STATUS_STEPS = ["OPEN", "IN_REVIEW", "IN_PROGRESS", "RESOLVED", "CLOSED"];
const STATUS_LABELS: Record<string, string> = {
    OPEN: "Submitted",
    IN_REVIEW: "Under Review",
    IN_PROGRESS: "Work Started",
    RESOLVED: "Resolved",
    CLOSED: "Closed",
};

function ProgressTracker({ status }: { status: string }) {
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
            {/* Panel header */}
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
                    {/* Status progress */}
                    <ProgressTracker status={detail.status} />

                    {/* Status + badge */}
                    <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-gray-500">Current Status:</span>
                        <StatusBadge status={detail.status} />
                    </div>

                    {/* Description */}
                    <div className="bg-gray-50 rounded-xl p-4">
                        <p className="text-xs text-gray-400 mb-1">Issue Description</p>
                        <p className="text-sm text-gray-800 leading-relaxed">{detail.description}</p>
                    </div>

                    {/* Meta grid */}
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

                    {/* Seasonal alert */}
                    {detail.seasonal_alert && (
                        <div className="bg-orange-50 border border-orange-200 rounded-xl p-3 text-sm text-orange-800">
                            🌤️ <strong>Seasonal Alert:</strong> {detail.seasonal_alert}
                        </div>
                    )}

                    {/* Timeline (simple) */}
                    <div>
                        <p className="text-xs font-semibold text-gray-500 mb-3">📅 Activity Log</p>
                        <Timeline events={[{ event: "CREATED", timestamp: detail.created_at, actor: "System (AI Pipeline)" }]} />
                        <p className="text-xs text-gray-400 mt-2 text-center">Full timeline visible to your ward officer</p>
                    </div>

                    {/* Closed: download report */}
                    {detail.status === "CLOSED" && (
                        <button
                            onClick={() => window.open(`http://localhost:8000/api/v1/public/track/${detail.ticket_code}/apr`, "_blank")}
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

export default function MyTicketsPage() {
    const { user, token } = useAuth();
    const router = useRouter();
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedCode, setSelectedCode] = useState<string | null>(null);

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

    const openCount = tickets.filter(t => !["CLOSED", "RESOLVED"].includes(t.status)).length;
    const resolvedCount = tickets.filter(t => ["CLOSED", "RESOLVED"].includes(t.status)).length;

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
                        {/* Quick stats strip */}
                        <div className="flex gap-6 mt-5">
                            <div className="bg-white/10 rounded-xl px-4 py-2.5 backdrop-blur-sm border border-white/20">
                                <p className="text-xs text-blue-200">Total</p>
                                <p className="text-2xl font-bold">{tickets.length}</p>
                            </div>
                            <div className="bg-white/10 rounded-xl px-4 py-2.5 backdrop-blur-sm border border-white/20">
                                <p className="text-xs text-blue-200">Active</p>
                                <p className="text-2xl font-bold">{openCount}</p>
                            </div>
                            <div className="bg-white/10 rounded-xl px-4 py-2.5 backdrop-blur-sm border border-white/20">
                                <p className="text-xs text-blue-200">Resolved</p>
                                <p className="text-2xl font-bold">{resolvedCount}</p>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </section>

            <div className="max-w-5xl mx-auto px-4 py-8">
                {tickets.length === 0 ? (
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
                    <div className={`flex gap-6 ${selectedCode ? "flex-col lg:flex-row" : ""}`}>
                        {/* Ticket List */}
                        <div className={`space-y-3 ${selectedCode ? "lg:w-2/5 flex-shrink-0" : "w-full"}`}>
                            {tickets.map((t, i) => {
                                const isSelected = selectedCode === t.ticket_code;
                                return (
                                    <motion.div
                                        key={t.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: i * 0.04 }}
                                    >
                                        <button
                                            onClick={() => setSelectedCode(isSelected ? null : t.ticket_code)}
                                            className={`w-full text-left bg-white rounded-2xl border transition-all p-5 cursor-pointer group ${isSelected ? "border-blue-400 shadow-md ring-2 ring-blue-100" : "border-gray-100 shadow-sm hover:shadow-md"}`}
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
                                    </motion.div>
                                );
                            })}
                        </div>

                        {/* Detail Panel */}
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
                )}
            </div>
        </div>
    );
}
