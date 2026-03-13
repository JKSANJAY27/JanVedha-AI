"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { analyticsApi } from "@/lib/api";
import { DEPT_NAMES } from "@/lib/constants";

const SCENARIO_TYPES = [
    { value: "move_technicians", label: "Move technicians between departments" },
    { value: "add_technicians", label: "Add new technicians to a department" },
    { value: "deprioritize_dept", label: "Deprioritize a department temporarily" },
];

interface Props {
    wardId?: number;
}

interface AnalysisResult {
    scenario: {
        description: string;
        dept_to_name: string;
        dept_from_name: string;
        n_technicians: number;
        duration_weeks: number;
    };
    baseline: Array<{
        dept_name: string;
        avg_resolution_days: number | null;
        open_tickets: number;
        technician_count: number;
        weekly_arrival_rate: number;
    }>;
    ai_analysis: string;
}

const DEPT_OPTIONS = [
    { value: "roads", label: "Roads & Infrastructure" },
    { value: "water", label: "Water Supply" },
    { value: "electrical", label: "Electrical" },
    { value: "sanitation", label: "Sanitation & Waste" },
    { value: "parks", label: "Parks & Environment" },
    { value: "storm_drain", label: "Storm Drains" },
    { value: "buildings", label: "Buildings" },
    { value: "health", label: "Health" },
];

export default function ScenarioPlanner({ wardId }: Props) {
    const [scenarioType, setScenarioType] = useState("move_technicians");
    const [deptTo, setDeptTo] = useState("roads");
    const [deptFrom, setDeptFrom] = useState("electrical");
    const [nTech, setNTech] = useState(1);
    const [durationWeeks, setDurationWeeks] = useState(2);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<AnalysisResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const needsFrom = scenarioType === "move_technicians";

    const handleAnalyze = async () => {
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            const resp = await analyticsApi.analyzeScenario({
                scenario_type: scenarioType,
                dept_to: deptTo,
                dept_from: needsFrom ? deptFrom : undefined,
                n_technicians: nTech,
                duration_weeks: durationWeeks,
                ward_id: wardId,
            });
            setResult(resp.data);
        } catch {
            setError("Analysis failed. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            {/* Header */}
            <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">🔮</span>
                <h2 className="font-bold text-gray-800 text-sm">"What If" Scenario Planner</h2>
                <span className="ml-auto text-xs bg-indigo-100 text-indigo-700 font-semibold px-2 py-0.5 rounded-full">Gemini Reasoning</span>
            </div>

            <div className="p-5 space-y-5">
                <p className="text-xs text-gray-500">
                    Select a scenario, configure the parameters, and get an AI-reasoned impact analysis grounded in your current ticket data.
                </p>

                {/* Form */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Scenario type */}
                    <div className="sm:col-span-2">
                        <label className="block text-xs font-semibold text-gray-600 mb-1.5">Scenario</label>
                        <select
                            value={scenarioType}
                            onChange={e => setScenarioType(e.target.value)}
                            className="w-full text-sm border border-gray-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-gray-50"
                        >
                            {SCENARIO_TYPES.map(s => (
                                <option key={s.value} value={s.value}>{s.label}</option>
                            ))}
                        </select>
                    </div>

                    {/* Target dept */}
                    <div>
                        <label className="block text-xs font-semibold text-gray-600 mb-1.5">
                            {scenarioType === "deprioritize_dept" ? "Deprioritize Department" : "Target Department (receiving help)"}
                        </label>
                        <select
                            value={deptTo}
                            onChange={e => setDeptTo(e.target.value)}
                            className="w-full text-sm border border-gray-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-gray-50"
                        >
                            {DEPT_OPTIONS.map(d => (
                                <option key={d.value} value={d.value}>{d.label}</option>
                            ))}
                        </select>
                    </div>

                    {/* Source dept (only for move scenario) */}
                    {needsFrom && (
                        <div>
                            <label className="block text-xs font-semibold text-gray-600 mb-1.5">Source Department (losing staff)</label>
                            <select
                                value={deptFrom}
                                onChange={e => setDeptFrom(e.target.value)}
                                className="w-full text-sm border border-gray-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-gray-50"
                            >
                                {DEPT_OPTIONS.filter(d => d.value !== deptTo).map(d => (
                                    <option key={d.value} value={d.value}>{d.label}</option>
                                ))}
                            </select>
                        </div>
                    )}

                    {/* N technicians */}
                    <div>
                        <label className="block text-xs font-semibold text-gray-600 mb-1.5">
                            {scenarioType === "deprioritize_dept" ? "Reduced capacity" : "Number of technicians"}
                        </label>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => setNTech(Math.max(1, nTech - 1))}
                                className="w-8 h-8 rounded-lg bg-gray-100 text-gray-600 font-bold text-sm hover:bg-gray-200 transition"
                            >−</button>
                            <span className="text-xl font-bold text-indigo-700 w-8 text-center">{nTech}</span>
                            <button
                                onClick={() => setNTech(Math.min(10, nTech + 1))}
                                className="w-8 h-8 rounded-lg bg-gray-100 text-gray-600 font-bold text-sm hover:bg-gray-200 transition"
                            >+</button>
                        </div>
                    </div>

                    {/* Duration */}
                    <div>
                        <label className="block text-xs font-semibold text-gray-600 mb-1.5">Duration (weeks)</label>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => setDurationWeeks(Math.max(1, durationWeeks - 1))}
                                className="w-8 h-8 rounded-lg bg-gray-100 text-gray-600 font-bold text-sm hover:bg-gray-200 transition"
                            >−</button>
                            <span className="text-xl font-bold text-indigo-700 w-8 text-center">{durationWeeks}</span>
                            <button
                                onClick={() => setDurationWeeks(Math.min(12, durationWeeks + 1))}
                                className="w-8 h-8 rounded-lg bg-gray-100 text-gray-600 font-bold text-sm hover:bg-gray-200 transition"
                            >+</button>
                        </div>
                    </div>
                </div>

                {/* Analyze button */}
                <button
                    onClick={handleAnalyze}
                    disabled={loading}
                    className={`w-full py-3 rounded-xl text-sm font-bold transition-all ${loading
                        ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                        : "bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:shadow-lg hover:shadow-indigo-200 active:scale-[0.98]"
                        }`}
                >
                    {loading ? (
                        <span className="flex items-center justify-center gap-2">
                            <span className="w-4 h-4 border-2 border-gray-300 border-t-gray-500 rounded-full animate-spin" />
                            Analyzing with Gemini…
                        </span>
                    ) : "🔮 Analyze Impact"}
                </button>

                {error && (
                    <p className="text-sm text-red-500 italic text-center">{error}</p>
                )}

                {/* Result Panel */}
                <AnimatePresence>
                    {result && (
                        <motion.div
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -8 }}
                            className="space-y-4"
                        >
                            {/* Scenario recap */}
                            <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-3">
                                <p className="text-xs font-bold text-indigo-600 uppercase tracking-wide mb-1">Scenario</p>
                                <p className="text-sm text-gray-700">{result.scenario.description}</p>
                            </div>

                            {/* Baseline mini-table */}
                            {result.baseline.length > 0 && (
                                <div>
                                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">Baseline Data Used</p>
                                    <div className="grid grid-cols-2 gap-2">
                                        {result.baseline.map(d => (
                                            <div key={d.dept_name} className="bg-gray-50 rounded-xl p-3 border border-gray-100">
                                                <p className="text-xs font-bold text-gray-700">{d.dept_name}</p>
                                                <div className="mt-1 space-y-0.5">
                                                    <p className="text-[10px] text-gray-500">
                                                        Avg resolve: <span className="font-bold text-gray-700">{d.avg_resolution_days ?? "N/A"}d</span>
                                                    </p>
                                                    <p className="text-[10px] text-gray-500">
                                                        Open tickets: <span className="font-bold text-gray-700">{d.open_tickets}</span>
                                                    </p>
                                                    <p className="text-[10px] text-gray-500">
                                                        Technicians: <span className="font-bold text-gray-700">{d.technician_count}</span>
                                                    </p>
                                                    <p className="text-[10px] text-gray-500">
                                                        Arrival/wk: <span className="font-bold text-gray-700">~{d.weekly_arrival_rate}</span>
                                                    </p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* AI Analysis */}
                            <div className="bg-gradient-to-br from-violet-50 to-indigo-50 border border-violet-100 rounded-xl p-4">
                                <div className="flex items-center gap-1.5 mb-3">
                                    <span className="text-base">🤖</span>
                                    <p className="text-xs font-bold text-violet-700 uppercase tracking-wide">Gemini Impact Analysis</p>
                                </div>
                                <div className="space-y-2">
                                    {result.ai_analysis.split("\n\n").map((para, i) => (
                                        <p key={i} className="text-sm text-gray-700 leading-relaxed">{para}</p>
                                    ))}
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}
