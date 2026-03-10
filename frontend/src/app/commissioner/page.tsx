"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";
import { commissionerApi } from "@/lib/api";
import { DEPT_NAMES } from "@/lib/constants";

interface CitySummary {
    total_tickets: number;
    open: number;
    closed: number;
    overdue: number;
    resolution_rate: number;
    avg_resolution_days: number;
    avg_satisfaction: number | null;
    total_estimated_budget: number;
    total_spent_budget: number;
}

interface WardPerf {
    ward_id: number;
    total: number;
    open: number;
    closed: number;
    overdue: number;
    budget_spent: number;
}

interface WeekData {
    week_label: string;
    budget_spent: number;
    resolved_tickets: number;
}

interface CriticalTicket {
    id: string;
    ticket_code: string;
    ward_id: number;
    dept_id: string;
    issue_category: string;
    priority_score: number;
    days_overdue: number;
    estimated_cost: number | null;
}

const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumSignificantDigits: 3 }).format(amount);
};

function KpiCard({ label, value, sub, icon, color }: { label: string; value: string | number; sub?: string; icon: string; color: string }) {
    const colorMap: Record<string, string> = {
        blue: "from-blue-500 to-indigo-600",
        green: "from-emerald-500 to-green-600",
        red: "from-red-500 to-rose-600",
        orange: "from-orange-400 to-amber-500",
        purple: "from-purple-500 to-violet-600",
        slate: "from-slate-700 to-slate-900",
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

// Simple inline SVG budget burn rate chart (Bar chart)
function BudgetBurnChart({ data }: { data: WeekData[] }) {
    if (data.length === 0) {
        return (
            <div className="h-32 flex items-center justify-center text-gray-400 text-sm italic">
                No budget data yet
            </div>
        );
    }
    const maxVal = Math.max(...data.map(d => d.budget_spent), 100);
    const W = 500, H = 150, pad = 20;
    const barWidth = ((W - pad * 2) / data.length) * 0.6;
    const xStep = (W - pad * 2) / data.length;

    const yScale = (v: number) => H - pad - ((v / maxVal) * (H - pad * 2));

    return (
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-40" preserveAspectRatio="none">
            {/* Grid lines */}
            {[0, 0.5, 1].map(mult => (
                <line
                    key={mult}
                    x1={pad} y1={yScale(maxVal * mult)}
                    x2={W - pad} y2={yScale(maxVal * mult)}
                    stroke="#e5e7eb" strokeWidth="1" strokeDasharray="4 4"
                />
            ))}

            {data.map((d, i) => {
                const x = pad + (i * xStep) + (xStep - barWidth) / 2;
                const y = yScale(d.budget_spent);
                const height = H - pad - y;
                return (
                    <g key={i}>
                        <rect
                            x={x} y={y}
                            width={barWidth} height={height}
                            fill="url(#budgetGrad)" rx="2"
                        />
                        <text x={x + barWidth / 2} y={H - 5} textAnchor="middle" fontSize="10" fill="#9ca3af">
                            {d.week_label.split(" ")[0]}
                        </text>
                        {d.budget_spent > 0 && (
                            <text x={x + barWidth / 2} y={y - 5} textAnchor="middle" fontSize="8" fill="#6b7280" fontWeight="bold">
                                {formatCurrency(d.budget_spent).replace(/\.00$/, '')}
                            </text>
                        )}
                    </g>
                );
            })}
            <defs>
                <linearGradient id="budgetGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" />
                    <stop offset="100%" stopColor="#818cf8" stopOpacity="0.8" />
                </linearGradient>
            </defs>
        </svg>
    );
}

export default function CommissionerDashboard() {
    const { user, isCommissioner } = useAuth();
    const router = useRouter();

    const [summary, setSummary] = useState<CitySummary | null>(null);
    const [wardPerf, setWardPerf] = useState<WardPerf[]>([]);
    const [burnRate, setBurnRate] = useState<WeekData[]>([]);
    const [criticalTickets, setCriticalTickets] = useState<CriticalTicket[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!user) return;
        if (!isCommissioner) { router.push("/login"); return; }

        Promise.all([
            commissionerApi.getCitySummary(),
            commissionerApi.getWardPerformance(),
            commissionerApi.getBudgetBurnRate(10),
            commissionerApi.getCriticalOpenTickets(20),
        ]).then(([s, wp, br, ct]) => {
            setSummary(s.data);
            setWardPerf(wp.data);
            setBurnRate(br.data);
            setCriticalTickets(ct.data);
        }).catch(() => toast.error("Failed to load city data"))
            .finally(() => setLoading(false));
    }, [user, isCommissioner, router]);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-center">
                    <div className="w-14 h-14 border-4 border-slate-200 border-t-slate-800 rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-gray-500 font-medium">Loading HQ insights…</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50">
            {/* Header */}
            <div className="bg-slate-900 text-white px-6 py-6">
                <div className="max-w-7xl mx-auto">
                    <p className="text-slate-400 text-sm uppercase tracking-wider font-semibold">HQ Command Center</p>
                    <h1 className="text-3xl font-bold mt-1 tracking-tight">Commissioner Dashboard 🏙️</h1>
                    <p className="text-slate-300 text-sm mt-1">City-wide systems health, budget oversight, and critical alerts</p>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">
                {/* KPI Cards */}
                {summary && (
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                        <KpiCard label="Total Tickets" value={summary.total_tickets} icon="📋" color="blue" />
                        <KpiCard label="Resolved" value={summary.closed} icon="✅" color="green" sub={`${summary.resolution_rate}% overall`} />
                        <KpiCard label="City Overdue" value={summary.overdue} icon="⚠️" color="red" />
                        <KpiCard
                            label="Avg Sat."
                            value={summary.avg_satisfaction !== null ? `${summary.avg_satisfaction}/5` : "N/A"}
                            icon="⭐"
                            color="purple"
                            sub={`Avg ${summary.avg_resolution_days} days/res`}
                        />
                        <div className="col-span-2">
                            <KpiCard
                                label="Budget Spent (Est.)"
                                value={formatCurrency(summary.total_spent_budget)}
                                icon="₹"
                                color="slate"
                                sub={`Tracking ₹${formatCurrency(summary.total_estimated_budget)} total projected`}
                            />
                        </div>
                    </div>
                )}

                {/* Middle row: Burn Rate + Critical Issues */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Burn Rate */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex flex-col">
                        <div className="flex items-center gap-2 mb-4">
                            <span className="text-xl">📊</span>
                            <h2 className="font-bold text-gray-800 text-lg tracking-tight">Budget Burn Rate</h2>
                            <span className="ml-auto text-xs font-semibold text-slate-500 uppercase tracking-wider">Trailing 10 Weeks</span>
                        </div>
                        <div className="flex-1 flex items-end">
                            <BudgetBurnChart data={burnRate} />
                        </div>
                    </div>

                    {/* Critical Tickets */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
                        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2 bg-red-50/50">
                            <span className="text-xl">🚨</span>
                            <h2 className="font-bold text-red-900 text-lg tracking-tight">Critical Open Tickets Layer</h2>
                            <span className="ml-auto text-xs bg-red-100 text-red-700 font-bold px-2 py-0.5 rounded-full">{criticalTickets.length} critical</span>
                        </div>
                        <div className="divide-y divide-gray-50 max-h-[280px] overflow-y-auto">
                            {criticalTickets.length === 0 ? (
                                <div className="py-10 text-center">
                                    <p className="text-3xl mb-2">🎉</p>
                                    <p className="text-gray-400 text-sm">No critical infrastructure tickets!</p>
                                </div>
                            ) : (
                                criticalTickets.map(t => (
                                    <div key={t.id} className="px-5 py-3 flex items-center justify-between gap-4 hover:bg-red-50/30 transition-colors">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <p className="font-mono text-sm font-bold text-slate-900">{t.ticket_code}</p>
                                                <span className="text-[10px] font-bold px-1.5 py-0.5 bg-red-600 text-white rounded">
                                                    Score: {t.priority_score.toFixed(0)}
                                                </span>
                                            </div>
                                            <p className="text-sm text-gray-700 truncate mt-0.5">{t.issue_category}</p>
                                            <div className="flex items-center gap-2 mt-1">
                                                <p className="text-xs text-gray-500 border border-gray-200 px-1.5 rounded">{DEPT_NAMES[t.dept_id] ?? t.dept_id}</p>
                                                <p className="text-xs font-medium text-slate-600 bg-slate-100 px-1.5 rounded">Ward {t.ward_id}</p>
                                                {t.estimated_cost && (
                                                    <p className="text-xs font-medium text-emerald-700 bg-emerald-50 px-1.5 rounded border border-emerald-100">Est: {formatCurrency(t.estimated_cost)}</p>
                                                )}
                                            </div>
                                        </div>
                                        <div className="text-right shrink-0">
                                            {t.days_overdue > 0 ? (
                                                <p className="text-xs bg-red-100 text-red-800 font-bold px-2 py-1 rounded border border-red-200">{t.days_overdue}d Overdue</p>
                                            ) : (
                                                <p className="text-xs text-gray-500">In SLA</p>
                                            )}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>

                {/* Bottom Row: Ward Comparison Table */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                    <div className="px-5 py-5 border-b border-gray-100 flex items-center justify-between bg-slate-50">
                        <div className="flex items-center gap-2">
                            <span className="text-xl">🗺️</span>
                            <h2 className="font-bold text-slate-800 text-lg tracking-tight">Ward Infrastructure Performance Array</h2>
                        </div>
                        <span className="text-xs text-slate-500 font-medium">Sorted by highest overdue liabilities</span>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-white border-b-2 border-slate-100">
                                    <th className="text-left px-6 py-4 text-xs font-bold text-slate-600 uppercase tracking-wider">Ward ID</th>
                                    <th className="text-center px-4 py-4 text-xs font-bold text-slate-600 uppercase tracking-wider">Open Tickets</th>
                                    <th className="text-center px-4 py-4 text-xs font-bold text-slate-600 uppercase tracking-wider">Closed</th>
                                    <th className="text-left px-6 py-4 text-xs font-bold text-slate-600 uppercase tracking-wider">Overdue Risk</th>
                                    <th className="text-right px-6 py-4 text-xs font-bold text-slate-600 uppercase tracking-wider">Burned Budget</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50">
                                {wardPerf.length === 0 ? (
                                    <tr><td colSpan={5} className="text-center py-10 text-gray-400 text-sm italic">No ward data</td></tr>
                                ) : (
                                    wardPerf.map((w, i) => (
                                        <motion.tr
                                            key={w.ward_id}
                                            initial={{ opacity: 0, y: 5 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: i * 0.05 }}
                                            className="hover:bg-slate-50 transition-colors group"
                                        >
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-3">
                                                    <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center border border-slate-200 text-slate-700 font-bold text-sm group-hover:bg-slate-800 group-hover:text-white transition-colors">
                                                        {w.ward_id}
                                                    </div>
                                                    <span className="font-semibold text-slate-700 group-hover:text-slate-900">Ward {w.ward_id}</span>
                                                </div>
                                            </td>
                                            <td className="px-4 py-4 text-center text-slate-600 font-medium tracking-tight">
                                                {w.open}
                                            </td>
                                            <td className="px-4 py-4 text-center font-medium tracking-tight text-emerald-600">
                                                {w.closed}
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-2">
                                                    <div className={`h-2.5 rounded-full ${w.overdue > 10 ? 'bg-red-500' : w.overdue > 0 ? 'bg-orange-400' : 'bg-gray-200'}`} style={{ width: Math.min((w.overdue / Math.max(w.total, 1)) * 100, 100) + '%' }}></div>
                                                    <span className={`text-xs font-bold ${w.overdue > 0 ? "text-red-600" : "text-slate-400"}`}>
                                                        {w.overdue} tickets
                                                    </span>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 text-right">
                                                <span className="font-mono font-medium text-slate-700">
                                                    {formatCurrency(w.budget_spent)}
                                                </span>
                                            </td>
                                        </motion.tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
