"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { analyticsApi } from "@/lib/api";

interface TechLoad {
    technician_id: string;
    name: string;
    dept_id: string;
    open_tickets: number;
    is_overloaded: boolean;
}

interface DeptMetric {
    dept_id: string;
    dept_name: string;
    avg_resolution_days: number | null;
    open_tickets: number;
    resolved_tickets: number;
    skill_gap: boolean;
    open_7d: number;
    resolved_7d: number;
}

interface ResourceHealthData {
    ward_id: number | null;
    technician_loads: TechLoad[];
    dept_metrics: DeptMetric[];
    avg_load: number;
    overload_threshold: number;
    ai_summary: string;
}

interface Props {
    wardId?: number;
}

export default function ResourceHealthCard({ wardId }: Props) {
    const [data, setData] = useState<ResourceHealthData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        analyticsApi.getResourceHealth(wardId)
            .then(r => setData(r.data))
            .catch(() => setError("Failed to load resource health data"))
            .finally(() => setLoading(false));
    }, [wardId]);

    if (loading) {
        return (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                <div className="flex items-center gap-2 mb-4">
                    <span className="text-xl">⚙️</span>
                    <h2 className="font-bold text-gray-800 text-sm">Resource Health</h2>
                    <span className="ml-2 text-xs bg-violet-100 text-violet-700 font-semibold px-2 py-0.5 rounded-full">AI-Powered</span>
                </div>
                <div className="space-y-3 animate-pulse">
                    <div className="h-4 bg-gray-100 rounded w-3/4" />
                    <div className="h-4 bg-gray-100 rounded w-full" />
                    <div className="h-4 bg-gray-100 rounded w-2/3" />
                </div>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                <div className="flex items-center gap-2 mb-2">
                    <span className="text-xl">⚙️</span>
                    <h2 className="font-bold text-gray-800 text-sm">Resource Health</h2>
                </div>
                <p className="text-sm text-red-400 italic">{error ?? "No data available"}</p>
            </div>
        );
    }

    const overloadedTechs = data.technician_loads.filter(t => t.is_overloaded);
    const gapDepts = data.dept_metrics.filter(d => d.skill_gap);
    const maxLoad = Math.max(...data.technician_loads.map(t => t.open_tickets), 1);

    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden"
        >
            {/* Header */}
            <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">⚙️</span>
                <h2 className="font-bold text-gray-800 text-sm">Resource Health & Optimizer</h2>
                <span className="ml-auto text-xs bg-violet-100 text-violet-700 font-semibold px-2 py-0.5 rounded-full">Gemini AI</span>
            </div>

            <div className="p-5 space-y-6">
                {/* AI Summary */}
                <div className="bg-gradient-to-br from-violet-50 to-indigo-50 border border-violet-100 rounded-xl p-4">
                    <div className="flex items-center gap-1.5 mb-2">
                        <span className="text-base">🤖</span>
                        <p className="text-xs font-bold text-violet-700 uppercase tracking-wide">AI Executive Summary</p>
                    </div>
                    <p className="text-sm text-gray-700 leading-relaxed">{data.ai_summary}</p>
                </div>

                {/* Two-column layout: Technician loads + Dept skill gaps */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                    {/* Technician Load */}
                    <div>
                        <div className="flex items-center gap-1.5 mb-3">
                            <span className="text-sm">👷</span>
                            <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Technician Load</h3>
                            <span className="text-xs text-gray-400">avg: {data.avg_load} tickets</span>
                        </div>
                        {data.technician_loads.length === 0 ? (
                            <p className="text-xs text-gray-400 italic py-2">No technicians found in this ward.</p>
                        ) : (
                            <div className="space-y-2.5">
                                {data.technician_loads.slice(0, 6).map((tech, i) => (
                                    <motion.div
                                        key={tech.technician_id}
                                        initial={{ opacity: 0, x: -8 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: i * 0.05 }}
                                    >
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="text-xs text-gray-700 font-medium truncate max-w-[130px]">
                                                {tech.name}
                                            </span>
                                            <div className="flex items-center gap-1.5 shrink-0">
                                                {tech.is_overloaded && (
                                                    <span className="text-[9px] bg-red-100 text-red-700 font-bold px-1.5 py-0.5 rounded border border-red-200">
                                                        OVERLOADED
                                                    </span>
                                                )}
                                                <span className={`text-xs font-bold ${tech.is_overloaded ? "text-red-600" : "text-gray-600"}`}>
                                                    {tech.open_tickets}
                                                </span>
                                            </div>
                                        </div>
                                        <div className="w-full bg-gray-100 rounded-full h-1.5">
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: `${(tech.open_tickets / maxLoad) * 100}%` }}
                                                transition={{ delay: i * 0.06, duration: 0.5 }}
                                                className={`h-1.5 rounded-full ${tech.is_overloaded
                                                    ? "bg-gradient-to-r from-red-400 to-rose-500"
                                                    : "bg-gradient-to-r from-blue-400 to-indigo-500"
                                                    }`}
                                            />
                                        </div>
                                    </motion.div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Department skill gaps */}
                    <div>
                        <div className="flex items-center gap-1.5 mb-3">
                            <span className="text-sm">🏢</span>
                            <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Dept Resolution (30d)</h3>
                        </div>
                        {data.dept_metrics.length === 0 ? (
                            <p className="text-xs text-gray-400 italic py-2">No department data available.</p>
                        ) : (
                            <div className="space-y-2">
                                {data.dept_metrics.slice(0, 6).map((dept, i) => (
                                    <motion.div
                                        key={dept.dept_id}
                                        initial={{ opacity: 0, x: 8 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: i * 0.05 }}
                                        className="flex items-center justify-between gap-2 py-1.5 border-b border-gray-50 last:border-0"
                                    >
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-1">
                                                {dept.skill_gap && (
                                                    <span title="Skill gap: more tickets opening than resolving">⚠️</span>
                                                )}
                                                <span className="text-xs text-gray-700 font-medium truncate">
                                                    {dept.dept_name}
                                                </span>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2 shrink-0">
                                            <span className={`text-xs font-bold ${dept.avg_resolution_days && dept.avg_resolution_days > 5
                                                ? "text-red-600" : "text-emerald-600"
                                                }`}>
                                                {dept.avg_resolution_days !== null
                                                    ? `${dept.avg_resolution_days}d`
                                                    : "—"}
                                            </span>
                                            <span className="text-[10px] text-gray-400">
                                                {dept.open_tickets} open
                                            </span>
                                        </div>
                                    </motion.div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Skill gap summary pills */}
                {gapDepts.length > 0 && (
                    <div className="bg-amber-50 border border-amber-100 rounded-xl p-3">
                        <p className="text-xs font-bold text-amber-700 mb-2">⚠️ Skill Gaps (7-day window: more opening than closing)</p>
                        <div className="flex flex-wrap gap-1.5">
                            {gapDepts.map(d => (
                                <span key={d.dept_id} className="text-xs bg-amber-100 text-amber-800 font-semibold px-2 py-0.5 rounded-full border border-amber-200">
                                    {d.dept_name} ({d.open_7d} open vs {d.resolved_7d} resolved)
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {overloadedTechs.length === 0 && gapDepts.length === 0 && (
                    <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-100 rounded-xl p-3">
                        <span className="text-lg">✅</span>
                        <p className="text-sm text-emerald-700 font-medium">All technician loads are balanced and within normal range.</p>
                    </div>
                )}
            </div>
        </motion.div>
    );
}
