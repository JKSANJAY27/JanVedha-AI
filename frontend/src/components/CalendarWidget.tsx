"use client";

import { useState } from "react";

export interface CalendarEvent {
    id: string;
    ticket_id: string;
    ticket_code: string;
    scheduled_date: string;
    dept_id: string;
    priority_label?: string;
    issue_category?: string;
    is_ai_suggested?: boolean;
    time_slot?: string;
    event_type?: string;          // "schedule" | "deadline"
    ticket_description?: string;
    notes?: string;
}

interface Props {
    events: CalendarEvent[];
    onDateClick?: (date: Date) => void;
    onEventClick?: (event: CalendarEvent) => void;
    month?: number; // 0-indexed
    year?: number;
}

const PRIORITY_CHIP: Record<string, string> = {
    CRITICAL: "bg-red-500 text-white",
    HIGH: "bg-orange-400 text-white",
    MEDIUM: "bg-yellow-400 text-gray-900",
    LOW: "bg-green-400 text-white",
};

const DEADLINE_CHIP = "bg-pink-500 text-white";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
];

export default function CalendarWidget({ events, onDateClick, onEventClick, month, year }: Props) {
    const now = new Date();
    const [currentMonth, setCurrentMonth] = useState(month ?? now.getMonth());
    const [currentYear, setCurrentYear] = useState(year ?? now.getFullYear());

    const firstDay = new Date(currentYear, currentMonth, 1).getDay();
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();

    const prevMonth = () => {
        if (currentMonth === 0) { setCurrentMonth(11); setCurrentYear(y => y - 1); }
        else setCurrentMonth(m => m - 1);
    };
    const nextMonth = () => {
        if (currentMonth === 11) { setCurrentMonth(0); setCurrentYear(y => y + 1); }
        else setCurrentMonth(m => m + 1);
    };

    // Group events by date string (YYYY-MM-DD)
    const eventsByDate: Record<string, CalendarEvent[]> = {};
    for (const ev of events) {
        const d = new Date(ev.scheduled_date);
        const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        if (!eventsByDate[key]) eventsByDate[key] = [];
        eventsByDate[key].push(ev);
    }

    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;

    const cells: (number | null)[] = [
        ...Array(firstDay).fill(null),
        ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
    ];

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-indigo-600 to-blue-600 text-white">
                <button onClick={prevMonth} className="p-1.5 rounded-lg hover:bg-white/20 transition-colors text-lg">‹</button>
                <h3 className="font-bold text-lg tracking-wide">
                    {MONTHS[currentMonth]} {currentYear}
                </h3>
                <button onClick={nextMonth} className="p-1.5 rounded-lg hover:bg-white/20 transition-colors text-lg">›</button>
            </div>

            {/* Day headers */}
            <div className="grid grid-cols-7 border-b border-gray-100">
                {DAYS.map(d => (
                    <div key={d} className="text-center py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                        {d}
                    </div>
                ))}
            </div>

            {/* Calendar grid */}
            <div className="grid grid-cols-7">
                {cells.map((day, idx) => {
                    if (!day) return <div key={`empty-${idx}`} className="min-h-[80px] border-r border-b border-gray-50/80 bg-gray-50/30" />;

                    const monthStr = String(currentMonth + 1).padStart(2, "0");
                    const dayStr = String(day).padStart(2, "0");
                    const dateKey = `${currentYear}-${monthStr}-${dayStr}`;
                    const dayEvents = eventsByDate[dateKey] ?? [];
                    const isToday = dateKey === todayStr;
                    const isSunday = (idx % 7) === 0;

                    return (
                        <div
                            key={dateKey}
                            className={`min-h-[80px] border-r border-b border-gray-100 p-1.5 cursor-pointer hover:bg-blue-50/50 transition-colors
                                ${isToday ? "bg-blue-50 ring-1 ring-blue-300 ring-inset" : ""}
                                ${isSunday ? "bg-gray-50/50" : ""}`}
                            onClick={() => onDateClick?.(new Date(currentYear, currentMonth, day))}
                        >
                            <span className={`text-xs font-bold inline-flex w-6 h-6 items-center justify-center rounded-full
                                ${isToday ? "bg-blue-600 text-white" : "text-gray-500"}`}>
                                {day}
                            </span>
                            <div className="mt-1 space-y-0.5">
                                {dayEvents.slice(0, 3).map(ev => (
                                    <button
                                        key={ev.id}
                                        onClick={e => { e.stopPropagation(); onEventClick?.(ev); }}
                                        className={`w-full text-left text-[10px] font-medium px-1 py-0.5 rounded truncate
                                            ${ev.event_type === "deadline" ? DEADLINE_CHIP : PRIORITY_CHIP[ev.priority_label ?? "LOW"]}
                                            ${ev.is_ai_suggested ? "ring-1 ring-purple-400 ring-offset-0" : ""}`}
                                        title={`${ev.event_type === "deadline" ? "⏰ Deadline: " : ""
                                            }${ev.ticket_code} — ${ev.issue_category ?? "Issue"}${ev.is_ai_suggested ? " (AI)" : ""}`}
                                    >
                                        {ev.event_type === "deadline" ? "🔔 " : ev.is_ai_suggested ? "✨ " : ""}{ev.ticket_code}
                                    </button>
                                ))}
                                {dayEvents.length > 3 && (
                                    <span className="text-[10px] text-gray-400 pl-1">+{dayEvents.length - 3} more</span>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Legend */}
            <div className="flex flex-wrap gap-3 px-4 py-3 border-t border-gray-100 bg-gray-50/50">
                {Object.entries(PRIORITY_CHIP).map(([label, cls]) => (
                    <span key={label} className={`text-[10px] font-bold px-2 py-0.5 rounded ${cls}`}>
                        {label}
                    </span>
                ))}
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${DEADLINE_CHIP}`}>
                    🔔 DEADLINE
                </span>
                <span className="text-[10px] text-gray-500 flex items-center gap-1">
                    <span className="ring-1 ring-purple-400 rounded px-1 bg-green-400 text-white font-bold">✨ AI</span>
                    AI Suggested
                </span>
            </div>
        </div>
    );
}
