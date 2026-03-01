import { format, formatDistanceToNow, isAfter } from "date-fns";

export function formatDate(ts: string | Date | null | undefined): string {
    if (!ts) return "—";
    return format(new Date(ts), "dd MMM yyyy, hh:mm a");
}

export function formatRelative(ts: string | Date | null | undefined): string {
    if (!ts) return "—";
    return formatDistanceToNow(new Date(ts), { addSuffix: true });
}

export function formatPriority(
    label: string
): { color: string; bg: string; text: string } {
    switch (label?.toUpperCase()) {
        case "CRITICAL":
            return { color: "#DC2626", bg: "bg-red-100", text: "text-red-700" };
        case "HIGH":
            return { color: "#EA580C", bg: "bg-orange-100", text: "text-orange-700" };
        case "MEDIUM":
            return { color: "#CA8A04", bg: "bg-yellow-100", text: "text-yellow-700" };
        case "LOW":
        default:
            return { color: "#16A34A", bg: "bg-green-100", text: "text-green-700" };
    }
}

export function formatStatus(
    status: string
): { bg: string; text: string; dot: string } {
    switch (status?.toUpperCase()) {
        case "OPEN":
            return { bg: "bg-blue-100", text: "text-blue-700", dot: "bg-blue-500" };
        case "ASSIGNED":
            return {
                bg: "bg-indigo-100",
                text: "text-indigo-700",
                dot: "bg-indigo-500",
            };
        case "IN_PROGRESS":
            return {
                bg: "bg-amber-100",
                text: "text-amber-700",
                dot: "bg-amber-500",
            };
        case "PENDING_VERIFICATION":
            return {
                bg: "bg-purple-100",
                text: "text-purple-700",
                dot: "bg-purple-500",
            };
        case "CLOSED":
            return {
                bg: "bg-green-100",
                text: "text-green-700",
                dot: "bg-green-500",
            };
        case "REJECTED":
            return { bg: "bg-red-100", text: "text-red-700", dot: "bg-red-500" };
        default:
            return { bg: "bg-gray-100", text: "text-gray-600", dot: "bg-gray-400" };
    }
}

export function slaStatus(deadline: string | null | undefined): {
    label: string;
    color: string;
    pct: number;
} {
    if (!deadline) return { label: "No SLA", color: "bg-gray-300", pct: 0 };
    const now = new Date();
    const end = new Date(deadline);
    const isBr = isAfter(now, end);
    if (isBr) return { label: "SLA Breached", color: "bg-red-500", pct: 100 };
    // Assume 14-day SLA window
    const totalMs = 14 * 24 * 3600 * 1000;
    const elapsedMs = end.getTime() - 14 * 24 * 3600 * 1000 - now.getTime() * -1;
    const pct = Math.min(
        100,
        Math.max(0, ((totalMs - (end.getTime() - now.getTime())) / totalMs) * 100)
    );
    const days = Math.ceil((end.getTime() - now.getTime()) / (1000 * 3600 * 24));
    return {
        label: `${days} day${days !== 1 ? "s" : ""} remaining`,
        color: pct > 75 ? "bg-red-400" : pct > 50 ? "bg-yellow-400" : "bg-green-400",
        pct,
    };
}

export function priorityScoreLabel(score: number): string {
    if (score >= 80) return "CRITICAL";
    if (score >= 60) return "HIGH";
    if (score >= 35) return "MEDIUM";
    return "LOW";
}
