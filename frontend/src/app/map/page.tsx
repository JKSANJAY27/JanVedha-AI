"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import { publicApi } from "@/lib/api";
import { PRIORITY_COLORS, PRIORITY_EMOJI, DEPT_NAMES } from "@/lib/constants";
import PriorityBadge from "@/components/PriorityBadge";
import StatusBadge from "@/components/StatusBadge";
import { formatRelative } from "@/lib/formatters";
import { useAuth } from "@/context/AuthContext";

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
const REFRESH_INTERVAL_MS = 30_000; // auto-refresh every 30 seconds

export default function MapPage() {
    const auth = useAuth();
    const deptId = auth.isJuniorEngineer ? auth.user?.dept_id : undefined;

    const [issues, setIssues] = useState<MapIssue[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    // Default: show all priorities and statuses so every ticket is visible
    const [priorityFilter, setPriorityFilter] = useState<string[]>(["CRITICAL", "HIGH", "MEDIUM", "LOW"]);
    const [statusFilter, setStatusFilter] = useState<string[]>(["OPEN", "IN_PROGRESS", "ASSIGNED", "CLOSED"]);
    const [selectedIssue, setSelectedIssue] = useState<MapIssue | null>(null);
    const intervalRef = useRef<NodeJS.Timeout | null>(null);

    const fetchIssues = useCallback(async (isInitial = false) => {
        if (auth.loading) return;
        if (!isInitial) setRefreshing(true);
        try {
            const res = await publicApi.getHeatmap(deptId);
            // API returns { data: [...] }, Axios wraps HTTP body in res.data
            const items: any[] = res.data?.data || res.data || [];
            const normalized = items.map((item: any) => ({
                ...item,
                lat: item.location?.lat ?? item.lat ?? undefined,
                lng: item.location?.lng ?? item.lng ?? undefined,
            }));
            setIssues(normalized);
            setLastUpdated(new Date());
        } catch {
            // silent — keep showing stale data
        } finally {
            if (isInitial) setLoading(false);
            else setRefreshing(false);
        }
    }, [auth.loading, deptId]);

    // Initial load
    useEffect(() => {
        fetchIssues(true);
    }, [fetchIssues]);

    // Auto-refresh every 30 s
    useEffect(() => {
        intervalRef.current = setInterval(() => fetchIssues(false), REFRESH_INTERVAL_MS);
        return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
    }, [fetchIssues]);

    // Refresh when tab becomes visible again (user switches back from submit page)
    useEffect(() => {
        const handleVisibility = () => {
            if (document.visibilityState === "visible") fetchIssues(false);
        };
        document.addEventListener("visibilitychange", handleVisibility);
        return () => document.removeEventListener("visibilitychange", handleVisibility);
    }, [fetchIssues]);


    const filtered = useMemo(() => {
        return issues.filter((i) => {
            const hasCords = i.lat && i.lng;
            if (!hasCords) return false;
            if (!priorityFilter.includes(i.priority_label)) return false;
            if (!statusFilter.includes(i.status)) return false;
            return true;
        });
    }, [issues, priorityFilter, statusFilter]);

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

                <div className="ml-auto flex items-center gap-3">
                    {/* Live indicator */}
                    <div className="flex items-center gap-1.5 text-xs text-gray-500">
                        <span className={`w-2 h-2 rounded-full ${refreshing ? "bg-yellow-400 animate-pulse" : "bg-green-400 animate-pulse"}`} />
                        {loading ? "Loading…" : `${filtered.length} issues`}
                        {lastUpdated && !loading && (
                            <span className="text-gray-400 hidden sm:inline">
                                · updated {lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                            </span>
                        )}
                    </div>
                    {/* Manual refresh */}
                    <button
                        onClick={() => fetchIssues(false)}
                        disabled={refreshing || loading}
                        title="Refresh map"
                        className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors disabled:opacity-40"
                    >
                        <svg className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                    </button>
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
