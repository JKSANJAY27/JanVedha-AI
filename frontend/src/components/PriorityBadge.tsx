import { formatPriority } from "@/lib/formatters";

interface PriorityBadgeProps {
    label: string;
    score?: number;
    size?: "sm" | "md" | "lg";
}

export default function PriorityBadge({ label, score, size = "md" }: PriorityBadgeProps) {
    const { bg, text } = formatPriority(label);
    const sizeClass = size === "sm" ? "text-xs px-2 py-0.5" : size === "lg" ? "text-base px-4 py-1.5" : "text-sm px-3 py-1";
    return (
        <span className={`inline-flex items-center gap-1 rounded-full font-semibold ${bg} ${text} ${sizeClass}`}>
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: formatPriority(label).color }} />
            {label?.toUpperCase()}
            {score !== undefined && <span className="opacity-70">({score})</span>}
        </span>
    );
}
