"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { officerApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { formatDate, formatRelative } from "@/lib/formatters";
import PriorityBadge from "@/components/PriorityBadge";
import StatusBadge from "@/components/StatusBadge";
import StatCard from "@/components/StatCard";
import Link from "next/link";
import { DEPT_NAMES, getWardLabel } from "@/lib/constants";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";

interface Ticket {
    id: string;
    ticket_code: string;
    status: string;
    dept_id: string;
    issue_category?: string;
    priority_label: string;
    priority_score: number;
    created_at: string;
    ward_id?: number;
}

const PIE_COLORS = ["#DC2626", "#EA580C", "#CA8A04", "#16A34A"];

export default function CouncillorDashboard() {
    const { user, isOfficer } = useAuth();
    const router = useRouter();
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!isOfficer) { router.push("/login"); return; }
        officerApi.getTickets(200)
            .then((res) => setTickets(res.data))
            .catch(() => toast.error("Failed to load data"))
            .finally(() => setLoading(false));
    }, []);

    const byPriority = [
        { name: "Critical", value: tickets.filter(t => t.priority_label === "CRITICAL").length },
        { name: "High", value: tickets.filter(t => t.priority_label === "HIGH").length },
        { name: "Medium", value: tickets.filter(t => t.priority_label === "MEDIUM").length },
        { name: "Low", value: tickets.filter(t => t.priority_label === "LOW").length },
    ];

    const byStatus = [
        { name: "Open", value: tickets.filter(t => t.status === "OPEN").length },
        { name: "Assigned", value: tickets.filter(t => t.status === "ASSIGNED").length },
        { name: "In Progress", value: tickets.filter(t => t.status === "IN_PROGRESS").length },
        { name: "Closed", value: tickets.filter(t => t.status === "CLOSED").length },
    ];

    const byDept = Object.entries(
        tickets.reduce<Record<string, number>>((acc, t) => {
            acc[t.dept_id] = (acc[t.dept_id] || 0) + 1;
            return acc;
        }, {})
    ).map(([dept_id, count]) => ({ name: DEPT_NAMES[dept_id] ?? dept_id, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 6);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50">
            <div className="bg-gradient-to-r from-indigo-800 to-purple-900 text-white px-6 py-6">
                <div className="max-w-7xl mx-auto">
                    <p className="text-indigo-300 text-sm">Councillor · {user?.ward_id ? getWardLabel(user.ward_id) : "All Wards"}</p>
                    <h1 className="text-2xl font-bold mt-0.5">Councillor Dashboard</h1>
                    <p className="text-indigo-200 text-sm mt-1">Complete ward issue overview with analytics</p>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
                {/* Stats row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <StatCard label="Total Tickets" value={tickets.length} icon="📋" color="blue" />
                    <StatCard label="Critical" value={tickets.filter(t => t.priority_label === "CRITICAL").length} icon="🚨" color="red" />
                    <StatCard label="In Progress" value={tickets.filter(t => t.status === "IN_PROGRESS").length} icon="🔧" color="orange" />
                    <StatCard label="Resolved" value={tickets.filter(t => t.status === "CLOSED").length} icon="✅" color="green" />
                </div>

                {/* Charts */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                        <h3 className="font-bold text-gray-900 mb-4">Priority Breakdown</h3>
                        <ResponsiveContainer width="100%" height={240}>
                            <PieChart>
                                <Pie data={byPriority} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={85} label={({ name, value }) => value > 0 ? `${name}: ${value}` : ""}>
                                    {byPriority.map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>

                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                        <h3 className="font-bold text-gray-900 mb-4">Issues by Department</h3>
                        <ResponsiveContainer width="100%" height={240}>
                            <BarChart data={byDept} layout="vertical">
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis type="number" tick={{ fontSize: 11 }} />
                                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={110} />
                                <Tooltip />
                                <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Status summary */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                    <h3 className="font-bold text-gray-900 mb-4">Status Overview</h3>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                        {byStatus.map((s) => (
                            <div key={s.name} className="text-center p-4 bg-gray-50 rounded-xl">
                                <p className="text-2xl font-bold text-gray-900">{s.value}</p>
                                <p className="text-sm text-gray-500 mt-1">{s.name}</p>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Recent critical tickets */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                        <h3 className="font-bold text-gray-900">🔴 Critical Tickets</h3>
                        <Link href="/officer/dashboard" className="text-sm text-blue-600 hover:underline">View all →</Link>
                    </div>
                    {tickets.filter(t => t.priority_label === "CRITICAL").length === 0 ? (
                        <p className="text-center text-gray-400 py-8">No critical tickets 🎉</p>
                    ) : (
                        <div className="divide-y divide-gray-50">
                            {tickets.filter(t => t.priority_label === "CRITICAL").slice(0, 5).map((t) => (
                                <div key={t.id} className="px-6 py-4 flex items-center justify-between gap-3 hover:bg-red-50 transition-colors">
                                    <div>
                                        <p className="font-mono text-sm font-bold text-blue-700">{t.ticket_code}</p>
                                        <p className="text-xs text-gray-500 mt-0.5">{DEPT_NAMES[t.dept_id] ?? t.dept_id} · {formatRelative(t.created_at)}</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <StatusBadge status={t.status} size="sm" />
                                        <Link href={`/officer/tickets/${t.id}`} className="text-sm text-blue-600 hover:text-blue-800">View →</Link>
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
