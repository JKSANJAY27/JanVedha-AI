"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { publicApi } from "@/lib/api";
import { formatDate } from "@/lib/formatters";
import { DEPT_NAMES } from "@/lib/constants";
import StatusBadge from "@/components/StatusBadge";
import { useRouter } from "next/navigation";

interface MyTicket {
    id: string;
    ticket_code: string;
    status: string;
    description: string;
    dept_id: string;
    issue_category: string | null;
    created_at: string;
    sla_deadline: string | null;
}

interface WardEntry {
    ward_id: number;
    ward_name?: string;
    score: number;
    resolved: number;
    total: number;
}

export default function CitizenDashboardPage() {
    const { user, isOfficer } = useAuth();
    const router = useRouter();

    const [tickets, setTickets] = useState<MyTicket[]>([]);
    const [leaderboard, setLeaderboard] = useState<WardEntry[]>([]);
    const [loading, setLoading] = useState(true);

    // Redirect if not logged in or if officer
    useEffect(() => {
        if (!user) {
            router.push("/user-login");
        } else if (isOfficer) {
            router.push("/officer/dashboard");
        }
    }, [user, isOfficer, router]);

    useEffect(() => {
        if (!user || isOfficer) return;

        const load = async () => {
            try {
                const [tickRes, lbRes] = await Promise.allSettled([
                    publicApi.getMyTickets(),
                    publicApi.getLeaderboard(),
                ]);
                if (tickRes.status === "fulfilled") setTickets(tickRes.value.data ?? []);
                if (lbRes.status === "fulfilled") setLeaderboard((lbRes.value.data ?? []).slice(0, 5));
            } catch { }
            finally { setLoading(false); }
        };
        load();
    }, [user, isOfficer]);

    if (!user || isOfficer) return null;

    const open = tickets.filter(t => !["CLOSED", "RESOLVED"].includes(t.status));
    const resolved = tickets.filter(t => ["CLOSED", "RESOLVED"].includes(t.status));
    const recent = [...tickets].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 3);
    const nextDeadline = open
        .filter(t => t.sla_deadline)
        .sort((a, b) => new Date(a.sla_deadline!).getTime() - new Date(b.sla_deadline!).getTime())[0];
    const activeDepts = [...new Set(open.map(t => t.dept_id))].filter(Boolean);

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <div className="flex items-center gap-2 text-gray-500 text-sm">
                    <div className="w-5 h-5 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
                    Loading your dashboard…
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white pt-8 pb-12">
            <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                className="max-w-5xl mx-auto px-4"
            >
                {/* Welcome strip */}
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-3xl font-extrabold text-gray-900">
                            Welcome back, {user?.name?.split(" ")[0] ?? "Citizen"} 👋
                        </h1>
                        <p className="text-gray-500 mt-1">Here's the latest on your civic complaints</p>
                    </div>
                    <div className="flex gap-3">
                        <Link
                            href="/"
                            className="text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 transition-colors px-5 py-2.5 rounded-xl shadow-sm"
                        >
                            + New Complaint
                        </Link>
                        <Link
                            href="/my-tickets"
                            className="text-sm font-semibold text-blue-600 bg-blue-50 border border-blue-100 hover:bg-blue-100 transition-colors px-4 py-2.5 rounded-xl"
                        >
                            All Complaints →
                        </Link>
                    </div>
                </div>

                {tickets.length === 0 ? (
                    <div className="bg-blue-50 border border-blue-100 rounded-3xl p-10 text-center text-gray-600 mb-6 shadow-sm">
                        <p className="text-4xl mb-4">📭</p>
                        <h3 className="text-lg font-bold text-gray-900 mb-2">You haven't submitted any complaints yet</h3>
                        <p className="max-w-md mx-auto mb-6">Contribute to improving your city by reporting civic issues like broken streetlights, potholes, or garbage accumulation.</p>
                        <Link
                            href="/"
                            className="inline-block text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 transition-colors px-6 py-3 rounded-xl shadow mx-auto"
                        >
                            Report an Issue Now
                        </Link>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                        {/* ── Col 1+2: My Complaints Overview ── */}
                        <div className="lg:col-span-2 space-y-6">

                            {/* Stat pills */}
                            <div className="grid grid-cols-3 gap-4">
                                {[
                                    { label: "Total Filed", value: tickets.length, color: "bg-indigo-50 text-indigo-700", border: "border-indigo-100" },
                                    { label: "Active", value: open.length, color: "bg-amber-50 text-amber-700", border: "border-amber-100" },
                                    { label: "Resolved", value: resolved.length, color: "bg-emerald-50 text-emerald-700", border: "border-emerald-100" },
                                ].map(s => (
                                    <div key={s.label} className={`rounded-2xl p-5 ${s.color} border ${s.border}`}>
                                        <p className="text-4xl font-extrabold mb-1">{s.value}</p>
                                        <p className="text-sm font-bold opacity-80">{s.label}</p>
                                    </div>
                                ))}
                            </div>

                            {/* Next expected resolution */}
                            {nextDeadline && (
                                <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-2xl p-6 text-white flex items-center gap-5 shadow-md">
                                    <div className="text-4xl">📅</div>
                                    <div>
                                        <p className="text-sm font-medium text-blue-200 mb-1">Your next pending issue is expected to be resolved by</p>
                                        <p className="text-2xl font-bold">{formatDate(nextDeadline.sla_deadline!)}</p>
                                        <p className="text-sm text-blue-300 mt-1 font-mono uppercase tracking-widest">{nextDeadline.ticket_code}</p>
                                    </div>
                                </div>
                            )}

                            {/* Departments handling your issues */}
                            {activeDepts.length > 0 && (
                                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                                    <h3 className="text-sm font-bold text-gray-900 mb-4 flex items-center gap-2">
                                        <span>🏛️</span> Departments Handling Your Active Issues
                                    </h3>
                                    <div className="flex flex-wrap gap-2.5">
                                        {activeDepts.map(deptId => (
                                            <span key={deptId} className="bg-gray-50 border border-gray-200 text-gray-700 text-sm font-semibold px-4 py-2 rounded-xl">
                                                {DEPT_NAMES[deptId] ?? deptId}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Recent activity */}
                            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                                <div className="flex items-center justify-between mb-5">
                                    <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                                        <span>🕒</span> Recent Complaints
                                    </h3>
                                    <Link href="/my-tickets" className="text-xs font-semibold text-blue-600 hover:text-blue-800 transition-colors">
                                        View all →
                                    </Link>
                                </div>
                                <div className="space-y-4">
                                    {recent.map(t => (
                                        <div key={t.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl border border-gray-50 hover:bg-gray-50 transition-colors">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-3 mb-1.5">
                                                    <span className="text-xs font-mono font-bold text-blue-700 bg-blue-50/50 px-2 py-0.5 rounded-md border border-blue-100">
                                                        {t.ticket_code}
                                                    </span>
                                                    <span className="text-xs text-gray-400 font-medium">Filed {formatDate(t.created_at)}</span>
                                                </div>
                                                <p className="text-sm font-medium text-gray-800 line-clamp-1">{t.description}</p>
                                            </div>
                                            <div className="shrink-0 self-start sm:self-center">
                                                <StatusBadge status={t.status} />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* ── Col 3: Ward Transparency ── */}
                        <div className="space-y-6">
                            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                                <h3 className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-2">
                                    <span>🏆</span> City Transparency Leaderboard
                                </h3>
                                <p className="text-xs text-gray-500 mb-5">Top performing wards ranked by issue resolution rate</p>

                                {leaderboard.length === 0 ? (
                                    <p className="text-sm text-gray-400 text-center py-4 bg-gray-50 rounded-xl">No public data available yet</p>
                                ) : (
                                    <div className="space-y-4">
                                        {leaderboard.map((w, i) => {
                                            const pct = w.total > 0 ? Math.round((w.resolved / w.total) * 100) : 0;
                                            return (
                                                <div key={w.ward_id}>
                                                    <div className="flex items-center justify-between text-sm mb-1.5">
                                                        <span className="font-semibold text-gray-700 flex items-center gap-2">
                                                            <span className={`w-5 h-5 rounded-full flex items-center justify-center text-white text-[11px] font-bold ${i === 0 ? "bg-yellow-400 shadow-sm" : i === 1 ? "bg-gray-400" : i === 2 ? "bg-amber-600" : "bg-blue-100 text-blue-700"}`}>{i + 1}</span>
                                                            {w.ward_name ?? `Ward ${w.ward_id}`}
                                                        </span>
                                                        <span className="font-bold text-gray-800">{pct}%</span>
                                                    </div>
                                                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                                        <div className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>

                            {/* Transparency info card */}
                            <div className="bg-slate-900 rounded-2xl p-6 text-white shadow-lg relative overflow-hidden">
                                <div className="absolute top-0 right-0 p-4 opacity-10 text-6xl">⚖️</div>
                                <h3 className="text-sm font-bold text-white mb-4 relative z-10 flex items-center gap-2">
                                    <span>ℹ️</span> Your Rights as a Citizen
                                </h3>
                                <ul className="text-sm text-slate-300 space-y-3 relative z-10">
                                    <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Track every complaint you file</li>
                                    <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Know which department handles it</li>
                                    <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> See expected resolution dates</li>
                                    <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Download a resolution report on close</li>
                                    <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> View ward-level performance publicly</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                )}
            </motion.div>
        </div>
    );
}
