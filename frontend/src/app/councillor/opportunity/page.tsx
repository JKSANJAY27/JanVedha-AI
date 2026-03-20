"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";
import { opportunityApi } from "@/lib/api";

// ── Leaflet loaded client-side only ──────────────────────────────────────────
const MapView = dynamic(() => import("./MapView"), { ssr: false });

// ── Types ─────────────────────────────────────────────────────────────────────
interface Zone {
  cell_id: string;
  rank: number;
  opportunity_score: number;
  cell_center: { lat: number; lng: number };
  complaint_volume: number;
  dominant_category: string;
  infrastructure_recommendation: string;
  resolution_failure_rate: number;
  recurrence_score: number;
  category_breakdown: Record<string, number>;
  ai_narrative: string;
  bounds: { south: number; north: number; west: number; east: number };
}

interface ZonesResponse {
  ward_id: number;
  analysis_period_days: number;
  total_tickets_analyzed: number;
  zones: Zone[];
  empty_reason?: string;
  min_lat?: number;
  min_lng?: number;
}

// ── Constants ─────────────────────────────────────────────────────────────────
const ZONE_LABELS = ["A", "B", "C", "D", "E"];

const CAT_COLORS: Record<string, string> = {
  roads: "#ef4444",
  road: "#ef4444",
  water: "#3b82f6",
  drainage: "#8b5cf6",
  lighting: "#f59e0b",
  waste: "#10b981",
  other: "#6b7280",
};

function scoreColor(score: number) {
  if (score >= 80) return { bg: "#dc2626", text: "text-white", label: "Critical" };
  if (score >= 60) return { bg: "#d97706", text: "text-white", label: "High Priority" };
  return { bg: "#2563eb", text: "text-white", label: "Moderate" };
}

function CategoryBar({ breakdown }: { breakdown: Record<string, number> }) {
  const total = Object.values(breakdown).reduce((a, b) => a + b, 0) || 1;
  return (
    <div className="flex h-2 w-full rounded-full overflow-hidden mt-2">
      {Object.entries(breakdown).map(([cat, count]) => (
        <div
          key={cat}
          style={{ width: `${(count / total) * 100}%`, backgroundColor: CAT_COLORS[cat] ?? "#6b7280" }}
          title={`${cat}: ${count}`}
        />
      ))}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function OpportunityPage() {
  const { user, isCouncillor, isAdmin, isSupervisor } = useAuth();
  const router = useRouter();

  const [data, setData] = useState<ZonesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(180);
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const fetchZones = useCallback(async (daysVal: number) => {
    setLoading(true);
    try {
      const res = await opportunityApi.getZones(user?.ward_id, daysVal);
      setData(res.data);
    } catch {
      toast.error("Failed to load opportunity analysis");
    } finally {
      setLoading(false);
    }
  }, [user?.ward_id]);

  useEffect(() => {
    const allowed = isCouncillor || isAdmin || isSupervisor;
    if (!user) return;
    if (!allowed) { router.push("/officer/dashboard"); return; }
    fetchZones(days);
  }, [user, days]);

  const handleZoneClick = useCallback((cellId: string) => {
    setSelectedZone(cellId);
    const el = cardRefs.current[cellId];
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  if (!user) return null;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-emerald-700 to-teal-800 text-white px-6 py-5">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center gap-3 flex-wrap">
            <div>
              <p className="text-emerald-300 text-sm">Development · Ward {user?.ward_id}</p>
              <h1 className="text-xl font-bold mt-0.5">Infrastructure Opportunity Spotter 🗺️</h1>
              <p className="text-emerald-200 text-xs mt-0.5">
                Areas with the highest unmet infrastructure need
              </p>
            </div>
            <div className="ml-auto flex items-center gap-2 flex-wrap">
              <a href="/dashboard" className="text-xs text-emerald-300 hover:text-white underline">
                ← Dashboard
              </a>
              <div className="flex rounded-lg overflow-hidden border border-emerald-500">
                {[90, 180, 365].map((d) => (
                  <button
                    key={d}
                    onClick={() => setDays(d)}
                    className={`px-3 py-1.5 text-xs font-semibold transition-colors ${days === d ? "bg-white text-emerald-800" : "text-emerald-200 hover:bg-emerald-600"}`}
                  >
                    {d}d
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-96">
            <div className="w-12 h-12 border-4 border-emerald-200 border-t-emerald-600 rounded-full animate-spin mb-4" />
            <p className="text-gray-500 font-medium">Analysing complaint patterns…</p>
            <p className="text-gray-400 text-xs mt-1">Scoring zones by recency, recurrence, and resolution failure</p>
          </div>
        ) : data?.empty_reason ? (
          <div className="flex flex-col items-center justify-center h-64 bg-white rounded-2xl border border-dashed border-gray-200">
            <span className="text-4xl mb-3">🗺️</span>
            <p className="text-gray-600 font-semibold text-center max-w-sm">{data.empty_reason}</p>
          </div>
        ) : (
          <div className="flex flex-col lg:flex-row gap-6">
            {/* ── LEFT: Zone cards ─────────────────────────────────────────── */}
            <div className="w-full lg:w-2/5 space-y-4">
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4">
                <h2 className="font-bold text-gray-800 text-sm mb-0.5">Infrastructure Opportunities</h2>
                <p className="text-xs text-gray-400">
                  Based on {data?.total_tickets_analyzed} tickets from the last {data?.analysis_period_days} days
                </p>
              </div>

              {data?.zones.map((zone, idx) => {
                const col = scoreColor(zone.opportunity_score);
                const isSelected = selectedZone === zone.cell_id;
                const label = ZONE_LABELS[idx] ?? `Z${idx + 1}`;

                return (
                  <motion.div
                    key={zone.cell_id}
                    initial={{ opacity: 0, x: -16 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.08 }}
                    ref={(el) => { cardRefs.current[zone.cell_id] = el; }}
                    onClick={() => setSelectedZone(isSelected ? null : zone.cell_id)}
                    className={`bg-white rounded-2xl border shadow-sm p-5 cursor-pointer transition-all ${
                      isSelected ? "border-emerald-400 ring-2 ring-emerald-100 shadow-md" : "border-gray-100 hover:border-gray-200"
                    }`}
                  >
                    {/* Header row */}
                    <div className="flex items-start gap-3 mb-3">
                      <div
                        className="w-9 h-9 rounded-xl flex items-center justify-center font-extrabold text-base shrink-0"
                        style={{ backgroundColor: col.bg, color: "#fff" }}
                      >
                        {label}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-bold text-gray-800 text-sm">Zone {label}</span>
                          <span
                            className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                            style={{ backgroundColor: col.bg + "22", color: col.bg }}
                          >
                            {col.label}
                          </span>
                          <span className="ml-auto font-extrabold text-lg" style={{ color: col.bg }}>
                            {zone.opportunity_score}
                          </span>
                        </div>
                        <p className="text-xs text-emerald-700 font-semibold mt-0.5 truncate">
                          ◈ {zone.infrastructure_recommendation}
                        </p>
                      </div>
                    </div>

                    {/* AI narrative */}
                    <p className="text-xs text-gray-600 leading-relaxed mb-3">{zone.ai_narrative}</p>

                    {/* Category breakdown bar */}
                    <div className="mb-1">
                      <p className="text-[10px] text-gray-400 font-medium mb-1">Category breakdown</p>
                      <CategoryBar breakdown={zone.category_breakdown} />
                      <div className="flex gap-3 flex-wrap mt-1.5">
                        {Object.entries(zone.category_breakdown).map(([cat, count]) => (
                          <div key={cat} className="flex items-center gap-1">
                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: CAT_COLORS[cat] ?? "#6b7280" }} />
                            <span className="text-[10px] text-gray-500">{cat} ({count})</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Stats row */}
                    <div className="flex gap-4 mt-3 pb-3 border-b border-gray-50">
                      <div className="text-center">
                        <p className="text-xs font-bold text-red-600">{Math.round(zone.resolution_failure_rate * 100)}%</p>
                        <p className="text-[10px] text-gray-400">Resolution failure</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs font-bold text-purple-700">{zone.recurrence_score}</p>
                        <p className="text-[10px] text-gray-400">Recurrence events</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs font-bold text-gray-700">{zone.complaint_volume}</p>
                        <p className="text-[10px] text-gray-400">Total complaints</p>
                      </div>
                    </div>

                    {/* CTA */}
                    <a
                      href={`/councillor/proposal?zone_id=${zone.cell_id}&dominant_category=${zone.dominant_category}&cell_center_lat=${zone.cell_center.lat}&cell_center_lng=${zone.cell_center.lng}&ward_id=${data?.ward_id}&recommendation_text=${encodeURIComponent(zone.infrastructure_recommendation)}`}
                      onClick={(e) => e.stopPropagation()}
                      className="mt-3 w-full flex items-center justify-center gap-2 text-xs font-semibold py-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 text-white hover:shadow-md transition-all"
                    >
                      Generate proposal for this zone →
                    </a>
                  </motion.div>
                );
              })}
            </div>

            {/* ── RIGHT: Map ──────────────────────────────────────────────── */}
            <div className="w-full lg:w-3/5 lg:sticky lg:top-6" style={{ height: "calc(100vh - 140px)" }}>
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden h-full">
                <MapView
                  zones={data?.zones ?? []}
                  selectedZone={selectedZone}
                  onZoneClick={handleZoneClick}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
