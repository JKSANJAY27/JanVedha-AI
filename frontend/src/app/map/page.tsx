"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { publicApi } from "@/lib/api";
import { PRIORITY_COLORS, PRIORITY_EMOJI, DEPT_NAMES } from "@/lib/constants";
import PriorityBadge from "@/components/PriorityBadge";
import StatusBadge from "@/components/StatusBadge";
import { formatRelative } from "@/lib/formatters";

// Load Leaflet map only on client side to prevent SSR errors
const MapComponent = dynamic(() => import("@/features/map/IssueMap"), { ssr: false });

interface MapIssue {
    id: string;
    ticket_code: string;
    description: string;
    dept_id: string;
    priority_label: string;
    priority_score: number;
    status: string;
    lat?: number;
    lng?: number;
    location?: { lat?: number; lng?: number; address?: string };
    created_at: string;
    photo_url?: string;
}

const PRIORITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const STATUSES_MAP = ["OPEN", "IN_PROGRESS", "ASSIGNED", "CLOSED"];

export default function MapPage() {
    const [issues, setIssues] = useState<MapIssue[]>([]);
    const [loading, setLoading] = useState(true);
    const [priorityFilter, setPriorityFilter] = useState<string[]>(["CRITICAL", "HIGH"]);
    const [statusFilter, setStatusFilter] = useState<string[]>(["OPEN", "IN_PROGRESS", "ASSIGNED"]);
    const [selectedIssue, setSelectedIssue] = useState<MapIssue | null>(null);

    useEffect(() => {
        publicApi.getHeatmap()
            .then((res) => {
                // Normalise heatmap data for the map
                const normalized = (res.data || []).map((item: any) => ({
                    ...item,
                    lat: item.location?.lat ?? undefined,
                    lng: item.location?.lng ?? undefined,
                }));
                setIssues(normalized);
            })
            .catch(() => { })
            .finally(() => setLoading(false));
    }, []);

    const filtered = issues.filter((i) => {
        const hasCords = i.lat && i.lng;
        if (!hasCords) return false;
        if (!priorityFilter.includes(i.priority_label)) return false;
        if (!statusFilter.includes(i.status)) return false;
        return true;
    });

    const toggleFilter = (arr: string[], val: string, setter: (a: string[]) => void) => {
        setter(arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val]);
    };

    return (
        <div className="h-[calc(100vh-4rem)] flex flex-col">
            {/* Filter bar */}
            <div className="bg-white border-b border-gray-200 px-4 py-3 flex flex-wrap items-center gap-4 z-20 shadow-sm">
                <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Priority:</span>
                    {PRIORITIES.map((p) => (
                        <button
                            key={p}
                            onClick={() => toggleFilter(priorityFilter, p, setPriorityFilter)}
                            className={`text-xs px-3 py-1.5 rounded-full font-medium border transition-all ${priorityFilter.includes(p)
                                    ? "border-transparent text-white"
                                    : "border-gray-200 text-gray-400 bg-gray-50"
                                }`}
                            style={priorityFilter.includes(p) ? { backgroundColor: PRIORITY_COLORS[p] } : {}}
                        >
                            {PRIORITY_EMOJI[p]} {p}
                        </button>
                    ))}
                </div>

                <div className="w-px h-5 bg-gray-200 hidden sm:block" />

                <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Status:</span>
                    {STATUSES_MAP.map((s) => (
                        <button
                            key={s}
                            onClick={() => toggleFilter(statusFilter, s, setStatusFilter)}
                            className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all ${statusFilter.includes(s)
                                    ? "bg-blue-600 text-white border-blue-600"
                                    : "border border-gray-200 text-gray-400 bg-gray-50"
                                }`}
                        >
                            {s.replace(/_/g, " ")}
                        </button>
                    ))}
                </div>

                <div className="ml-auto text-sm text-gray-500 font-medium">
                    {loading ? "Loading…" : `${filtered.length} issues shown`}
                </div>
            </div>

            {/* Map + sidebar */}
            <div className="flex flex-1 overflow-hidden">
                {/* Map */}
                <div className="flex-1 relative">
                    {loading ? (
                        <div className="flex items-center justify-center h-full bg-gray-100">
                            <div className="text-center">
                                <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-3" />
                                <p className="text-gray-500">Loading issue map…</p>
                            </div>
                        </div>
                    ) : (
                        <MapComponent
                            issues={filtered}
                            onIssueClick={(issue) => setSelectedIssue(issue)}
                        />
                    )}
                </div>

                {/* Issue detail sidebar */}
                {selectedIssue && (
                    <div className="w-72 bg-white border-l border-gray-200 p-5 overflow-y-auto flex-shrink-0">
                        <div className="flex items-start justify-between mb-4">
                            <p className="font-mono font-bold text-blue-700 text-sm">{selectedIssue.ticket_code}</p>
                            <button onClick={() => setSelectedIssue(null)} className="text-gray-400 hover:text-gray-700 text-lg">✕</button>
                        </div>
                        <div className="flex gap-2 mb-4 flex-wrap">
                            <PriorityBadge label={selectedIssue.priority_label} score={selectedIssue.priority_score} size="sm" />
                            <StatusBadge status={selectedIssue.status} size="sm" />
                        </div>
                        <p className="text-sm text-gray-700 mb-3 leading-relaxed">{selectedIssue.description}</p>
                        <div className="space-y-2 text-xs text-gray-500">
                            <div className="flex justify-between">
                                <span>Department</span>
                                <span className="font-medium">{DEPT_NAMES[selectedIssue.dept_id] ?? selectedIssue.dept_id}</span>
                            </div>
                            <div className="flex justify-between">
                                <span>Submitted</span>
                                <span className="font-medium">{formatRelative(selectedIssue.created_at)}</span>
                            </div>
                        </div>
                        <a
                            href={`/track/${selectedIssue.ticket_code}`}
                            className="mt-4 block text-center bg-blue-600 text-white rounded-xl py-2 text-sm font-semibold hover:bg-blue-700 transition-colors"
                        >
                            Track Ticket →
                        </a>
                    </div>
                )}
            </div>

            {/* Legend */}
            <div className="absolute bottom-8 left-4 bg-white/90 backdrop-blur rounded-2xl shadow-lg border border-gray-100 p-3 z-10">
                <p className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">Legend</p>
                {PRIORITIES.map((p) => (
                    <div key={p} className="flex items-center gap-2 mb-1">
                        <span className="text-base">{PRIORITY_EMOJI[p]}</span>
                        <span className="text-xs text-gray-600">{p}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
