import { formatDate } from "@/lib/formatters";

interface TimelineEvent {
    event: string;
    timestamp?: string;
    actor?: string;
    reason?: string;
}

interface TimelineProps {
    events: TimelineEvent[];
}

const EVENT_ICONS: Record<string, string> = {
    CREATED: "📋",
    ASSIGNED: "👤",
    IN_PROGRESS: "🔧",
    STATUS_CHANGED: "🔄",
    PRIORITY_OVERRIDDEN: "⚡",
    CLOSED: "✅",
    REOPENED: "🔁",
    REJECTED: "❌",
    PENDING_VERIFICATION: "🔍",
};

export default function Timeline({ events }: TimelineProps) {
    if (!events?.length) return <p className="text-gray-400 text-sm">No timeline events yet.</p>;

    return (
        <ol className="relative border-l border-gray-200 dark:border-gray-700 ml-3">
            {events.map((ev, i) => (
                <li key={i} className="mb-6 ml-6">
                    <span className="absolute flex items-center justify-center w-8 h-8 bg-white border-2 border-blue-400 rounded-full -left-4 text-sm">
                        {EVENT_ICONS[ev.event] ?? "📌"}
                    </span>
                    <div className="p-3 bg-white border border-gray-100 rounded-lg shadow-sm">
                        <p className="text-sm font-semibold text-gray-800">
                            {ev.event.replace(/_/g, " ")}
                        </p>
                        {ev.actor && (
                            <p className="text-xs text-gray-500 mt-0.5">By: {ev.actor}</p>
                        )}
                        {ev.reason && (
                            <p className="text-xs text-gray-500 mt-0.5 italic">{ev.reason}</p>
                        )}
                        {ev.timestamp && (
                            <p className="text-xs text-gray-400 mt-1">{formatDate(ev.timestamp)}</p>
                        )}
                    </div>
                </li>
            ))}
        </ol>
    );
}
