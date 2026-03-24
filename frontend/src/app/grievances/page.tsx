"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import axios from "axios";
import StatCard from "@/components/StatCard";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from "recharts";

const API = "http://localhost:8000/api/grievances";

// ── Severity color map ──────────────────────────────────────────────────────
const SEV_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700 border-red-200",
  high: "bg-orange-100 text-orange-700 border-orange-200",
  medium: "bg-yellow-100 text-yellow-700 border-yellow-200",
  low: "bg-green-100 text-green-700 border-green-200",
};

const PLATFORM_COLORS: Record<string, string> = {
  twitter: "#1DA1F2",
  cpgrams: "#FF6B35",
  civic: "#8B5CF6",
  news: "#10B981",
  reddit: "#FF4500",
  municipal_portal: "#3B82F6",
};

const PLATFORM_ICONS: Record<string, string> = {
  twitter: "🐦",
  cpgrams: "📋",
  civic: "🏛️",
  news: "📰",
  reddit: "🤖",
  municipal_portal: "🏢",
};

interface Grievance {
  id: string;
  source_platform: string;
  source_url: string;
  raw_content: string;
  author: string;
  structured_summary: string;
  category: string;
  subcategory: string;
  dept_id: string;
  location_text: string;
  ward_id: number | null;
  severity: string;
  severity_score: number;
  severity_reasoning: string;
  sentiment: string;
  affected_population: number | null;
  auto_ticket_generated: boolean;
  ticket_id: string | null;
  ticket_code: string | null;
  status: string;
  original_timestamp: string | null;
  ingested_at: string;
  processed_at: string | null;
  keywords: string[];
}

interface ScraperInfo {
  name: string;
  platform: string;
  icon: string;
  configured: boolean;
  method: string;
  last_scraped_at: string | null;
  total_records: number;
}

interface Stats {
  total: number;
  auto_ticketed: number;
  pending_review: number;
  severity: Record<string, number>;
  by_platform: Record<string, number>;
  last_ingested_at: string | null;
}

export default function GrievanceDashboard() {
  const { user, token, isCommissioner, isCouncillor } = useAuth();
  const router = useRouter();

  const [stats, setStats] = useState<Stats | null>(null);
  const [scrapers, setScrapers] = useState<ScraperInfo[]>([]);
  const [grievances, setGrievances] = useState<Grievance[]>([]);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [filter, setFilter] = useState({ severity: "", platform: "", status: "" });
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const headers = { Authorization: `Bearer ${token}` };

  // ── Access check ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!user || (!isCommissioner && !isCouncillor)) {
      router.push("/login");
    }
  }, [user, isCommissioner, isCouncillor, router]);

  // ── Data fetching ─────────────────────────────────────────────────────
  const fetchAll = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [statsRes, scraperRes, grievRes] = await Promise.all([
        axios.get(`${API}/stats`, { headers }),
        axios.get(`${API}/scraper-status/all`, { headers }),
        axios.get(`${API}/`, {
          headers,
          params: {
            page,
            page_size: 15,
            ...(filter.severity && { severity: filter.severity }),
            ...(filter.platform && { platform: filter.platform }),
            ...(filter.status && { status: filter.status }),
          },
        }),
      ]);
      setStats(statsRes.data);
      setScrapers(scraperRes.data.scrapers || []);
      setGrievances(grievRes.data.results || []);
      setTotal(grievRes.data.total || 0);
    } catch (err) {
      console.error("Failed to load grievance data:", err);
    } finally {
      setLoading(false);
    }
  }, [token, page, filter]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ── Manual scrape trigger ─────────────────────────────────────────────
  const triggerScrape = async () => {
    setScraping(true);
    try {
      const res = await axios.post(`${API}/scrape`, {}, { headers });
      toast.success(
        `Scrape complete! ${res.data.scraped} items, ${res.data.auto_ticketed} auto-ticketed`
      );
      fetchAll();
    } catch (err) {
      toast.error("Scrape failed — check backend logs");
    } finally {
      setScraping(false);
    }
  };

  // ── Ticket creation from grievance ────────────────────────────────────
  const createTicket = async (id: string) => {
    try {
      const res = await axios.post(`${API}/${id}/create-ticket`, {}, { headers });
      toast.success(`Ticket created: ${res.data.ticket_code}`);
      fetchAll();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to create ticket");
    }
  };

  // ── Dismiss grievance ─────────────────────────────────────────────────
  const dismissGrievance = async (id: string) => {
    try {
      await axios.post(`${API}/${id}/dismiss`, { reason: "Not actionable" }, { headers });
      toast.success("Grievance dismissed");
      fetchAll();
    } catch {
      toast.error("Failed to dismiss");
    }
  };

  // ── Chart data ────────────────────────────────────────────────────────
  const platformPieData = stats
    ? Object.entries(stats.by_platform).map(([name, value]) => ({
        name, value, color: PLATFORM_COLORS[name] || "#94A3B8",
      }))
    : [];

  const severityBarData = stats
    ? Object.entries(stats.severity).map(([name, value]) => ({ name, count: value }))
    : [];

  const severityBarColors: Record<string, string> = {
    critical: "#EF4444", high: "#F97316", medium: "#EAB308", low: "#22C55E",
  };

  if (!user) return null;

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-blue-50">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <section className="bg-gradient-to-br from-violet-700 via-purple-800 to-indigo-900 text-white py-10 px-4">
        <div className="max-w-7xl mx-auto">
          <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
            <div className="flex items-center justify-between">
              <div>
                <div className="inline-flex items-center gap-2 bg-white/10 rounded-full px-4 py-1.5 mb-4 text-sm font-medium backdrop-blur-sm border border-white/20">
                  <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  Grievance Intelligence Hub
                </div>
                <h1 className="text-3xl md:text-4xl font-extrabold mb-2">
                  🔍 Public Grievance Dashboard
                </h1>
                <p className="text-purple-200 text-sm max-w-xl">
                  Real-time scraping, AI-powered structuring, and automatic ticket generation
                  for serious civic grievances across multiple platforms.
                </p>
              </div>
              <button
                onClick={triggerScrape}
                disabled={scraping}
                className="px-6 py-3 bg-white/15 hover:bg-white/25 border border-white/20 rounded-xl text-sm font-semibold transition-all backdrop-blur-sm disabled:opacity-50 flex items-center gap-2"
              >
                {scraping ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Scraping…
                  </>
                ) : (
                  <>🚀 Trigger Manual Scrape</>
                )}
              </button>
            </div>
          </motion.div>
        </div>
      </section>

      <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* ── Metrics Strip ────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="Total Ingested" value={stats?.total ?? "—"}
            icon="📥" color="blue"
          />
          <StatCard
            label="Auto-Ticketed" value={stats?.auto_ticketed ?? "—"}
            icon="🎫" color="green"
          />
          <StatCard
            label="Pending Review" value={stats?.pending_review ?? "—"}
            icon="⏳" color="orange"
          />
          <StatCard
            label="Critical / High"
            value={((stats?.severity?.critical ?? 0) + (stats?.severity?.high ?? 0))}
            icon="🔴" color="red"
          />
        </div>

        {/* ── Live Scraper Status ──────────────────────────────────────── */}
        <div>
          <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            Live Scraper Status
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {scrapers.map((s) => (
              <motion.div
                key={s.platform}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`rounded-2xl p-4 border ${
                  s.configured
                    ? "bg-white border-gray-100 shadow-sm"
                    : "bg-gray-50 border-gray-200 opacity-60"
                }`}
              >
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-2xl">{s.icon}</span>
                  <div>
                    <p className="text-sm font-bold text-gray-800">{s.name}</p>
                    <p className="text-[10px] text-gray-400">{s.method}</p>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                    s.configured ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"
                  }`}>
                    {s.configured ? "Active" : "Disabled"}
                  </span>
                  <span className="text-xs text-gray-500 font-mono">{s.total_records} rec</span>
                </div>
                {s.last_scraped_at && (
                  <p className="text-[10px] text-gray-400 mt-2">
                    Last: {new Date(s.last_scraped_at).toLocaleString()}
                  </p>
                )}
              </motion.div>
            ))}
          </div>
        </div>

        {/* ── Charts Row ──────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Platform Distribution */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <h3 className="text-sm font-bold text-gray-700 mb-4">📊 Grievances by Platform</h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={platformPieData}
                  cx="50%" cy="50%"
                  innerRadius={50} outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {platformPieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap gap-2 mt-2 justify-center">
              {platformPieData.map((d) => (
                <span key={d.name} className="flex items-center gap-1.5 text-xs text-gray-600">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: d.color }} />
                  {PLATFORM_ICONS[d.name] || "📦"} {d.name} ({d.value})
                </span>
              ))}
            </div>
          </div>

          {/* Severity Breakdown */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <h3 className="text-sm font-bold text-gray-700 mb-4">⚡ Severity Breakdown</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={severityBarData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip />
                <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                  {severityBarData.map((entry, i) => (
                    <Cell key={i} fill={severityBarColors[entry.name] || "#94A3B8"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ── Filters ─────────────────────────────────────────────────── */}
        <div className="flex flex-wrap gap-3 items-center">
          <span className="text-sm font-semibold text-gray-600">Filter:</span>
          <select
            value={filter.severity}
            onChange={(e) => { setFilter(f => ({ ...f, severity: e.target.value })); setPage(1); }}
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white"
          >
            <option value="">All Severity</option>
            <option value="critical">🔴 Critical</option>
            <option value="high">🟠 High</option>
            <option value="medium">🟡 Medium</option>
            <option value="low">🟢 Low</option>
          </select>
          <select
            value={filter.platform}
            onChange={(e) => { setFilter(f => ({ ...f, platform: e.target.value })); setPage(1); }}
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white"
          >
            <option value="">All Platforms</option>
            <option value="twitter">🐦 Twitter</option>
            <option value="cpgrams">📋 CPGRAMS</option>
            <option value="civic">🏛️ Civic</option>
            <option value="news">📰 News</option>
            <option value="reddit">🤖 Reddit</option>
          </select>
          <select
            value={filter.status}
            onChange={(e) => { setFilter(f => ({ ...f, status: e.target.value })); setPage(1); }}
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white"
          >
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="processed">Processed</option>
            <option value="ticket_created">Ticket Created</option>
            <option value="dismissed">Dismissed</option>
          </select>
          <span className="ml-auto text-xs text-gray-400">
            Showing {grievances.length} of {total}
          </span>
        </div>

        {/* ── Grievance Feed ──────────────────────────────────────────── */}
        <div className="space-y-3">
          <AnimatePresence mode="popLayout">
            {loading ? (
              <div className="text-center py-20">
                <span className="w-8 h-8 border-3 border-purple-400 border-t-transparent rounded-full animate-spin inline-block" />
                <p className="text-gray-400 text-sm mt-3">Loading grievances…</p>
              </div>
            ) : grievances.length === 0 ? (
              <div className="text-center py-20 bg-white rounded-2xl border border-gray-100">
                <p className="text-3xl mb-2">📭</p>
                <p className="text-gray-500 text-sm">No grievances found. Trigger a scrape to start ingesting.</p>
              </div>
            ) : (
              grievances.map((g, i) => (
                <motion.div
                  key={g.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ delay: i * 0.03 }}
                  className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start gap-4">
                    {/* Platform icon */}
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-100 to-indigo-100 flex items-center justify-center text-xl shrink-0">
                      {PLATFORM_ICONS[g.source_platform] || "📦"}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                        <span className="text-xs font-semibold text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full">
                          {g.source_platform.toUpperCase()}
                        </span>
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${SEV_COLORS[g.severity] || SEV_COLORS.low}`}>
                          {g.severity.toUpperCase()} ({(g.severity_score * 100).toFixed(0)}%)
                        </span>
                        {g.auto_ticket_generated && (
                          <span className="text-xs font-semibold bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                            🎫 {g.ticket_code}
                          </span>
                        )}
                        {g.category && (
                          <span className="text-xs text-gray-500 bg-gray-50 px-2 py-0.5 rounded-full">
                            {g.category}
                          </span>
                        )}
                      </div>

                      {/* Summary */}
                      {g.structured_summary && (
                        <p className="text-sm font-semibold text-gray-800 mb-1">
                          {g.structured_summary}
                        </p>
                      )}

                      {/* Raw content preview */}
                      <p className="text-xs text-gray-500 line-clamp-2 mb-2">
                        {g.raw_content}
                      </p>

                      {/* Severity reasoning */}
                      {g.severity_reasoning && (
                        <p className="text-xs text-orange-600 bg-orange-50 rounded-lg px-3 py-1.5 mb-2">
                          🧠 <strong>AI:</strong> {g.severity_reasoning}
                        </p>
                      )}

                      {/* Meta row */}
                      <div className="flex items-center gap-3 text-[11px] text-gray-400">
                        {g.author && <span>by {g.author}</span>}
                        {g.location_text && <span>📍 {g.location_text}</span>}
                        {g.ward_id && <span>🏛️ Ward {g.ward_id}</span>}
                        {g.ingested_at && <span>⏱ {new Date(g.ingested_at).toLocaleString()}</span>}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col gap-1.5 shrink-0">
                      {!g.auto_ticket_generated && g.status !== "dismissed" && (
                        <>
                          <button
                            onClick={() => createTicket(g.id)}
                            className="text-xs px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg font-semibold hover:bg-blue-100 transition-colors"
                          >
                            🎫 Create Ticket
                          </button>
                          <button
                            onClick={() => dismissGrievance(g.id)}
                            className="text-xs px-3 py-1.5 bg-gray-50 text-gray-500 rounded-lg font-medium hover:bg-gray-100 transition-colors"
                          >
                            ✕ Dismiss
                          </button>
                        </>
                      )}
                      {g.source_url && (
                        <a
                          href={g.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs px-3 py-1.5 bg-purple-50 text-purple-600 rounded-lg font-medium hover:bg-purple-100 transition-colors text-center"
                        >
                          🔗 Source
                        </a>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))
            )}
          </AnimatePresence>
        </div>

        {/* ── Pagination ──────────────────────────────────────────────── */}
        {total > 15 && (
          <div className="flex justify-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
              className="px-4 py-2 bg-white border border-gray-200 rounded-xl text-sm font-medium disabled:opacity-40"
            >
              ← Previous
            </button>
            <span className="px-4 py-2 text-sm text-gray-500">
              Page {page} of {Math.ceil(total / 15)}
            </span>
            <button
              disabled={page >= Math.ceil(total / 15)}
              onClick={() => setPage(p => p + 1)}
              className="px-4 py-2 bg-white border border-gray-200 rounded-xl text-sm font-medium disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
