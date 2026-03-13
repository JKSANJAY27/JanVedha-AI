"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { formatDate } from "@/lib/formatters";
import { publicApi, officerApi } from "@/lib/api";
import toast from "react-hot-toast";
import StatCard from "@/components/StatCard";
import { DEPT_NAMES, getWardLabel } from "@/lib/constants";

interface WardEntry {
    ward_id: number;
    total_tickets: number;
    resolved_tickets: number;
    resolution_rate: number;
}

interface CityStats {
    total_tickets: number;
    resolved_pct: number;
    active_critical: number;
    active_high: number;
}

interface DeptSummary {
    total: number;
    open: number;
    closed: number;
    overdue: number;
    critical: number;
    avg_satisfaction: number | null;
}

export default function ReportsPage() {
    const { user, isOfficer } = useAuth();
    const router = useRouter();
    const isJuniorEngineer = user?.role === "JUNIOR_ENGINEER";

    // City-wide state (supervisor / other officers)
    const [stats, setStats] = useState<CityStats | null>(null);
    const [wards, setWards] = useState<WardEntry[]>([]);

    // Dept-specific state (JE)
    const [deptSummary, setDeptSummary] = useState<DeptSummary | null>(null);
    const [deptTickets, setDeptTickets] = useState<any[]>([]);

    const [loading, setLoading] = useState(true);
    const [selectedWard, setSelectedWard] = useState<number | "all">("all");

    const now = new Date();
    const monthName = now.toLocaleString("en-IN", { month: "long", year: "numeric" });
    const deptName = user?.dept_id ? (DEPT_NAMES[user.dept_id] ?? user.dept_id) : "Department";

    useEffect(() => {
        if (!isOfficer) { router.push("/login"); return; }

        if (isJuniorEngineer) {
            // Load JE department-specific data
            Promise.all([
                officerApi.getDashboardSummary(),
                officerApi.getTickets(500),
            ])
                .then(([s, t]) => {
                    setDeptSummary(s.data);
                    setDeptTickets(t.data);
                })
                .catch(() => toast.error("Failed to load department report"))
                .finally(() => setLoading(false));
        } else {
            Promise.all([publicApi.getStats(), publicApi.getLeaderboard()])
                .then(([s, l]) => {
                    setStats(s.data);
                    setWards(l.data);
                })
                .finally(() => setLoading(false));
        }
    }, [isJuniorEngineer]);

    // ─── Dept breakdown helpers ───────────────────────────────────────────────

    const statusGroups = {
        open: deptTickets.filter(t => t.status === "OPEN").length,
        assigned: deptTickets.filter(t => t.status === "ASSIGNED").length,
        scheduled: deptTickets.filter(t => t.status === "SCHEDULED").length,
        inProgress: deptTickets.filter(t => t.status === "IN_PROGRESS").length,
        closed: deptTickets.filter(t => t.status === "CLOSED").length,
    };

    const priorityGroups = {
        CRITICAL: deptTickets.filter(t => t.priority_label === "CRITICAL").length,
        HIGH: deptTickets.filter(t => t.priority_label === "HIGH").length,
        MEDIUM: deptTickets.filter(t => t.priority_label === "MEDIUM").length,
        LOW: deptTickets.filter(t => t.priority_label === "LOW").length,
    };

    const overdue = deptTickets.filter(t =>
        t.sla_deadline && new Date(t.sla_deadline) < now && !["CLOSED", "REJECTED"].includes(t.status)
    );

    const resolutionRate = deptSummary
        ? deptSummary.total > 0
            ? Math.round((deptSummary.closed / deptSummary.total) * 100)
            : 0
        : 0;

    // ─── Download handler ─────────────────────────────────────────────────────

    const handleDownload = () => {
        let content = "";
        if (isJuniorEngineer && deptSummary) {
            content =
                `JanVedha AI — ${deptName} Department Report\n` +
                `Generated: ${now.toLocaleString()}\n\n` +
                `DEPARTMENT: ${deptName}\n` +
                `Period: ${monthName}\n\n` +
                `SUMMARY\n` +
                `Total Tickets: ${deptSummary.total}\n` +
                `Open: ${deptSummary.open}\n` +
                `Closed: ${deptSummary.closed}\n` +
                `Overdue: ${deptSummary.overdue}\n` +
                `Critical: ${deptSummary.critical}\n` +
                `Resolution Rate: ${resolutionRate}%\n\n` +
                `PRIORITY BREAKDOWN\n` +
                Object.entries(priorityGroups).map(([p, c]) => `  ${p}: ${c}`).join("\n") + "\n\n" +
                `OVERDUE TICKETS (${overdue.length})\n` +
                overdue.map(t => `  ${t.ticket_code} — ${t.issue_category ?? "General"} [${t.priority_label}]`).join("\n");
        } else {
            content =
                `JanVedha AI — ${monthName} Report\n` +
                `Generated: ${now.toLocaleString()}\n\n` +
                `CITY OVERVIEW\n` +
                `Total Tickets: ${stats?.total_tickets ?? "N/A"}\n` +
                `Resolution Rate: ${stats?.resolved_pct ?? "N/A"}%\n` +
                `Active Critical: ${stats?.active_critical ?? "N/A"}\n\n` +
                `WARD LEADERBOARD\n` +
                wards.map((w, i) => `  ${i + 1}. ${getWardLabel(w.ward_id)}: ${w.resolution_rate}% (${w.resolved_tickets}/${w.total_tickets})`).join("\n");
        }

        const blob = new Blob([content], { type: "text/plain" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `JanVedha-${isJuniorEngineer ? deptName.replace(/\s+/g, "-") : "City"}-Report-${now.toISOString().slice(0, 7)}.txt`;
        a.click();
        toast.success("Report downloaded!");
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
            </div>
        );
    }

    // ─── JE Department Report View ────────────────────────────────────────────

    if (isJuniorEngineer && deptSummary) {
        return (
            <div className="min-h-screen bg-slate-50">
                {/* Header */}
                <div className="bg-gradient-to-r from-teal-700 to-cyan-800 text-white px-6 py-6">
                    <div className="max-w-5xl mx-auto flex flex-wrap items-center justify-between gap-4">
                        <div>
                            <p className="text-teal-300 text-sm">
                                {user?.role?.replace(/_/g, " ")} · {deptName}
                            </p>
                            <h1 className="text-2xl font-bold mt-0.5">Department Reports</h1>
                            <p className="text-teal-300 text-sm mt-1">{monthName}</p>
                        </div>
                        <button
                            onClick={handleDownload}
                            className="bg-white/10 border border-white/20 text-white px-5 py-2.5 rounded-xl font-semibold text-sm hover:bg-white/20 transition-colors flex items-center gap-2"
                        >
                            ⬇ Download Report
                        </button>
                    </div>
                </div>

                <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">

                    {/* Department Summary Card */}
                    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
                        <div className="flex items-start justify-between mb-6">
                            <div>
                                <h2 className="text-xl font-bold text-gray-900">
                                    {deptName} — Executive Summary
                                </h2>
                                <p className="text-gray-500 text-sm mt-1">{monthName}</p>
                            </div>
                            <div className="text-right">
                                <p className="text-xs text-gray-400">Generated by</p>
                                <p className="font-bold text-teal-700">JanVedha AI</p>
                            </div>
                        </div>

                        {/* Stats grid */}
                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
                            <StatCard label="Total" value={deptSummary.total} icon="📋" color="blue" />
                            <StatCard label="Open" value={deptSummary.open} icon="⚡" color="orange" />
                            <StatCard label="Closed" value={deptSummary.closed} icon="✅" color="green" />
                            <StatCard label="Overdue" value={deptSummary.overdue} icon="⚠️" color="red" />
                            <StatCard label="Critical" value={deptSummary.critical} icon="🚨" color="red" />
                        </div>

                        {/* Key findings */}
                        <div className="bg-gray-50 rounded-2xl p-5">
                            <p className="text-sm font-semibold text-gray-700 mb-2">Key Findings</p>
                            <ul className="space-y-1.5 text-sm text-gray-600">
                                <li>• Resolution rate: <strong>{resolutionRate}%</strong> {resolutionRate >= 70 ? "✅ Meeting target" : "⚠️ Below 70% target"}</li>
                                <li>• Critical issues requiring immediate attention: <strong>{deptSummary.critical}</strong></li>
                                <li>• SLA-breached tickets: <strong>{deptSummary.overdue}</strong></li>
                                {deptSummary.avg_satisfaction !== null && (
                                    <li>• Average citizen satisfaction: <strong>{deptSummary.avg_satisfaction}/5</strong></li>
                                )}
                                <li>• Total complaints processed for {deptName}: <strong>{deptSummary.total}</strong></li>
                            </ul>
                        </div>
                    </div>

                    {/* Status Breakdown */}
                    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-6">
                        <h2 className="font-bold text-gray-900 mb-4">📊 Status Breakdown</h2>
                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                            {[
                                { label: "Open", value: statusGroups.open, color: "bg-orange-50 text-orange-700 border-orange-200" },
                                { label: "Assigned", value: statusGroups.assigned, color: "bg-blue-50 text-blue-700 border-blue-200" },
                                { label: "Scheduled", value: statusGroups.scheduled, color: "bg-purple-50 text-purple-700 border-purple-200" },
                                { label: "In Progress", value: statusGroups.inProgress, color: "bg-yellow-50 text-yellow-700 border-yellow-200" },
                                { label: "Closed", value: statusGroups.closed, color: "bg-green-50 text-green-700 border-green-200" },
                            ].map(s => (
                                <div key={s.label} className={`rounded-xl border p-4 text-center ${s.color}`}>
                                    <p className="text-2xl font-bold">{s.value}</p>
                                    <p className="text-xs font-medium mt-1">{s.label}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Priority Breakdown */}
                    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-6">
                        <h2 className="font-bold text-gray-900 mb-4">🎯 Priority Breakdown</h2>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                            {[
                                { label: "Critical", value: priorityGroups.CRITICAL, color: "bg-red-50 text-red-700 border-red-200" },
                                { label: "High", value: priorityGroups.HIGH, color: "bg-orange-50 text-orange-700 border-orange-200" },
                                { label: "Medium", value: priorityGroups.MEDIUM, color: "bg-yellow-50 text-yellow-700 border-yellow-200" },
                                { label: "Low", value: priorityGroups.LOW, color: "bg-green-50 text-green-700 border-green-200" },
                            ].map(p => (
                                <div key={p.label} className={`rounded-xl border p-4 text-center ${p.color}`}>
                                    <p className="text-2xl font-bold">{p.value}</p>
                                    <p className="text-xs font-medium mt-1">{p.label}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Overdue Tickets */}
                    {overdue.length > 0 && (
                        <div className="bg-red-50 border border-red-200 rounded-3xl p-6">
                            <h2 className="font-bold text-red-800 mb-4 flex items-center gap-2">
                                ⚠️ SLA Breached Tickets ({overdue.length})
                            </h2>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead className="bg-red-100 text-red-700 text-xs font-semibold">
                                        <tr>
                                            <th className="px-4 py-2 text-left">Ticket ID</th>
                                            <th className="px-4 py-2 text-left">Category</th>
                                            <th className="px-4 py-2 text-left">Priority</th>
                                            <th className="px-4 py-2 text-left">Status</th>
                                            <th className="px-4 py-2 text-left">SLA Deadline</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-red-100">
                                        {overdue.map(t => (
                                            <tr key={t.id} className="bg-white hover:bg-red-50 transition-colors">
                                                <td className="px-4 py-2 font-mono font-bold text-red-700">{t.ticket_code}</td>
                                                <td className="px-4 py-2 text-gray-700">{t.issue_category ?? "General"}</td>
                                                <td className="px-4 py-2">
                                                    <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700">{t.priority_label}</span>
                                                </td>
                                                <td className="px-4 py-2 text-gray-500">{t.status}</td>
                                                <td className="px-4 py-2 text-red-600 font-semibold">
                                                    {new Date(t.sla_deadline).toLocaleDateString("en-IN", { dateStyle: "medium" })}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* All tickets table */}
                    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
                        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                            <h2 className="font-bold text-gray-900">All {deptName} Tickets</h2>
                            <span className="text-xs text-gray-400 bg-gray-100 px-3 py-1 rounded-full">{deptTickets.length} total</span>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-gray-50 text-gray-500 text-xs font-semibold uppercase">
                                    <tr>
                                        <th className="px-5 py-3 text-left">Ticket ID</th>
                                        <th className="px-5 py-3 text-left">Category</th>
                                        <th className="px-5 py-3 text-left">Priority</th>
                                        <th className="px-5 py-3 text-left">Status</th>
                                        <th className="px-5 py-3 text-left">Created</th>
                                        <th className="px-5 py-3 text-left">SLA</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-50">
                                    {deptTickets.map(t => {
                                        const isOverdue = t.sla_deadline && new Date(t.sla_deadline) < now && !["CLOSED"].includes(t.status);
                                        return (
                                            <tr key={t.id} className={`transition-colors ${isOverdue ? "bg-red-50 hover:bg-red-100" : "hover:bg-gray-50"}`}>
                                                <td className="px-5 py-3 font-mono font-bold text-blue-600">{t.ticket_code}</td>
                                                <td className="px-5 py-3 text-gray-700">{t.issue_category ?? "General"}</td>
                                                <td className="px-5 py-3">
                                                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                                                        t.priority_label === "CRITICAL" ? "bg-red-100 text-red-700" :
                                                        t.priority_label === "HIGH" ? "bg-orange-100 text-orange-700" :
                                                        t.priority_label === "MEDIUM" ? "bg-yellow-100 text-yellow-700" :
                                                        "bg-green-100 text-green-700"
                                                    }`}>{t.priority_label}</span>
                                                </td>
                                                <td className="px-5 py-3 text-gray-500 text-xs">{t.status.replace(/_/g, " ")}</td>
                                                <td className="px-5 py-3 text-gray-400 text-xs">{new Date(t.created_at).toLocaleDateString("en-IN", { dateStyle: "medium" })}</td>
                                                <td className={`px-5 py-3 text-xs font-semibold ${isOverdue ? "text-red-600" : "text-gray-400"}`}>
                                                    {t.sla_deadline ? new Date(t.sla_deadline).toLocaleDateString("en-IN", { dateStyle: "medium" }) : "N/A"}
                                                    {isOverdue && " ⚠️"}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // ─── City-Wide / Supervisor Reports View ─────────────────────────────────

    const wardData = selectedWard !== "all" ? wards.find(w => w.ward_id === Number(selectedWard)) : null;

    return (
        <div className="min-h-screen bg-slate-50">
            <div className="bg-gradient-to-r from-slate-800 to-gray-900 text-white px-6 py-6">
                <div className="max-w-5xl mx-auto flex flex-wrap items-center justify-between gap-4">
                    <div>
                        <p className="text-gray-400 text-sm">{user?.role?.replace(/_/g, " ")}</p>
                        <h1 className="text-2xl font-bold mt-0.5">Reports & Analytics</h1>
                        <p className="text-gray-400 text-sm mt-1">{monthName}</p>
                    </div>
                    <button
                        onClick={handleDownload}
                        className="bg-blue-600 text-white px-5 py-2.5 rounded-xl font-semibold text-sm hover:bg-blue-700 transition-colors shadow-sm flex items-center gap-2"
                    >
                        ⬇ Download Report
                    </button>
                </div>
            </div>

            <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
                {/* Ward selector */}
                <div className="flex items-center gap-3">
                    <label className="text-sm font-medium text-gray-600">Filter by Ward:</label>
                    <select
                        value={selectedWard}
                        onChange={(e) => setSelectedWard(e.target.value === "all" ? "all" : Number(e.target.value))}
                        className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    >
                        <option value="all">All Wards (City Overview)</option>
                        {wards.map((w) => (
                            <option key={w.ward_id} value={w.ward_id}>{getWardLabel(w.ward_id)}</option>
                        ))}
                    </select>
                </div>

                {/* Executive summary */}
                <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
                    <div className="flex items-start justify-between mb-6">
                        <div>
                            <h2 className="text-xl font-bold text-gray-900">
                                {selectedWard === "all" ? "City-Wide Executive Summary" : `${getWardLabel(selectedWard as number)} Summary`}
                            </h2>
                            <p className="text-gray-500 text-sm mt-1">{monthName}</p>
                        </div>
                        <div className="text-right">
                            <p className="text-xs text-gray-400">Generated by</p>
                            <p className="font-bold text-blue-700">JanVedha AI</p>
                        </div>
                    </div>

                    {stats && (
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                            <StatCard label="Total Tickets" value={wardData?.total_tickets ?? stats.total_tickets} icon="📋" color="blue" />
                            <StatCard label="Resolution Rate" value={`${wardData?.resolution_rate ?? stats.resolved_pct}%`} icon="✅" color="green" />
                            <StatCard label="Active Critical" value={stats.active_critical} icon="🚨" color="red" />
                            <StatCard label="Active High" value={stats.active_high} icon="🟠" color="orange" />
                        </div>
                    )}

                    <div className="bg-gray-50 rounded-2xl p-5">
                        <p className="text-sm font-semibold text-gray-700 mb-2">Key Findings</p>
                        <ul className="space-y-1.5 text-sm text-gray-600">
                            <li>• Resolution rate: <strong>{wardData?.resolution_rate ?? stats?.resolved_pct}%</strong> {(wardData?.resolution_rate ?? stats?.resolved_pct ?? 0) >= 70 ? "✅ Meeting target" : "⚠️ Below 70% target"}</li>
                            <li>• Critical issues requiring immediate attention: <strong>{stats?.active_critical ?? "—"}</strong></li>
                            <li>• Total civic complaints processed this period: <strong>{wardData?.total_tickets ?? stats?.total_tickets ?? "—"}</strong></li>
                        </ul>
                    </div>
                </div>

                {/* Ward leaderboard table */}
                {selectedWard === "all" && (
                    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
                        <div className="px-6 py-4 border-b border-gray-100">
                            <h2 className="font-bold text-gray-900">Ward Performance Table</h2>
                        </div>
                        <table className="w-full">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Rank</th>
                                    <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Ward</th>
                                    <th className="px-5 py-3 text-center text-xs font-semibold text-gray-500 uppercase">Total</th>
                                    <th className="px-5 py-3 text-center text-xs font-semibold text-gray-500 uppercase">Resolved</th>
                                    <th className="px-5 py-3 text-center text-xs font-semibold text-gray-500 uppercase">Rate</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50">
                                {wards.map((w, i) => (
                                    <tr key={w.ward_id} className="hover:bg-gray-50 transition-colors">
                                        <td className="px-5 py-3 text-sm font-bold text-gray-400">#{i + 1}</td>
                                        <td className="px-5 py-3 text-sm font-medium text-gray-900">{getWardLabel(w.ward_id)}</td>
                                        <td className="px-5 py-3 text-center text-sm text-gray-600">{w.total_tickets}</td>
                                        <td className="px-5 py-3 text-center text-sm text-green-600 font-medium">{w.resolved_tickets}</td>
                                        <td className="px-5 py-3 text-center">
                                            <span className={`inline-flex items-center gap-1.5 text-sm font-semibold ${w.resolution_rate >= 70 ? "text-green-600" : "text-orange-600"}`}>
                                                {w.resolution_rate}%
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
