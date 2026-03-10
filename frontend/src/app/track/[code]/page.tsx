"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { publicApi } from "@/lib/api";
import { formatDate, formatRelative } from "@/lib/formatters";
import StatusBadge from "@/components/StatusBadge";
import Timeline from "@/components/Timeline";
import { DEPT_NAMES } from "@/lib/constants";

interface TicketData {
    ticket_code: string;
    status: string;
    description: string;
    department: string;
    issue_category?: string;
    priority_label: string;
    priority_score: number;
    created_at: string;
    sla_deadline?: string;
    suggestions?: string[];
    seasonal_alert?: string;
    location_text?: string;
}

function SearchBar({ onSearch }: { onSearch: (code: string) => void }) {
    const [value, setValue] = useState("");
    return (
        <div className="flex gap-3 max-w-lg mx-auto">
            <input
                value={value}
                onChange={(e) => setValue(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === "Enter" && value && onSearch(value)}
                placeholder="Enter ticket code (e.g. CIV-2025-XXXXX)"
                className="flex-1 border-2 border-gray-200 rounded-2xl px-5 py-4 text-sm font-mono focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 bg-white shadow-sm placeholder:text-gray-400"
            />
            <button
                onClick={() => value && onSearch(value)}
                className="px-6 py-4 bg-blue-600 text-white font-semibold rounded-2xl hover:bg-blue-700 transition-colors shadow-sm"
            >
                Track →
            </button>
        </div>
    );
}

export default function TrackTicketPage() {
    const params = useParams();
    const codeFromUrl = params?.code as string | undefined;

    const [ticket, setTicket] = useState<TicketData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchTicket = async (code: string) => {
        setLoading(true);
        setError(null);
        try {
            const res = await publicApi.trackTicket(code.trim());
            setTicket(res.data);
        } catch (err: any) {
            const msg = err?.response?.status === 404 ? "Ticket not found. Please check the code." : "Failed to fetch ticket.";
            setError(msg);
            toast.error(msg);
            setTicket(null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (codeFromUrl) fetchTicket(codeFromUrl);
    }, [codeFromUrl]);

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
            {/* Header */}
            <section className="bg-gradient-to-br from-indigo-700 to-blue-800 text-white py-12 px-4">
                <div className="max-w-3xl mx-auto text-center">
                    <h1 className="text-3xl md:text-4xl font-extrabold mb-3">Track Your Complaint</h1>
                    <p className="text-blue-200 mb-8">Enter your ticket code to see real-time status and updates</p>
                    <SearchBar onSearch={fetchTicket} />
                </div>
            </section>

            <div className="max-w-3xl mx-auto px-4 py-10">
                {loading && (
                    <div className="text-center py-20">
                        <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4" />
                        <p className="text-gray-500">Fetching your ticket...</p>
                    </div>
                )}

                {error && !loading && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="text-center py-16"
                    >
                        <div className="text-5xl mb-4">🔍</div>
                        <h3 className="text-xl font-bold text-gray-800 mb-2">Ticket Not Found</h3>
                        <p className="text-gray-500">{error}</p>
                    </motion.div>
                )}

                {!loading && !error && !ticket && !codeFromUrl && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="text-center py-20 text-gray-400"
                    >
                        <div className="text-6xl mb-4">📋</div>
                        <p className="text-lg">Enter a ticket code above to get started</p>
                    </motion.div>
                )}

                {ticket && !loading && (
                    <AnimatePresence>
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="space-y-5"
                        >
                            {/* Main card */}
                            <div className="bg-white rounded-3xl shadow-xl p-6 border border-gray-100">
                                {/* Header row */}
                                <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
                                    <div>
                                        <p className="text-xs text-gray-400 mb-0.5">Ticket Code</p>
                                        <p className="text-2xl font-mono font-bold text-blue-700">{ticket.ticket_code}</p>
                                    </div>
                                    <StatusBadge status={ticket.status} />
                                </div>

                                {/* Details grid */}
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
                                    <div className="bg-gray-50 rounded-2xl p-4">
                                        <p className="text-xs text-gray-400 mb-1">Issue Description</p>
                                        <p className="text-sm text-gray-800 leading-relaxed">{ticket.description}</p>
                                    </div>
                                    <div className="space-y-3">
                                        <div className="bg-gray-50 rounded-xl p-3">
                                            <p className="text-xs text-gray-400 mb-0.5">Department</p>
                                            <p className="text-sm font-medium text-gray-800">
                                                {DEPT_NAMES[ticket.department] ?? ticket.department}
                                            </p>
                                        </div>
                                        {ticket.issue_category && (
                                            <div className="bg-gray-50 rounded-xl p-3">
                                                <p className="text-xs text-gray-400 mb-0.5">Category</p>
                                                <p className="text-sm font-medium text-gray-800">{ticket.issue_category}</p>
                                            </div>
                                        )}
                                        <div className="bg-gray-50 rounded-xl p-3">
                                            <p className="text-xs text-gray-400 mb-0.5">Submitted</p>
                                            <p className="text-sm font-medium text-gray-800">{formatDate(ticket.created_at)}</p>
                                            <p className="text-xs text-gray-400">{formatRelative(ticket.created_at)}</p>
                                        </div>
                                        {ticket.sla_deadline && (
                                            <div className="bg-blue-50 rounded-xl p-3">
                                                <p className="text-xs text-blue-500 mb-0.5">Expected Resolution By</p>
                                                <p className="text-sm font-semibold text-blue-800">{formatDate(ticket.sla_deadline)}</p>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Seasonal alert */}
                                {ticket.seasonal_alert && (
                                    <div className="bg-orange-50 border border-orange-200 rounded-xl p-3 text-sm text-orange-800">
                                        🌤️ <strong>Seasonal Alert:</strong> {ticket.seasonal_alert}
                                    </div>
                                )}
                            </div>

                            {/* Actions card (if closed) */}
                            {ticket.status === "CLOSED" && (
                                <div className="bg-emerald-50 rounded-3xl shadow-sm p-6 border border-emerald-100 flex flex-col sm:flex-row items-center justify-between gap-4">
                                    <div>
                                        <h3 className="font-bold text-emerald-900 flex items-center gap-2">
                                            <span>✅</span> Issue Resolved
                                        </h3>
                                        <p className="text-sm text-emerald-700 mt-1">
                                            This complaint has been closed. You can view the final verified report below.
                                        </p>
                                    </div>
                                    <button
                                        onClick={() => window.open(`http://localhost:8001/api/v1/public/track/${ticket.ticket_code}/apr`, '_blank')}
                                        className="whitespace-nowrap px-6 py-3 bg-emerald-600 text-white font-semibold rounded-xl hover:bg-emerald-700 transition-colors shadow-sm flex items-center gap-2"
                                    >
                                        📄 Download Final Report
                                    </button>
                                </div>
                            )}

                            {/* Timeline card */}
                            <div className="bg-white rounded-3xl shadow-xl p-6 border border-gray-100">
                                <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                                    <span className="text-blue-600">📅</span> Status Timeline
                                </h3>
                                <Timeline
                                    events={[
                                        {
                                            event: "CREATED",
                                            timestamp: ticket.created_at,
                                            actor: "System (AI Pipeline)",
                                        },
                                    ]}
                                />
                                <p className="text-xs text-gray-400 mt-3 text-center">
                                    Full timeline visible to your ward officer
                                </p>
                            </div>
                        </motion.div>
                    </AnimatePresence>
                )}

            </div>
        </div>
    );
}
