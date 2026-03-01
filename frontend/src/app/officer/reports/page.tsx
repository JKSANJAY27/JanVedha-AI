"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { publicApi } from "@/lib/api";
import toast from "react-hot-toast";
import StatCard from "@/components/StatCard";
import { DEPT_NAMES } from "@/lib/constants";

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

export default function ReportsPage() {
    const { user, isOfficer } = useAuth();
    const router = useRouter();
    const [stats, setStats] = useState<CityStats | null>(null);
    const [wards, setWards] = useState<WardEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedWard, setSelectedWard] = useState<number | "all">("all");

    useEffect(() => {
        if (!isOfficer) { router.push("/login"); return; }
        Promise.all([publicApi.getStats(), publicApi.getLeaderboard()])
            .then(([s, l]) => {
                setStats(s.data);
                setWards(l.data);
            })
            .finally(() => setLoading(false));
    }, []);

    const now = new Date();
    const monthName = now.toLocaleString("en-IN", { month: "long", year: "numeric" });

    const selectedWardData = selectedWard === "all" ? null : wards.find((w) => w.ward_id === selectedWard);

    const handleDownload = () => {
        const content = `JanVedha AI — ${monthName} Report\n` +
            `Generated: ${now.toLocaleString()}\n\n` +
            `CITY OVERVIEW\n` +
            `Total Tickets: ${stats?.total_tickets ?? "N/A"}\n` +
            `Resolution Rate: ${stats?.resolved_pct ?? "N/A"}%\n` +
            `Active Critical: ${stats?.active_critical ?? "N/A"}\n\n` +
            (selectedWardData
                ? `WARD ${selectedWardData.ward_id} REPORT\n` +
                `Total: ${selectedWardData.total_tickets}\n` +
                `Resolved: ${selectedWardData.resolved_tickets}\n` +
                `Resolution Rate: ${selectedWardData.resolution_rate}%\n`
                : `WARD LEADERBOARD\n` +
                wards.map((w, i) => `  ${i + 1}. Ward ${w.ward_id}: ${w.resolution_rate}% resolution (${w.resolved_tickets}/${w.total_tickets})`).join("\n")
            );

        const blob = new Blob([content], { type: "text/plain" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `JanVedha-Report-${now.toISOString().slice(0, 7)}.txt`;
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
                            <option key={w.ward_id} value={w.ward_id}>Ward {w.ward_id}</option>
                        ))}
                    </select>
                </div>

                {/* Executive summary */}
                <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
                    <div className="flex items-start justify-between mb-6">
                        <div>
                            <h2 className="text-xl font-bold text-gray-900">
                                {selectedWard === "all" ? "City-Wide Executive Summary" : `Ward ${selectedWard} Summary`}
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
                                        <td className="px-5 py-3 text-sm font-medium text-gray-900">Ward {w.ward_id}</td>
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
