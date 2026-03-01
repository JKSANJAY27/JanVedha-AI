interface StatCardProps {
    label: string;
    value: string | number;
    icon?: string;
    trend?: string;
    trendUp?: boolean;
    color?: string;
}

export default function StatCard({ label, value, icon, trend, trendUp, color = "blue" }: StatCardProps) {
    const colorMap: Record<string, string> = {
        blue: "from-blue-500 to-blue-600",
        red: "from-red-500 to-red-600",
        green: "from-emerald-500 to-emerald-600",
        orange: "from-orange-500 to-orange-600",
        purple: "from-purple-500 to-purple-600",
    };
    return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 flex flex-col gap-3">
            <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-gray-500">{label}</p>
                {icon && (
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${colorMap[color] ?? colorMap.blue} flex items-center justify-center text-white text-lg shadow-sm`}>
                        {icon}
                    </div>
                )}
            </div>
            <p className="text-3xl font-bold text-gray-900">{value}</p>
            {trend && (
                <p className={`text-xs font-medium flex items-center gap-1 ${trendUp ? "text-green-600" : "text-red-500"}`}>
                    {trendUp ? "↑" : "↓"} {trend}
                </p>
            )}
        </div>
    );
}
