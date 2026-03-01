import { formatStatus } from "@/lib/formatters";
import { STATUS_LABELS } from "@/lib/constants";

interface StatusBadgeProps {
    status: string;
    size?: "sm" | "md";
}

export default function StatusBadge({ status, size = "md" }: StatusBadgeProps) {
    const { bg, text, dot } = formatStatus(status);
    const sizeClass = size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1";
    return (
        <span
            className={`inline-flex items-center gap-1.5 rounded-full font-medium ${bg} ${text} ${sizeClass}`}
        >
            <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
            {STATUS_LABELS[status] ?? status.replace(/_/g, " ")}
        </span>
    );
}
