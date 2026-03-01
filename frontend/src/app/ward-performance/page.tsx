"use client";

import { useEffect, useState } from "react";
import { publicApi } from "@/lib/api";
import { motion } from "framer-motion";
import StatCard from "@/components/StatCard";

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
    avg_resolution_hours: number;
}

function getGrade(rate: number) {
    if (rate >= 90) return { label: "EXCELLENT", color: "bg-green-100 text-green-700" };
    if (rate >= 75) return { label: "GOOD", color: "bg-blue-100 text-blue-700" };
    if (rate >= 60) return { label: "SATISFACTORY", color: "bg-yellow-100 text-yellow-700" };
    if (rate >= 40) return { label: "NEEDS IMPROVEMENT", color: "bg-orange-100 text-orange-700" };
    return { label: "POOR", color: "bg-red-100 text-red-700" };
}

const MEDALS = ["🥇", "🥈", "🥉"];

export default function WardPerformancePage() {
    const [stats, setStats] = useState<CityStats | null>(null);
    const [wards, setWards] = useState<WardEntry[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([publicApi.getStats(), publicApi.getLeaderboard()])
            .then(([statsRes, leaderboardRes]) => {
                setStats(statsRes.data);
                setWards(leaderboardRes.data);
            })
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
            {/* Header */}
            <section className="bg-gradient-to-br from-blue-900 via-blue-800 to-indigo-900 text-white py-14 px-4">
                <div className="max-w-5xl mx-auto text-center">
                    <h1 className="text-4xl font-extrabold mb-3">Ward Performance Leaderboard</h1>
                    <p className="text-blue-200 text-lg">Real-time civic resolution ratings across all wards</p>
                </div>
            </section>

            <div className="max-w-5xl mx-auto px-4 py-10">
                {/* City stats */}
                {stats && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
                        <StatCard
                            label="Total Tickets"
                            value={stats.total_tickets.toLocaleString()}
                            icon="📋"
                            color="blue"
                        />
                        <StatCard
                            label="Resolution Rate"
                            value={`${stats.resolved_pct}%`}
                            icon="✅"
                            color="green"
                        />
                        <StatCard
                            label="Active Critical"
                            value={stats.active_critical}
                            icon="🔴"
                            color="red"
                        />
                        <StatCard
                            label="Active High"
                            value={stats.active_high}
                            icon="🟠"
                            color="orange"
                        />
                    </div>
                )}

                {/* Ward table */}
                <div className="bg-white rounded-3xl shadow-xl border border-gray-100 overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                        <h2 className="text-lg font-bold text-gray-900">Ward Rankings</h2>
                        <span className="text-sm text-gray-400">{wards.length} wards</span>
                    </div>
                    {wards.length === 0 ? (
                        <div className="text-center py-16 text-gray-400">
                            <div className="text-4xl mb-3">🏙️</div>
                            <p>No ward data available yet. Submit some complaints first!</p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead className="bg-gray-50 border-b border-gray-100">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Rank</th>
                                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Ward</th>
                                        <th className="px-6 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Total Tickets</th>
                                        <th className="px-6 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Resolved</th>
                                        <th className="px-6 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Resolution %</th>
                                        <th className="px-6 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Grade</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-50">
                                    {wards.map((ward, i) => {
                                        const grade = getGrade(ward.resolution_rate);
                                        return (
                                            <motion.tr
                                                key={ward.ward_id}
                                                initial={{ opacity: 0, x: -10 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: i * 0.05 }}
                                                className="hover:bg-gray-50 transition-colors"
                                            >
                                                <td className="px-6 py-4">
                                                    <span className="text-lg">
                                                        {MEDALS[i] ?? <span className="font-bold text-gray-400">#{i + 1}</span>}
                                                    </span>
                                                    {i >= 3 && <span className="font-bold text-gray-400 text-sm">#{i + 1}</span>}
                                                </td>
                                                <td className="px-6 py-4">
                                                    <p className="font-semibold text-gray-900 text-sm">Ward {ward.ward_id}</p>
                                                </td>
                                                <td className="px-6 py-4 text-center text-sm text-gray-600">{ward.total_tickets}</td>
                                                <td className="px-6 py-4 text-center text-sm text-green-600 font-medium">{ward.resolved_tickets}</td>
                                                <td className="px-6 py-4 text-center">
                                                    <div className="flex items-center justify-center gap-3">
                                                        <div className="w-24 h-2 bg-gray-100 rounded-full overflow-hidden">
                                                            <div
                                                                className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full"
                                                                style={{ width: `${ward.resolution_rate}%` }}
                                                            />
                                                        </div>
                                                        <span className="text-sm font-semibold text-gray-800">{ward.resolution_rate}%</span>
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 text-center">
                                                    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${grade.color}`}>
                                                        {grade.label}
                                                    </span>
                                                </td>
                                            </motion.tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
