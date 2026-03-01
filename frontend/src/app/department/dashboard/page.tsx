"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { officerApi } from "@/lib/api";
import toast from "react-hot-toast";
import { formatRelative } from "@/lib/formatters";
import StatCard from "@/components/StatCard";
import PriorityBadge from "@/components/PriorityBadge";
import StatusBadge from "@/components/StatusBadge";
import Link from "next/link";
import { DEPT_NAMES } from "@/lib/constants";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface Ticket {
    id: string;
    ticket_code: string;
    status: string;
    dept_id: string;
    issue_category?: string;
    priority_label: string;
    priority_score: number;
    created_at: string;
}

export default function DepartmentDashboard() {
    const { user, isOfficer } = useAuth();
    const router = useRouter();
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);
    const [catFilter, setCatFilter] = useState("ALL");

    useEffect(() => {
        if (!isOfficer) { router.push("/login"); return; }
        officerApi.getTickets(200)
            .then((res) => setTickets(res.data))
            .catch(() => toast.error("Failed to load tickets"))
            .finally(() => setLoading(false));
    }, []);

    const categories = ["ALL", ...new Set(tickets.map((t) => t.issue_category ?? "Uncategorized"))];
    const filtered = catFilter === "ALL" ? tickets : tickets.filter((t) => (t.issue_category ?? "Uncategorized") === catFilter);

    const catData = Object.entries(
        tickets.reduce<Record<string, number>>((acc, t) => {
            const cat = t.issue_category ?? "Uncategorized";
            acc[cat] = (acc[cat] || 0) + 1;
            return acc;
        }, {})
    ).map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count).slice(0, 8);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50">
            <div className="bg-gradient-to-r from-teal-700 to-cyan-800 text-white px-6 py-6">
                <div className="max-w-7xl mx-auto">
                    <p className="text-teal-200 text-sm">Department Head · {DEPT_NAMES[user?.dept_id ?? ""] ?? user?.dept_id}</p>
                    <h1 className="text-2xl font-bold mt-0.5">Department Dashboard</h1>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <StatCard label="Total Tickets" value={tickets.length} icon="📋" color="blue" />
                    <StatCard label="Open" value={tickets.filter(t => t.status === "OPEN").length} icon="📬" color="orange" />
                    <StatCard label="In Progress" value={tickets.filter(t => t.status === "IN_PROGRESS").length} icon="🔧" color="purple" />
                    <StatCard label="Resolved" value={tickets.filter(t => t.status === "CLOSED").length} icon="✅" color="green" />
                </div>

                {/* Category chart */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                    <h3 className="font-bold text-gray-900 mb-4">Issues by Category</h3>
                    <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={catData}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-15} textAnchor="end" height={50} />
                            <YAxis tick={{ fontSize: 11 }} />
                            <Tooltip />
                            <Bar dataKey="count" fill="#0d9488" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {/* Category filter + ticket list */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-100 flex flex-wrap gap-2 items-center justify-between">
                        <h3 className="font-bold text-gray-900">Ticket Queue</h3>
                        <div className="flex gap-2 flex-wrap">
                            {categories.slice(0, 6).map((cat) => (
                                <button
                                    key={cat}
                                    onClick={() => setCatFilter(cat)}
                                    className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all ${catFilter === cat ? "bg-teal-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
                                >
                                    {cat}
                                </button>
                            ))}
                        </div>
                    </div>

                    {filtered.length === 0 ? (
                        <p className="text-center text-gray-400 py-12">No tickets for this category</p>
                    ) : (
                        <div className="divide-y divide-gray-50">
                            {filtered.slice(0, 30).map((t) => (
                                <div key={t.id} className="px-6 py-4 flex items-center justify-between gap-3 hover:bg-gray-50 transition-colors">
                                    <div className="flex-1 min-w-0">
                                        <p className="font-mono text-sm font-bold text-blue-700">{t.ticket_code}</p>
                                        <p className="text-xs text-gray-500 mt-0.5">{t.issue_category ?? "Uncategorized"} · {formatRelative(t.created_at)}</p>
                                    </div>
                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        <PriorityBadge label={t.priority_label} size="sm" />
                                        <StatusBadge status={t.status} size="sm" />
                                        <Link href={`/officer/tickets/${t.id}`} className="text-xs text-blue-600 hover:underline">View →</Link>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
