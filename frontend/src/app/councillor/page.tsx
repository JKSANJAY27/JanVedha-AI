"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";
import { councillorApi } from "@/lib/api";
import { DEPT_NAMES } from "@/lib/constants";

interface WardSummary {
    ward_id: number;
    total: number;
    open: number;
    closed: number;
    overdue: number;
    resolution_rate: number;
    avg_resolution_days: number;
    avg_satisfaction: number | null;
}

interface DeptPerf {
    dept_id: string;
    total: number;
    open: number;
    closed: number;
    overdue: number;
}

interface WeekData {
    week_label: string;
    avg_satisfaction: number | null;
    ticket_count: number;
}

interface TopIssue {
    category: string;
    count: number;
    percentage: number;
}

interface OverdueTicket {
    id: string;
    ticket_code: string;
    dept_id: string;
    issue_category: string;
    priority_label: string;
    days_overdue: number;
    status: string;
}

const KPI_COLORS = ["blue", "green", "red", "orange", "purple"];

function KpiCard({ label, value, sub, icon, color }: { label: string; value: string | number; sub?: string; icon: string; color: string }) {
    const colorMap: Record<string, string> = {
        blue: "from-blue-500 to-indigo-600",
        green: "from-emerald-500 to-green-600",
        red: "from-red-500 to-rose-600",
        orange: "from-orange-400 to-amber-500",
        purple: "from-purple-500 to-violet-600",
    };
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`bg-gradient-to-br ${colorMap[color]} text-white rounded-2xl p-5 shadow-sm`}
        >
            <div className="flex items-center justify-between">
                <p className="text-sm font-medium opacity-90">{label}</p>
                <span className="text-2xl">{icon}</span>
            </div>
            <p className="text-3xl font-bold mt-2">{value}</p>
            {sub && <p className="text-xs mt-1 opacity-75">{sub}</p>}
        </motion.div>
    );
}

// Simple inline SVG satisfaction trend chart
function SatisfactionChart({ data }: { data: WeekData[] }) {
    const validData = data.filter(d => d.avg_satisfaction !== null);
    if (validData.length < 2) {
        return (
            <div className="h-32 flex items-center justify-center text-gray-400 text-sm italic">
                Not enough data yet
            </div>
        );
    }
    const max = 5, min = 1;
    const W = 500, H = 100, pad = 20;
    const xStep = (W - pad * 2) / (validData.length - 1);
    const yScale = (v: number) => H - pad - ((v - min) / (max - min)) * (H - pad * 2);
    const points = validData.map((d, i) => `${pad + i * xStep},${yScale(d.avg_satisfaction!)}`)
        .join(" ");

    return (
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-28" preserveAspectRatio="none">
            <polyline points={points} fill="none" stroke="#6366f1" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            {validData.map((d, i) => (
                <g key={i}>
                    <circle cx={pad + i * xStep} cy={yScale(d.avg_satisfaction!)} r="4" fill="#6366f1" />
                    <text x={pad + i * xStep} y={H - 2} textAnchor="middle" fontSize="8" fill="#9ca3af">{d.week_label}</text>
                </g>
            ))}
        </svg>
    );
}

export default function CouncillorDashboard() {
    const { user, isCouncillor, isAdmin, isSupervisor } = useAuth();
    const router = useRouter();

    const [summary, setSummary] = useState<WardSummary | null>(null);
    const [deptPerf, setDeptPerf] = useState<DeptPerf[]>([]);
    const [trend, setTrend] = useState<WeekData[]>([]);
    const [topIssues, setTopIssues] = useState<TopIssue[]>([]);
    const [overdue, setOverdue] = useState<OverdueTicket[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const allowed = isCouncillor || isAdmin || isSupervisor;
        if (!user) return;
        if (!allowed) { router.push("/officer/dashboard"); return; }

        const ward = user.ward_id;
        Promise.all([
            councillorApi.getWardSummary(ward),
            councillorApi.getDeptPerformance(ward),
            councillorApi.getSatisfactionTrend(ward, 8),
            councillorApi.getTopIssues(ward, 8),
            councillorApi.getOverdueTickets(ward),
        ]).then(([s, d, t, issues, ov]) => {
            setSummary(s.data);
            setDeptPerf(d.data);
            setTrend(t.data);
            setTopIssues(issues.data);
            setOverdue(ov.data);
        }).catch(() => toast.error("Failed to load ward data"))
            .finally(() => setLoading(false));
    }, [user]);

    const PRIORITY_COLORS: Record<string, string> = {
        CRITICAL: "bg-red-100 text-red-700",
        HIGH: "bg-orange-100 text-orange-700",
        MEDIUM: "bg-yellow-100 text-yellow-700",
        LOW: "bg-green-100 text-green-700",
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-center">
                    <div className="w-14 h-14 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-gray-500 font-medium">Loading ward insights…</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50">
            {/* Header */}
            <div className="bg-gradient-to-r from-emerald-700 to-teal-800 text-white px-6 py-6">
                <div className="max-w-7xl mx-auto">
                    <p className="text-emerald-300 text-sm">Councillor · Ward {user?.ward_id}</p>
                    <h1 className="text-2xl font-bold mt-0.5">Ward {user?.ward_id} — Insights Dashboard 🏛️</h1>
                    <p className="text-emerald-200 text-xs mt-1">Read-only visibility into your ward's civic performance</p>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">
                {/* KPI Cards */}
                {summary && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                        <KpiCard label="Total Tickets" value={summary.total} icon="📋" color="blue" />
                        <KpiCard label="Open" value={summary.open} icon="⚡" color="orange" />
                        <KpiCard label="Resolved" value={summary.closed} icon="✅" color="green" sub={`${summary.resolution_rate}% rate`} />
                        <KpiCard label="Overdue" value={summary.overdue} icon="⚠️" color="red" />
                        <KpiCard
                            label="Avg Satisfaction"
                            value={summary.avg_satisfaction !== null ? `${summary.avg_satisfaction}/5` : "N/A"}
                            icon="⭐"
                            color="purple"
                            sub={`Avg ${summary.avg_resolution_days} days to resolve`}
                        />
                    </div>
                )}

                {/* Middle row: Dept Performance + Satisfaction Trend */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Department Performance Table */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                            <span className="text-xl">🏢</span>
                            <h2 className="font-bold text-gray-800 text-sm">Department Performance</h2>
                            <span className="ml-auto text-xs text-gray-400">Sorted by overdue</span>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="bg-gray-50 border-b border-gray-100">
                                        <th className="text-left px-4 py-2.5 text-xs text-gray-500 font-semibold">Department</th>
                                        <th className="text-center px-4 py-2.5 text-xs text-gray-500 font-semibold">Open</th>
                                        <th className="text-center px-4 py-2.5 text-xs text-gray-500 font-semibold">Closed</th>
                                        <th className="text-center px-4 py-2.5 text-xs text-gray-500 font-semibold">Overdue</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-50">
                                    {deptPerf.length === 0 ? (
                                        <tr><td colSpan={4} className="text-center py-8 text-gray-400 text-xs italic">No data</td></tr>
                                    ) : (
                                        deptPerf.map((d, i) => (
                                            <motion.tr
                                                key={d.dept_id}
                                                initial={{ opacity: 0, x: -10 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: i * 0.04 }}
                                                className="hover:bg-gray-50 transition-colors"
                                            >
                                                <td className="px-4 py-3 font-medium text-gray-800 text-xs">
                                                    {DEPT_NAMES[d.dept_id] ?? d.dept_id}
                                                </td>
                                                <td className="px-4 py-3 text-center">
                                                    <span className="bg-orange-100 text-orange-700 text-xs font-bold px-2 py-0.5 rounded-full">{d.open}</span>
                                                </td>
                                                <td className="px-4 py-3 text-center">
                                                    <span className="bg-green-100 text-green-700 text-xs font-bold px-2 py-0.5 rounded-full">{d.closed}</span>
                                                </td>
                                                <td className="px-4 py-3 text-center">
                                                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${d.overdue > 0 ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-500"}`}>
                                                        {d.overdue}
                                                    </span>
                                                </td>
                                            </motion.tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Satisfaction Trend */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                        <div className="flex items-center gap-2 mb-4">
                            <span className="text-xl">📈</span>
                            <h2 className="font-bold text-gray-800 text-sm">Satisfaction Trend (8 weeks)</h2>
                        </div>
                        <SatisfactionChart data={trend} />
                        <div className="mt-3 flex gap-4 flex-wrap">
                            {trend.slice(-3).map(w => (
                                <div key={w.week_label} className="text-center">
                                    <p className="text-xs text-gray-500">{w.week_label}</p>
                                    <p className="font-bold text-indigo-700 text-sm">
                                        {w.avg_satisfaction !== null ? `${w.avg_satisfaction}/5` : "—"}
                                    </p>
                                    <p className="text-[10px] text-gray-400">{w.ticket_count} tickets</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Bottom row: Top Issues + Overdue List */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Top Issues */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                        <div className="flex items-center gap-2 mb-4">
                            <span className="text-xl">🔥</span>
                            <h2 className="font-bold text-gray-800 text-sm">Top Issue Categories</h2>
                        </div>
                        <div className="space-y-3">
                            {topIssues.length === 0 ? (
                                <p className="text-gray-400 text-sm italic text-center py-4">No data</p>
                            ) : (
                                topIssues.map((issue, i) => (
                                    <div key={issue.category}>
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="text-sm text-gray-700 font-medium">{issue.category}</span>
                                            <span className="text-xs font-bold text-gray-600">{issue.count} ({issue.percentage}%)</span>
                                        </div>
                                        <div className="w-full bg-gray-100 rounded-full h-2">
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: `${issue.percentage}%` }}
                                                transition={{ delay: i * 0.07, duration: 0.6, ease: "easeOut" }}
                                                className="h-2 rounded-full bg-gradient-to-r from-indigo-400 to-blue-500"
                                            />
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Overdue Tickets */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                            <span className="text-xl">⚠️</span>
                            <h2 className="font-bold text-gray-800 text-sm">Overdue Tickets</h2>
                            {overdue.length > 0 && (
                                <span className="ml-auto text-xs bg-red-100 text-red-700 font-bold px-2 py-0.5 rounded-full">{overdue.length} overdue</span>
                            )}
                        </div>
                        <div className="divide-y divide-gray-50 max-h-72 overflow-y-auto">
                            {overdue.length === 0 ? (
                                <div className="py-10 text-center">
                                    <p className="text-3xl mb-2">🎉</p>
                                    <p className="text-gray-400 text-sm">No overdue tickets!</p>
                                </div>
                            ) : (
                                overdue.map(t => (
                                    <div key={t.id} className="px-4 py-3 flex items-center justify-between gap-3">
                                        <div className="flex-1 min-w-0">
                                            <p className="font-mono text-xs font-bold text-indigo-700">{t.ticket_code}</p>
                                            <p className="text-xs text-gray-700 truncate">{t.issue_category}</p>
                                            <p className="text-[10px] text-gray-400 mt-0.5">{DEPT_NAMES[t.dept_id] ?? t.dept_id}</p>
                                        </div>
                                        <div className="text-right shrink-0">
                                            <span className={`text-xs font-bold px-1.5 py-0.5 rounded-full ${PRIORITY_COLORS[t.priority_label] ?? "bg-gray-100 text-gray-600"}`}>
                                                {t.priority_label}
                                            </span>
                                            <p className="text-[10px] text-red-600 font-bold mt-1">{t.days_overdue}d overdue</p>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
