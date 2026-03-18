"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";
import { councillorApi, socialIntelApi } from "@/lib/api";
import { DEPT_NAMES } from "@/lib/constants";
import ScenarioPlanner from "@/components/ScenarioPlanner";
import WardBenchmarkPanel from "@/components/WardBenchmarkPanel";
import WardTrustScoreCard from "@/components/WardTrustScoreCard";
import VerifiedResolutionsTable from "@/components/VerifiedResolutionsTable";
import CommunicationLogPanel from "@/components/CommunicationLogPanel";
import MisinfoFlagsPanel from "@/components/MisinfoFlagsPanel";

interface WardSummary {
    total: number;
    open: number;
    closed: number;
    overdue: number;
    resolution_rate: number;
    avg_satisfaction: number | null;
    avg_resolution_days: number;
}

interface DeptPerf {
    dept_id: string;
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
    issue_category: string;
    dept_id: string;
    priority_label: string;
    days_overdue: number;
}

interface SentimentOverview {
    total: number;
    positive: number;
    neutral: number;
    negative: number;
    score: number;
}

interface EmergingIssue {
    category: string;
    count: number;
    negative_count: number;
    max_urgency: string;
    platforms: string[];
    sample_summary: string | null;
}

interface SocialPost {
    id: string;
    platform: string;
    author: string | null;
    content: string;
    category: string | null;
    urgency: string | null;
    sentiment: string | null;
    summary: string | null;
    scraped_at: string | null;
    source_url: string;
}

const PLATFORM_ICONS: Record<string, string> = {
    news: "📰", reddit: "🟠", twitter: "🐦", youtube: "▶️",
    google_maps: "🗺️", civic: "🏛️", instagram: "📸", facebook: "📘",
};

const URGENCY_COLORS: Record<string, string> = {
    critical: "bg-red-100 text-red-700 border-red-200",
    high: "bg-orange-100 text-orange-700 border-orange-200",
    medium: "bg-yellow-100 text-yellow-700 border-yellow-200",
    low: "bg-green-100 text-green-600 border-green-200",
};

const SENTIMENT_COLORS: Record<string, string> = {
    negative: "text-red-600",
    positive: "text-emerald-600",
    neutral: "text-slate-500",
};

function SentimentGauge({ data }: { data: SentimentOverview }) {
    const total = data.total || 1;
    const negPct = Math.round((data.negative / total) * 100);
    const neuPct = Math.round((data.neutral / total) * 100);
    const posPct = 100 - negPct - neuPct;
    const score = data.score;
    const scoreColor = score > 0.2 ? "text-emerald-600" : score < -0.2 ? "text-red-600" : "text-yellow-600";

    if (data.total === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-8 text-center text-gray-400">
                <span className="text-3xl mb-2">📡</span>
                <p className="text-sm">No social signals yet</p>
                <p className="text-xs mt-1">Trigger a scrape from the Commissioner dashboard to start collecting data</p>
            </div>
        );
    }

    return (
        <div>
            <div className="flex items-center justify-between mb-2">
                <span className={`text-2xl font-bold ${scoreColor}`}>
                    {score > 0 ? "+" : ""}{score.toFixed(2)}
                </span>
                <span className="text-xs text-gray-400">{data.total} posts · last 7 days</span>
            </div>
            <div className="flex rounded-full overflow-hidden h-4 w-full mb-3">
                {negPct > 0 && <div className="bg-red-400 transition-all" style={{ width: `${negPct}%` }} title={`Negative: ${negPct}%`} />}
                {neuPct > 0 && <div className="bg-gray-300 transition-all" style={{ width: `${neuPct}%` }} title={`Neutral: ${neuPct}%`} />}
                {posPct > 0 && <div className="bg-emerald-400 transition-all" style={{ width: `${posPct}%` }} title={`Positive: ${posPct}%`} />}
            </div>
            <div className="flex gap-4 text-xs">
                <span className="text-red-600 font-medium">🔴 {negPct}% Negative</span>
                <span className="text-gray-500">⚪ {neuPct}% Neutral</span>
                <span className="text-emerald-600 font-medium">🟢 {posPct}% Positive</span>
            </div>
        </div>
    );
}

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
            className={`bg-gradient-to-br ${colorMap[color] || colorMap.blue} text-white rounded-2xl p-5 shadow-sm`}
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

function SatisfactionChart({ data }: { data: WeekData[] }) {
    if (data.length === 0) {
        return <div className="h-32 flex items-center justify-center text-gray-400 text-sm italic">No trend data</div>;
    }
    const maxVal = 5;
    const W = 500, H = 150, pad = 20;
    const xStep = (W - pad * 2) / Math.max(1, data.length - 1);
    const yScale = (v: number) => H - pad - ((v / maxVal) * (H - pad * 2));

    const points = data.map((d, i) => {
        const x = pad + (i * xStep);
        const y = yScale(d.avg_satisfaction || 0);
        return `${x},${y}`;
    }).join(" ");

    return (
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-40" preserveAspectRatio="none">
            {[0, 2.5, 5].map(v => (
                <line key={v} x1={pad} y1={yScale(v)} x2={W - pad} y2={yScale(v)} stroke="#e5e7eb" strokeWidth="1" strokeDasharray="4 4" />
            ))}
            <polyline points={points} fill="none" stroke="#4f46e5" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            {data.map((d, i) => {
                const x = pad + (i * xStep);
                const y = yScale(d.avg_satisfaction || 0);
                return (
                    <circle key={i} cx={x} cy={y} r="4" fill="#ffffff" stroke="#4f46e5" strokeWidth="2" />
                );
            })}
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
    const [sentiment, setSentiment] = useState<SentimentOverview | null>(null);
    const [emerging, setEmerging] = useState<EmergingIssue[]>([]);
    const [socialPosts, setSocialPosts] = useState<SocialPost[]>([]);
    
    // AI Intelligence state
    const [briefing, setBriefing] = useState<string | null>(null);
    const [rootCauses, setRootCauses] = useState<any[]>([]);
    const [alerts, setAlerts] = useState<any[]>([]);
    const [intelligenceLoading, setIntelligenceLoading] = useState(true);

    const [loading, setLoading] = useState(true);
    const [scrapeLoading, setScrapeLoading] = useState(false);

    const loadSocialData = useCallback(async (ward?: number) => {
        try {
            const [sent, emerg, posts] = await Promise.all([
                socialIntelApi.getSentimentOverview(ward).catch(() => ({ data: { total: 0, positive: 0, neutral: 0, negative: 0, score: 0 } })),
                socialIntelApi.getEmergingIssues(ward, 24, 6).catch(() => ({ data: [] })),
                socialIntelApi.getSocialPosts(ward, undefined, 1, 10).catch(() => ({ data: { results: [] } })),
            ]);
            setSentiment(sent.data);
            setEmerging(emerg.data);
            setSocialPosts(posts.data?.results ?? []);
        } catch {
            toast.error("Failed to refresh social data");
        }
    }, []);

    const handleScrape = useCallback(async (ward?: number) => {
        if (scrapeLoading) return;
        setScrapeLoading(true);
        try {
            await socialIntelApi.triggerWardScrape(ward);
            toast.success("Ward scrape started! Refreshing data in ~35 seconds…", { duration: 5000 });
            // Wait for scraper to finish, then reload
            setTimeout(() => {
                loadSocialData(ward).finally(() => setScrapeLoading(false));
            }, 35000);
        } catch {
            toast.error("Failed to trigger scrape");
            setScrapeLoading(false);
        }
    }, [scrapeLoading, loadSocialData]);

    useEffect(() => {
        const allowed = isCouncillor || isAdmin || isSupervisor;
        if (!user) return;
        if (!allowed) { router.push("/officer/dashboard"); return; }

        const ward = user.ward_id;
        
        // Load basic telemetry
        Promise.all([
            councillorApi.getWardSummary(ward),
            councillorApi.getDeptPerformance(ward),
            councillorApi.getSatisfactionTrend(ward, 8),
            councillorApi.getTopIssues(ward, 8),
            councillorApi.getOverdueTickets(ward),
            socialIntelApi.getSentimentOverview(ward).catch(() => ({ data: { total: 0, positive: 0, neutral: 0, negative: 0, score: 0 } })),
            socialIntelApi.getEmergingIssues(ward, 24, 6).catch(() => ({ data: [] })),
            socialIntelApi.getSocialPosts(ward, undefined, 1, 10).catch(() => ({ data: { results: [] } })),
        ]).then(([s, d, t, issues, ov, sent, emerg, posts]) => {
            setSummary(s.data);
            setDeptPerf(d.data);
            setTrend(t.data);
            setTopIssues(issues.data);
            setOverdue(ov.data);
            setSentiment((sent as { data: SentimentOverview }).data);
            setEmerging((emerg as { data: EmergingIssue[] }).data);
            setSocialPosts((posts as { data: { results: SocialPost[] } }).data?.results ?? []);
        }).catch(() => toast.error("Failed to load ward data"))
            .finally(() => setLoading(false));

        // Load AI Intelligence separately so it doesn't block the main dashboard
        Promise.all([
            councillorApi.getIntelligenceBriefing(ward).catch(() => ({ data: { briefing: "AI Briefing unavailable." } })),
            councillorApi.getRootCauses(ward).catch(() => ({ data: { root_causes: [] } })),
            councillorApi.getPredictiveAlerts(ward).catch(() => ({ data: { alerts: [] } })),
        ]).then(([briefResp, causesResp, alertsResp]) => {
            setBriefing(briefResp.data.briefing);
            setRootCauses(causesResp.data.root_causes || []);
            setAlerts(alertsResp.data.alerts || []);
        }).finally(() => setIntelligenceLoading(false));

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
                    <p className="text-emerald-200 text-xs mt-1">Ward-level civic intelligence — tickets + social signals</p>

                    {/* Development nav strip */}
                    <div className="flex items-center gap-1 mt-4 pt-3 border-t border-emerald-600 flex-wrap">
                        <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mr-2">
                            🏗️ Development
                        </span>
                        {[
                            { href: "/councillor/communications", label: "Communications", icon: "📣" },
                            { href: "/councillor/media-rti", label: "Media & RTI", icon: "🎙️" },
                            { href: "/councillor/casework", label: "Casework inbox", icon: "📂" },
                            { href: "/councillor/opportunity", label: "Opportunity Map", icon: "🗺️" },
                            { href: "/councillor/proposal", label: "Generate Proposal", icon: "📄" },
                            { href: "/councillor/proposals", label: "Past Proposals", icon: "📋" },
                        ].map(({ href, label, icon }) => (
                            <a
                                key={href}
                                href={href}
                                className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition-colors"
                            >
                                <span>{icon}</span>
                                {label}
                            </a>
                        ))}
                    </div>
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

                {/* ══ AI Intelligence Section ══════════════════════════════════════ */}
                <div>
                    <div className="flex items-center gap-2 mb-4">
                        <span className="text-xl">🧠</span>
                        <h2 className="text-base font-bold text-gray-800">Local Leadership Intelligence</h2>
                        <span className="text-xs bg-indigo-100 text-indigo-700 font-semibold px-2 py-0.5 rounded-full">Gemini AI</span>
                    </div>

                    {intelligenceLoading ? (
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 flex flex-col items-center justify-center">
                            <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-4" />
                            <p className="text-sm text-gray-500 font-medium">Synthesizing comprehensive ward intelligence...</p>
                            <p className="text-xs text-gray-400 mt-1">Analyzing cross-department data & geographic patterns</p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            {/* 1. Ward Reality Briefing */}
                            <div className="bg-gradient-to-br from-indigo-50 to-white rounded-2xl shadow-sm border border-indigo-100 p-5 col-span-1 lg:col-span-2">
                                <div className="flex items-center gap-2 mb-3">
                                    <span className="text-lg">🌅</span>
                                    <h3 className="font-bold text-indigo-900 text-sm">Morning Reality Briefing</h3>
                                </div>
                                <div className="text-sm text-gray-700 leading-relaxed space-y-2">
                                    {briefing ? (
                                        <p>{briefing}</p>
                                    ) : (
                                        <p className="text-gray-400 italic">Briefing currently unavailable. Check back later.</p>
                                    )}
                                </div>
                            </div>

                            {/* Predictive Alerts */}
                            <div className="bg-gradient-to-br from-amber-50 to-white rounded-2xl shadow-sm border border-amber-100 p-5">
                                <div className="flex items-center gap-2 mb-3">
                                    <span className="text-lg">🔮</span>
                                    <h3 className="font-bold text-amber-900 text-sm">Predictive Workload Alerts</h3>
                                </div>
                                <div className="space-y-3">
                                    {alerts.length === 0 ? (
                                        <div className="text-center py-4">
                                            <span className="text-2xl opacity-50 block mb-1">🌤️</span>
                                            <p className="text-xs text-amber-700">No seasonal spikes expected in the next 3 weeks.</p>
                                        </div>
                                    ) : (
                                        alerts.map((alert, idx) => (
                                            <div key={idx} className="bg-white rounded-lg p-3 border border-amber-200 shadow-sm">
                                                <div className="flex items-center justify-between mb-1">
                                                    <span className="text-xs font-bold text-orange-800 uppercase tracking-wide">{alert.category}</span>
                                                    <span className="text-[10px] bg-red-100 text-red-700 font-bold px-1.5 py-0.5 rounded">+{alert.predicted_increase_pct}% Spiking</span>
                                                </div>
                                                <p className="text-xs text-gray-700">{alert.narrative}</p>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>

                            {/* 2. Root Cause Radar */}
                            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 col-span-1 lg:col-span-3">
                                <div className="flex items-center gap-2 mb-4">
                                    <span className="text-lg">🎯</span>
                                    <h3 className="font-bold text-gray-800 text-sm">Root Cause Radar</h3>
                                    <span className="text-[10px] text-gray-400 ml-auto border border-gray-200 rounded px-1.5 py-0.5">Geospatial Clustering Active</span>
                                </div>
                                
                                {rootCauses.length === 0 ? (
                                    <div className="text-center py-6 text-gray-500 bg-gray-50 rounded-xl border border-dashed border-gray-200">
                                        <span className="text-2xl mb-2 block opacity-50">✨</span>
                                        <p className="text-sm font-medium">No systemic clusters detected</p>
                                        <p className="text-xs mt-1">Issues appear geographically isolated right now.</p>
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                        {rootCauses.map((rc, idx) => (
                                            <div key={idx} className="border border-gray-100 rounded-xl p-4 bg-gray-50/50 hover:bg-white transition-colors duration-200 group">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <div className="bg-rose-100 text-rose-700 text-xs font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                                                        <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse"></span>
                                                        {rc.ticket_count} tickets
                                                    </div>
                                                    <span className="text-xs font-semibold text-gray-600">{rc.category}</span>
                                                </div>
                                                <p className="text-xs text-gray-700 leading-relaxed">{rc.insight}</p>
                                                <div className="mt-3 text-[10px] text-indigo-600 font-medium opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 cursor-pointer">
                                                    Escalate to {DEPT_NAMES[rc.category] || "Department"} Head <span>→</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
                {/* ═══════════════════════════════════════════════════════════════ */}

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

                {/* ══ Decision Intelligence Section ══════════════════════════════════ */}
                <div>
                    <div className="flex items-center gap-2 mb-4">
                        <span className="text-xl">🧠</span>
                        <h2 className="text-lg font-extrabold text-slate-800 tracking-tight">Decision Intelligence</h2>
                        <span className="text-xs bg-indigo-100 text-indigo-700 font-bold px-2.5 py-1 rounded-full border border-indigo-200 shadow-sm ml-2">AI-Powered</span>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-6 border-b border-gray-100 mb-6">
                        <ScenarioPlanner wardId={user?.ward_id} />
                        <WardBenchmarkPanel wardId={user?.ward_id} />
                    </div>
                </div>

                {/* ═══════════════════════════════════════════════════════════════ */}

                {/* ══ PILLAR 3: Public Trust Section ══════════════════════════════ */}
                <div>
                    <div className="flex items-center gap-2 mb-6">
                        <span className="text-xl">🛡️</span>
                        <h2 className="text-lg font-extrabold text-slate-800 tracking-tight">Public Trust</h2>
                        <span className="text-xs bg-emerald-100 text-emerald-700 font-bold px-2.5 py-1 rounded-full border border-emerald-200 shadow-sm ml-2">Pillar 3</span>
                    </div>

                    {/* Row 1: Trust Score + Misinformation side-by-side */}  
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                        {/* Feature 4 — Ward Trust Score */}
                        {user?.ward_id && (
                            <WardTrustScoreCard wardId={user.ward_id} showInsights={true} />
                        )}
                        {/* Feature 3 — Misinformation Flags */}
                        <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-6">
                            <MisinfoFlagsPanel wardId={user?.ward_id} />
                        </div>
                    </div>

                    {/* Row 2: Verified Resolutions (Feature 1) */}
                    <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-6 mb-6">
                        <VerifiedResolutionsTable wardId={user?.ward_id} />
                    </div>

                    {/* Row 3: Communication Log (Feature 2) */}
                    {user?.ward_id && (
                        <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-6">
                            <CommunicationLogPanel wardId={user.ward_id} />
                        </div>
                    )}
                </div>
                {/* ═══════════════════════════════════════════════════════════════ */}

                {/* ══ Social Intelligence Section ══════════════════════════════════ */}
                <div>
                    <div className="flex items-center gap-2 mb-4">
                        <span className="text-xl">📡</span>
                        <h2 className="text-base font-bold text-gray-800">Social Intelligence</h2>
                        <span className="text-xs bg-indigo-100 text-indigo-700 font-semibold px-2 py-0.5 rounded-full">Live · News & Social</span>
                        <button
                            onClick={() => handleScrape(user?.ward_id)}
                            disabled={scrapeLoading}
                            className="ml-auto flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full border transition-all bg-white border-indigo-300 text-indigo-700 hover:bg-indigo-50 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {scrapeLoading ? (
                                <>
                                    <span className="w-3.5 h-3.5 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />
                                    Fetching…
                                </>
                            ) : (
                                <>
                                    <span>🔄</span> Refresh Data
                                </>
                            )}
                        </button>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Sentiment Gauge */}
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                            <div className="flex items-center gap-2 mb-4">
                                <span className="text-lg">💬</span>
                                <h3 className="font-bold text-gray-700 text-sm">Ward Sentiment (7 days)</h3>
                            </div>
                            {sentiment ? (
                                <SentimentGauge data={sentiment} />
                            ) : (
                                <div className="text-center py-6 text-gray-400 text-sm">Loading…</div>
                            )}
                        </div>

                        {/* Emerging Issues */}
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                            <div className="flex items-center gap-2 mb-4">
                                <span className="text-lg">🚨</span>
                                <h3 className="font-bold text-gray-700 text-sm">Emerging Issues (24h)</h3>
                            </div>
                            {emerging.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-6 text-gray-400 text-sm">
                                    <span className="text-2xl mb-2">🔍</span>
                                    <p>No emerging signals yet</p>
                                </div>
                            ) : (
                                <div className="space-y-2.5">
                                    {emerging.map((issue, i) => (
                                        <motion.div
                                            key={issue.category}
                                            initial={{ opacity: 0, x: -8 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            transition={{ delay: i * 0.05 }}
                                            className="flex items-start justify-between gap-2"
                                        >
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-1.5 flex-wrap">
                                                    <span className="text-xs font-bold text-gray-800">{issue.category}</span>
                                                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${URGENCY_COLORS[issue.max_urgency] ?? "bg-gray-100 text-gray-500 border-gray-200"}`}>
                                                        {issue.max_urgency}
                                                    </span>
                                                </div>
                                                {issue.sample_summary && (
                                                    <p className="text-[10px] text-gray-500 mt-0.5 line-clamp-1">{issue.sample_summary}</p>
                                                )}
                                                <div className="flex gap-1 mt-1">
                                                    {issue.platforms.slice(0, 3).map(p => (
                                                        <span key={p} className="text-[10px] bg-slate-100 text-slate-600 px-1.5 rounded">
                                                            {PLATFORM_ICONS[p] ?? "📄"} {p}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                            <span className="text-xs font-bold text-indigo-700 shrink-0">{issue.count}</span>
                                        </motion.div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Social Post Stream */}
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
                            <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                                <span className="text-lg">🌐</span>
                                <h3 className="font-bold text-gray-700 text-sm">Latest Social Posts</h3>
                                <span className="ml-auto text-xs text-gray-400">{socialPosts.length} shown</span>
                            </div>
                            <div className="divide-y divide-gray-50 max-h-72 overflow-y-auto flex-1">
                                {socialPosts.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center py-8 text-gray-400 text-center px-4">
                                        <span className="text-3xl mb-2">📭</span>
                                        <p className="text-sm">No posts collected yet</p>
                                        <p className="text-xs mt-1 text-gray-300">Commissioner can trigger a scrape to start</p>
                                    </div>
                                ) : (
                                    socialPosts.map(post => (
                                        <div key={post.id} className="px-4 py-3">
                                            <div className="flex items-center gap-1.5 mb-1">
                                                <span className="text-sm">{PLATFORM_ICONS[post.platform] ?? "📄"}</span>
                                                <span className="text-xs font-semibold text-gray-600 capitalize">{post.platform}</span>
                                                {post.urgency && (
                                                    <span className={`text-[9px] font-bold px-1 py-0.5 rounded border ml-auto ${URGENCY_COLORS[post.urgency] ?? "bg-gray-100 text-gray-500 border-gray-200"}`}>
                                                        {post.urgency}
                                                    </span>
                                                )}
                                                {post.sentiment && (
                                                    <span className={`text-[9px] font-semibold ${SENTIMENT_COLORS[post.sentiment] ?? "text-gray-400"}`}>
                                                        {post.sentiment === "negative" ? "😞" : post.sentiment === "positive" ? "😊" : "😐"}
                                                    </span>
                                                )}
                                            </div>
                                            {post.summary ? (
                                                <p className="text-xs text-gray-700 line-clamp-2">{post.summary}</p>
                                            ) : (
                                                <p className="text-xs text-gray-600 line-clamp-2">{post.content}</p>
                                            )}
                                            {post.category && (
                                                <span className="inline-block mt-1 text-[9px] bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded">{post.category}</span>
                                            )}
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>
                </div>
                {/* ═══════════════════════════════════════════════════════════════ */}

            </div>
        </div>
    );
}

