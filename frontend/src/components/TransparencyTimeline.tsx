"use client";

interface TimelineStep {
    status: string;
    timestamp: string;
    actor_role?: string;
    note?: string;
}

interface Props {
    steps: TimelineStep[];
    dept_name?: string;  // shown publicly instead of officer name
}

const STATUS_META: Record<string, { icon: string; label: string; color: string }> = {
    OPEN: { icon: "📋", label: "Issue Submitted", color: "border-blue-400 bg-blue-50" },
    ASSIGNED: { icon: "📌", label: "Assigned to Department Team", color: "border-indigo-400 bg-indigo-50" },
    SCHEDULED: { icon: "📅", label: "Work Scheduled", color: "border-purple-400 bg-purple-50" },
    IN_PROGRESS: { icon: "🔧", label: "Work In Progress", color: "border-orange-400 bg-orange-50" },
    AWAITING_MATERIAL: { icon: "📦", label: "Awaiting Materials", color: "border-yellow-400 bg-yellow-50" },
    PENDING_VERIFICATION: { icon: "🔍", label: "Work Completed — Verifying", color: "border-cyan-400 bg-cyan-50" },
    CLOSED: { icon: "✅", label: "Issue Resolved", color: "border-green-400 bg-green-50" },
    CLOSED_UNVERIFIED: { icon: "☑️", label: "Closed (Unverified)", color: "border-gray-400 bg-gray-50" },
    REOPENED: { icon: "🔄", label: "Reopened for Review", color: "border-red-400 bg-red-50" },
    REJECTED: { icon: "❌", label: "Complaint Rejected", color: "border-red-400 bg-red-50" },
};

function formatTs(ts: string): string {
    try {
        const d = new Date(ts.endsWith("Z") ? ts : ts + "Z");
        return d.toLocaleString("en-IN", {
            day: "numeric", month: "short", year: "numeric",
            hour: "2-digit", minute: "2-digit",
        });
    } catch {
        return ts;
    }
}

export default function TransparencyTimeline({ steps, dept_name }: Props) {
    if (!steps || steps.length === 0) {
        return (
            <div className="text-center py-8 text-gray-400">
                <p className="text-3xl mb-2">🕓</p>
                <p className="text-sm">No updates yet. Check back soon.</p>
            </div>
        );
    }

    return (
        <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-5 top-0 bottom-0 w-0.5 bg-gray-200 rounded" />
            <div className="space-y-4">
                {steps.map((step, i) => {
                    const meta = STATUS_META[step.status] ?? {
                        icon: "📌",
                        label: step.status.replace(/_/g, " "),
                        color: "border-gray-300 bg-gray-50",
                    };
                    const isLast = i === steps.length - 1;
                    return (
                        <div key={i} className="relative flex gap-4 pl-12">
                            {/* Icon circle */}
                            <div className={`absolute left-0 w-10 h-10 rounded-full border-2 flex items-center justify-center text-lg z-10 bg-white ${meta.color.split(" ")[0]}`}>
                                {meta.icon}
                            </div>
                            {/* Card */}
                            <div className={`flex-1 rounded-xl border p-3 ${meta.color} ${isLast ? "ring-2 ring-offset-1 ring-blue-200" : ""}`}>
                                <div className="flex items-start justify-between gap-2">
                                    <p className="font-semibold text-gray-800 text-sm">{meta.label}</p>
                                    {isLast && (
                                        <span className="text-[10px] bg-blue-100 text-blue-700 font-bold px-2 py-0.5 rounded-full whitespace-nowrap">
                                            Current Status
                                        </span>
                                    )}
                                </div>
                                <p className="text-xs text-gray-500 mt-0.5">{formatTs(step.timestamp)}</p>
                                {step.note && (
                                    <p className="text-xs text-gray-600 mt-1 italic">{step.note}</p>
                                )}
                                {step.actor_role && dept_name && step.status === "ASSIGNED" && (
                                    <p className="text-xs text-indigo-600 mt-1 font-medium">
                                        → {dept_name} Team
                                    </p>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
