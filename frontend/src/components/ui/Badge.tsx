export function Badge({
    children,
    variant = 'default',
    className = ''
}: {
    children: React.ReactNode,
    variant?: 'default' | 'critical' | 'high' | 'medium' | 'low',
    className?: string
}) {
    const base = "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2";
    const variants = {
        default: "border-transparent bg-secondary text-secondary-foreground",
        critical: "priority-critical border-transparent",
        high: "priority-high border-transparent",
        medium: "priority-medium border-transparent",
        low: "priority-low border-transparent"
    };

    return (
        <div className={`${base} ${variants[variant]} ${className}`}>
            {children}
        </div>
    );
}
