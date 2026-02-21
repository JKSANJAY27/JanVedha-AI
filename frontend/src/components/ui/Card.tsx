export function Card({ children, className = '' }: { children: React.ReactNode, className?: string }) {
    return (
        <div className={`glass-panel rounded-xl overflow-hidden transition-all duration-300 hover:shadow-2xl ${className}`}>
            {children}
        </div>
    );
}

export function CardHeader({ children, className = '' }: { children: React.ReactNode, className?: string }) {
    return (
        <div className={`px-6 py-4 border-b border-white/5 ${className}`}>
            {children}
        </div>
    );
}

export function CardTitle({ children, className = '' }: { children: React.ReactNode, className?: string }) {
    return (
        <h3 className={`text-lg font-semibold tracking-tight ${className}`}>
            {children}
        </h3>
    );
}

export function CardContent({ children, className = '' }: { children: React.ReactNode, className?: string }) {
    return (
        <div className={`px-6 py-4 ${className}`}>
            {children}
        </div>
    );
}
