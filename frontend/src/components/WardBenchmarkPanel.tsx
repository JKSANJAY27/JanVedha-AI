"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { analyticsApi } from "@/lib/api";

interface WardMetric {
    ward_id: number | null;
    ward_name: string;
    avg_resolution_days_by_dept: Record<string, number>;
    overall_avg_resolution_days: number | null;
    ticket_volume: number;
    resolution_rate_pct: number;
}

interface PeerWard {
    ward_name: string;
    ward_id: number;
    avg_resolution_days_by_dept: Record<string, number>;
    overall_avg_resolution_days: number | null;
    ticket_volume: number;
    resolution_rate_pct: number;
    top_practice: string;
}

interface BenchmarkData {
    current_ward: WardMetric;
    peer_wards: PeerWard[];
    ai_insight: string;
}

interface Props {
    wardId?: number;
}

// Parse the 3-bullet AI insight into structured points
function parseBullets(text: string): string[] {
    return text
        .split("\n")
        .map(l => l.trim())
        .filter(l => l.startsWith("-"))
        .map(l => l.slice(1).trim());
}

const BULLET_ICONS = ["🏆", "💡", "✅"];
const BULLET_COLORS = [
    "bg-emerald-50 border-emerald-100 text-emerald-800",
    "bg-blue-50 border-blue-100 text-blue-800",
    "bg-amber-50 border-amber-100 text-amber-800",
];

export default function WardBenchmarkPanel({ wardId }: Props) {
    const [data, setData] = useState<BenchmarkData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        analyticsApi.getBenchmarks(wardId)
            .then(r => setData(r.data))
            .catch(() => setError("Failed to load benchmark data"))
            .finally(() => setLoading(false));
    }, [wardId]);

    if (loading) {
        return (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                <div className="flex items-center gap-2 mb-4">
                    <span className="text-xl">📊</span>
                    <h2 className="font-bold text-gray-800 text-sm">Cross-Ward Benchmarking</h2>
                </div>
                <div className="space-y-3 animate-pulse">
                    <div className="h-4 bg-gray-100 rounded w-full" />
                    <div className="h-4 bg-gray-100 rounded w-5/6" />
                    <div className="h-28 bg-gray-50 rounded-xl" />
                </div>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                <div className="flex items-center gap-2 mb-2">
                    <span className="text-xl">📊</span>
                    <h2 className="font-bold text-gray-800 text-sm">Cross-Ward Benchmarking</h2>
                </div>
                <p className="text-sm text-red-400 italic">{error ?? "No data"}</p>
            </div>
        );
    }

    const bullets = parseBullets(data.ai_insight);
    const rawText = bullets.length < 2 ? data.ai_insight : null;

    // Build chart data: all wards + current
    const allWards = [
        {
            name: data.current_ward.ward_name ?? "Your Ward",
            avg: data.current_ward.overall_avg_resolution_days,
            rate: data.current_ward.resolution_rate_pct,
            volume: data.current_ward.ticket_volume,
            isCurrent: true,
        },
        ...data.peer_wards.map(pw => ({
            name: pw.ward_name,
            avg: pw.overall_avg_resolution_days,
            rate: pw.resolution_rate_pct,
            volume: pw.ticket_volume,
            isCurrent: false,
        })),
    ];

    const maxAvg = Math.max(...allWards.map(w => w.avg ?? 0), 1);

    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden"
        >
            {/* Header */}
            <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📊</span>
                <h2 className="font-bold text-gray-800 text-sm">Cross-Ward Benchmarking</h2>
                <span className="ml-auto text-xs bg-teal-100 text-teal-700 font-semibold px-2 py-0.5 rounded-full">Peer Insights</span>
            </div>

            <div className="p-5 space-y-5">
                {/* Bar chart: avg resolution days */}
                <div>
                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-3">
                        Avg Resolution Days — Your Ward vs Peers
                    </p>
                    <div className="space-y-3">
                        {allWards.map((ward, i) => (
                            <motion.div
                                key={ward.name}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: i * 0.07 }}
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <div className="flex items-center gap-1.5">
                                        {ward.isCurrent && (
                                            <span className="text-[9px] bg-indigo-600 text-white font-bold px-1.5 py-0.5 rounded">YOU</span>
                                        )}
                                        <span className={`text-xs font-medium ${ward.isCurrent ? "text-indigo-700" : "text-gray-600"}`}>
                                            {ward.name}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2 text-xs text-gray-500">
                                        <span className="font-bold text-gray-700">
                                            {ward.avg !== null ? `${ward.avg}d` : "—"}
                                        </span>
                                        <span>{ward.rate}% resolved</span>
                                    </div>
                                </div>
                                <div className="w-full bg-gray-100 rounded-full h-3">
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: ward.avg !== null ? `${((ward.avg / maxAvg) * 100)}%` : "0%" }}
                                        transition={{ delay: i * 0.08, duration: 0.6, ease: "easeOut" }}
                                        className={`h-3 rounded-full ${ward.isCurrent
                                            ? "bg-gradient-to-r from-indigo-500 to-violet-600"
                                            : "bg-gradient-to-r from-teal-400 to-emerald-500"
                                            }`}
                                    />
                                </div>
                            </motion.div>
                        ))}
                    </div>
                    <p className="text-[10px] text-gray-400 mt-2">Lower is better — shorter bars mean faster resolution ✓</p>
                </div>

                {/* AI Insight bullets */}
                <div>
                    <div className="flex items-center gap-1.5 mb-3">
                        <span className="text-base">🤖</span>
                        <p className="text-xs font-bold text-gray-600 uppercase tracking-wide">Gemini Peer Insight</p>
                    </div>

                    {rawText ? (
                        <div className="bg-teal-50 border border-teal-100 rounded-xl p-4">
                            <p className="text-sm text-gray-700 leading-relaxed">{rawText}</p>
                        </div>
                    ) : (
                        <div className="space-y-2.5">
                            {bullets.map((b, i) => (
                                <motion.div
                                    key={i}
                                    initial={{ opacity: 0, x: -8 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.1 + i * 0.1 }}
                                    className={`flex items-start gap-2.5 rounded-xl border p-3 ${BULLET_COLORS[i] ?? "bg-gray-50 border-gray-100 text-gray-700"}`}
                                >
                                    <span className="text-base mt-0.5 shrink-0">{BULLET_ICONS[i] ?? "•"}</span>
                                    <p className="text-xs leading-relaxed">{b}</p>
                                </motion.div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Best practice card from top performer */}
                {data.peer_wards.length > 0 && (() => {
                    const best = [...data.peer_wards].sort((a, b) =>
                        (a.overall_avg_resolution_days ?? 999) - (b.overall_avg_resolution_days ?? 999)
                    )[0];
                    return best?.top_practice ? (
                        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-2">
                                <span className="text-base">🌟</span>
                                <p className="text-xs font-bold text-emerald-700">Top Practice from {best.ward_name}</p>
                            </div>
                            <p className="text-xs text-emerald-800 leading-relaxed">{best.top_practice}</p>
                        </div>
                    ) : null;
                })()}
            </div>
        </motion.div>
    );
}
