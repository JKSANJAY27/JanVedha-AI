"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";
import { calendarApi, officerApi } from "@/lib/api";
import CalendarWidget, { CalendarEvent } from "@/components/CalendarWidget";
import { DEPT_NAMES } from "@/lib/constants";
import Link from "next/link";

interface Suggestion {
    ticket_id: string;
    ticket_code: string;
    suggested_date: string;
    priority_label: string;
    priority_score: number;
    issue_category?: string;
}

export default function OfficerCalendarPage() {
    const { user, isOfficer } = useAuth();
    const router = useRouter();

    const [events, setEvents] = useState<CalendarEvent[]>([]);
    const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
    const [loading, setLoading] = useState(true);
    const [aiLoading, setAiLoading] = useState(false);
    const [applying, setApplying] = useState(false);
    const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);

    const now = new Date();
    const [month, setMonth] = useState(now.getMonth() + 1);
    const [year] = useState(now.getFullYear());

    const loadEvents = useCallback(async () => {
        if (!user) return;
        setLoading(true);
        try {
            const params: Record<string, unknown> = { month, year };
            if (user.dept_id) params.dept_id = user.dept_id;
            if (user.ward_id) params.ward_id = user.ward_id;
            const res = await calendarApi.getEvents(params as Parameters<typeof calendarApi.getEvents>[0]);
            setEvents(res.data);
        } catch {
            toast.error("Failed to load calendar events");
        } finally {
            setLoading(false);
        }
    }, [user, month, year]);

    useEffect(() => {
        if (!isOfficer) { router.push("/login"); return; }
        // Calendar is for Junior Engineers only — supervisors no longer schedule
        if (user?.role && user.role !== "JUNIOR_ENGINEER") {
            router.push("/officer/dashboard");
            return;
        }
        loadEvents();
    }, [isOfficer, router, loadEvents, user?.role]);

    const getAISuggestions = async () => {
        if (!user?.dept_id || !user?.ward_id) {
            toast.error("Department or ward information missing");
            return;
        }
        setAiLoading(true);
        setSuggestions([]);
        try {
            const res = await calendarApi.getAISuggestions(user.dept_id, user.ward_id);
            setSuggestions(res.data.suggestions ?? []);
            toast.success(`${res.data.suggestions?.length ?? 0} AI scheduling suggestions ready`);
        } catch {
            toast.error("AI suggestion failed");
        } finally {
            setAiLoading(false);
        }
    };

    const applyAllSuggestions = async () => {
        if (!user?.dept_id || !user?.ward_id) return;
        setApplying(true);
        try {
            const res = await calendarApi.applyAISuggestions(user.dept_id, user.ward_id);
            toast.success(`Applied ${res.data.applied} schedules!`);
            setSuggestions([]);
            loadEvents();
        } catch {
            toast.error("Failed to apply suggestions");
        } finally {
            setApplying(false);
        }
    };

    const PRIORITY_BADGE: Record<string, string> = {
        CRITICAL: "bg-red-100 text-red-700 border border-red-200",
        HIGH: "bg-orange-100 text-orange-700 border border-orange-200",
        MEDIUM: "bg-yellow-100 text-yellow-700 border border-yellow-200",
        LOW: "bg-green-100 text-green-700 border border-green-200",
    };

    return (
        <div className="min-h-screen bg-slate-50">
            {/* Header */}
            <div className="bg-gradient-to-r from-indigo-800 to-purple-900 text-white px-6 py-6">
                <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
                    <div>
                        <p className="text-indigo-300 text-sm">
                            {user?.role?.replace(/_/g, " ")} — {user?.dept_id ? DEPT_NAMES[user.dept_id] ?? user.dept_id : ""} {user?.ward_id && `· Ward ${user.ward_id}`}
                        </p>
                        <h1 className="text-2xl font-bold mt-0.5">📅 Department Scheduling Calendar</h1>
                    </div>
                    <div className="flex gap-3">
                        <Link href="/officer/dashboard" className="text-sm bg-white/10 border border-white/20 text-white px-4 py-2 rounded-lg hover:bg-white/20 transition-colors">
                            ← Dashboard
                        </Link>
                        <button
                            onClick={getAISuggestions}
                            disabled={aiLoading}
                            className="text-sm bg-purple-500 hover:bg-purple-400 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 disabled:opacity-60"
                        >
                            {aiLoading ? <span className="animate-spin">⏳</span> : "✨"} AI Suggest Dates
                        </button>
                    </div>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Calendar */}
                <div className="lg:col-span-2">
                    {loading ? (
                        <div className="flex items-center justify-center h-96">
                            <div className="w-10 h-10 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
                        </div>
                    ) : (
                        <CalendarWidget
                            events={events}
                            month={month - 1}
                            year={year}
                            onEventClick={setSelectedEvent}
                        />
                    )}

                    {/* Event detail popover */}
                    {selectedEvent && (
                        <div className="mt-4 bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
                            <div className="flex items-start justify-between mb-3">
                                <div>
                                    <span className="font-mono font-bold text-indigo-700 text-sm">{selectedEvent.ticket_code}</span>
                                    {selectedEvent.event_type === "deadline" && (
                                        <span className="ml-2 text-xs bg-pink-100 text-pink-700 px-2 py-0.5 rounded-full font-semibold">🔔 Deadline Reminder</span>
                                    )}
                                    {selectedEvent.event_type !== "deadline" && selectedEvent.is_ai_suggested && (
                                        <span className="ml-2 text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">✨ AI Suggested</span>
                                    )}
                                </div>
                                <button onClick={() => setSelectedEvent(null)} className="text-gray-400 hover:text-gray-600 text-lg leading-none">✕</button>
                            </div>

                            {selectedEvent.event_type === "deadline" ? (
                                <>
                                    <p className="text-sm font-semibold text-pink-700 mb-1">⏰ Work must be completed by:</p>
                                    <p className="text-base font-bold text-gray-800 mb-2">
                                        {new Date(selectedEvent.scheduled_date).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
                                    </p>
                                    {selectedEvent.ticket_description && (
                                        <p className="text-xs text-gray-500 italic mb-2 line-clamp-2">{selectedEvent.ticket_description}</p>
                                    )}
                                    {selectedEvent.notes && (
                                        <p className="text-xs text-gray-400 border-t pt-2 mt-2">{selectedEvent.notes}</p>
                                    )}
                                </>
                            ) : (
                                <>
                                    <p className="text-sm text-gray-700 font-medium">{selectedEvent.issue_category ?? "General Issue"}</p>
                                    <p className="text-xs text-gray-500 mt-1">Dept: {DEPT_NAMES[selectedEvent.dept_id] ?? selectedEvent.dept_id}</p>
                                    <p className="text-xs text-gray-500">Scheduled: {new Date(selectedEvent.scheduled_date).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}</p>
                                    {selectedEvent.time_slot && <p className="text-xs text-gray-500">Time: {selectedEvent.time_slot}</p>}
                                </>
                            )}

                            <span className={`mt-3 inline-block text-xs font-bold px-2 py-0.5 rounded-full ${selectedEvent.event_type === "deadline"
                                ? "bg-pink-100 text-pink-700 border border-pink-200"
                                : PRIORITY_BADGE[selectedEvent.priority_label ?? "LOW"]
                                }`}>
                                {selectedEvent.event_type === "deadline" ? "🔔 Deadline" : selectedEvent.priority_label}
                            </span>
                        </div>
                    )}
                </div>

                {/* Sidebar */}
                <div className="space-y-4">
                    {/* AI Suggestions Panel */}
                    {suggestions.length > 0 && (
                        <div className="bg-gradient-to-br from-purple-50 to-indigo-50 rounded-2xl border border-purple-200 p-4">
                            <div className="flex items-center justify-between mb-3">
                                <h3 className="font-bold text-purple-800 text-sm flex items-center gap-2">
                                    ✨ AI Scheduling Suggestions
                                </h3>
                                <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">{suggestions.length} tickets</span>
                            </div>
                            <div className="space-y-2 max-h-72 overflow-y-auto">
                                {suggestions.map(s => (
                                    <div key={s.ticket_id} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 text-xs shadow-sm">
                                        <div>
                                            <p className="font-mono font-bold text-indigo-700">{s.ticket_code}</p>
                                            <p className="text-gray-500 truncate max-w-[120px]">{s.issue_category ?? "Issue"}</p>
                                        </div>
                                        <div className="text-right">
                                            <p className="font-semibold text-gray-700">
                                                {new Date(s.suggested_date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                                            </p>
                                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${PRIORITY_BADGE[s.priority_label]}`}>
                                                {s.priority_label}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            <button
                                onClick={applyAllSuggestions}
                                disabled={applying}
                                className="mt-3 w-full bg-purple-600 hover:bg-purple-700 text-white text-sm font-semibold py-2.5 rounded-xl transition-colors disabled:opacity-60"
                            >
                                {applying ? "Applying…" : "✅ Apply All Suggestions"}
                            </button>
                        </div>
                    )}

                    {/* Stats */}
                    <div className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm">
                        <h3 className="font-bold text-gray-700 text-sm mb-3">📊 This Month</h3>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="bg-blue-50 rounded-xl p-3 text-center">
                                <p className="text-2xl font-bold text-blue-700">{events.length}</p>
                                <p className="text-xs text-blue-600 mt-0.5">Scheduled</p>
                            </div>
                            <div className="bg-purple-50 rounded-xl p-3 text-center">
                                <p className="text-2xl font-bold text-purple-700">
                                    {events.filter(e => e.is_ai_suggested).length}
                                </p>
                                <p className="text-xs text-purple-600 mt-0.5">AI Suggested</p>
                            </div>
                            <div className="bg-red-50 rounded-xl p-3 text-center">
                                <p className="text-2xl font-bold text-red-700">
                                    {events.filter(e => e.priority_label === "CRITICAL").length}
                                </p>
                                <p className="text-xs text-red-600 mt-0.5">Critical</p>
                            </div>
                            <div className="bg-orange-50 rounded-xl p-3 text-center">
                                <p className="text-2xl font-bold text-orange-700">
                                    {events.filter(e => e.priority_label === "HIGH").length}
                                </p>
                                <p className="text-xs text-orange-600 mt-0.5">High Priority</p>
                            </div>
                        </div>
                    </div>

                    {/* How AI works */}
                    <div className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm">
                        <h3 className="font-bold text-gray-700 text-sm mb-3">🤖 How AI Scheduling Works</h3>
                        <div className="space-y-2">
                            {[
                                { icon: "🔴", label: "Critical", value: "Next 1-2 work days" },
                                { icon: "🟠", label: "High", value: "Within 3-7 days" },
                                { icon: "🟡", label: "Medium", value: "Within 7-15 days" },
                                { icon: "🟢", label: "Low", value: "Within 15-30 days" },
                            ].map(r => (
                                <div key={r.label} className="flex items-center justify-between text-xs">
                                    <span>{r.icon} {r.label}</span>
                                    <span className="text-gray-500">{r.value}</span>
                                </div>
                            ))}
                            <p className="text-[10px] text-gray-400 mt-2 border-t pt-2">Max 5 tickets/day. Sundays skipped. You can override any date manually.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
