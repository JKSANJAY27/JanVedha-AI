"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { publicApi } from "@/lib/api";
import { formatDate } from "@/lib/formatters";
import PriorityBadge from "@/components/PriorityBadge";
import StatusBadge from "@/components/StatusBadge";
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

export default function MyTicketsPage() {
    const { user, token } = useAuth();
    const router = useRouter();
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);

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

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
            {/* Header */}
            <section className="bg-gradient-to-br from-blue-700 via-blue-800 to-indigo-900 text-white py-10 px-4">
                <div className="max-w-4xl mx-auto">
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                    >
                        <h1 className="text-3xl md:text-4xl font-extrabold mb-2">
                            My Tickets
                        </h1>
                        <p className="text-blue-200">
                            {user?.name ? `${user.name}'s` : "Your"} submitted complaints
                            &nbsp;·&nbsp; {tickets.length} total
                        </p>
                    </motion.div>
                </div>
            </section>

            <div className="max-w-4xl mx-auto px-4 py-8">
                {tickets.length === 0 ? (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="text-center py-20"
                    >
                        <div className="text-6xl mb-4">📭</div>
                        <h2 className="text-2xl font-bold text-gray-800 mb-2">
                            No tickets yet
                        </h2>
                        <p className="text-gray-500 mb-6">
                            You haven&apos;t submitted any complaints. Report a civic
                            issue to get started!
                        </p>
                        <Link
                            href="/"
                            className="inline-flex items-center gap-2 bg-blue-600 text-white px-6 py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors shadow-md"
                        >
                            🚀 Submit a Complaint
                        </Link>
                    </motion.div>
                ) : (
                    <div className="space-y-4">
                        {tickets.map((t, i) => (
                            <motion.div
                                key={t.id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: i * 0.05 }}
                            >
                                <Link href={`/track/${t.ticket_code}`}>
                                    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-all p-5 cursor-pointer group">
                                        <div className="flex items-start justify-between mb-3">
                                            <div>
                                                <span className="text-xs font-mono font-bold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-lg">
                                                    {t.ticket_code}
                                                </span>
                                                <span className="text-xs text-gray-400 ml-3">
                                                    {formatDate(t.created_at)}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <PriorityBadge
                                                    label={t.priority_label}
                                                    score={t.priority_score}
                                                />
                                                <StatusBadge status={t.status} />
                                            </div>
                                        </div>

                                        <p className="text-sm text-gray-700 mb-3 line-clamp-2 group-hover:text-gray-900 transition-colors">
                                            {t.description}
                                        </p>

                                        <div className="flex items-center gap-4 text-xs text-gray-500">
                                            <span className="flex items-center gap-1">
                                                🏛️{" "}
                                                {DEPT_NAMES[t.dept_id] ?? t.dept_id}
                                            </span>
                                            {t.issue_category && (
                                                <span className="flex items-center gap-1">
                                                    🏷️ {t.issue_category}
                                                </span>
                                            )}
                                            {t.location_text && (
                                                <span className="flex items-center gap-1">
                                                    📍 {t.location_text.substring(0, 40)}
                                                    {t.location_text.length > 40 ? "…" : ""}
                                                </span>
                                            )}
                                            {t.sla_deadline && (
                                                <span className="flex items-center gap-1">
                                                    ⏰ SLA: {formatDate(t.sla_deadline)}
                                                </span>
                                            )}
                                        </div>

                                        <div className="mt-3 text-xs text-blue-500 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                                            View details →
                                        </div>
                                    </div>
                                </Link>
                            </motion.div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
