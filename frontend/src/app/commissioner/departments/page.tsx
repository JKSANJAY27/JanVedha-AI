"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { commissionerApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const TREND_ICONS: Record<string, string> = { improving: "↑", worsening: "↓", stable: "→" };
const TREND_COLORS: Record<string, string> = { improving: "text-green-400", worsening: "text-red-400", stable: "text-gray-400" };
const HEALTH_COLORS: Record<string, string> = {
  Healthy: "text-green-400 bg-green-500/10 border-green-500/30",
  "Needs attention": "text-amber-400 bg-amber-500/10 border-amber-500/30",
  "At risk": "text-orange-400 bg-orange-500/10 border-orange-500/30",
  Critical: "text-red-400 bg-red-500/10 border-red-500/30",
};

function MetricRow({ label, value, sub }: { label: string; value: any; sub?: string }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-[#30363d] last:border-0">
      <span className="text-xs text-gray-400">{label}</span>
      <span className="text-sm text-white font-medium">{value ?? "—"}{sub}</span>
    </div>
  );
}

export default function DepartmentsPage() {
  const { isCommissioner } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any>(null);
  const [detail, setDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await commissionerApi.getDepartmentHealth();
      setData(res.data);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openDept = async (dept: any) => {
    setSelected(dept);
    setDetail(null);
    setDetailLoading(true);
    try {
      const res = await commissionerApi.getDepartmentDetail(dept.dept_id);
      setDetail(res.data);
    } finally { setDetailLoading(false); }
  };

  if (!isCommissioner) return (
    <div className="min-h-screen bg-[#0d1117] flex items-center justify-center">
      <p className="text-red-400">Commissioner access required.</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#0d1117] text-white">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <button onClick={() => router.push("/commissioner")} className="text-gray-400 text-sm mb-2 hover:text-white">← Back</button>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold">Department Command Center</h1>
              <p className="text-gray-400 text-sm mt-1">30-day performance vs previous period</p>
            </div>
            <button onClick={load} className="px-3 py-2 bg-[#161b22] border border-[#30363d] text-gray-400 hover:text-white rounded-lg text-sm">
              ⟳ Refresh
            </button>
          </div>
          {data?.overall_verdict && (
            <div className="mt-4 bg-[#161b22] border border-[#30363d] rounded-xl p-4">
              <p className="text-xs text-gray-400 mb-1">Gemini Overview</p>
              <p className="text-sm text-white">{data.overall_verdict}</p>
            </div>
          )}
        </div>

        {loading ? (
          <div className="flex justify-center py-20"><div className="animate-spin text-3xl">⟳</div></div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {(data?.departments || []).map((dept: any) => {
              const hc = HEALTH_COLORS[dept.health_label] || "text-gray-400 bg-gray-500/10 border-gray-500/30";
              const m = dept.metrics || {};
              return (
                <button key={dept.dept_id} onClick={() => openDept(dept)}
                  className="text-left bg-[#161b22] border border-[#30363d] hover:border-[#58a6ff]/40 rounded-xl p-5 transition-all group">
                  {/* Dept color bar */}
                  <div className="h-1 rounded-full mb-4" style={{ backgroundColor: dept.color_hex }} />

                  <div className="flex items-start justify-between mb-3">
                    <h3 className="font-semibold text-white text-sm">{dept.dept_name}</h3>
                    <span className={`text-xs px-2 py-0.5 rounded border ${hc}`}>{dept.health_label}</span>
                  </div>

                  {/* Health score bar */}
                  <div className="mb-3">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Health</span><span>{dept.health_score}/100</span>
                    </div>
                    <div className="h-1.5 bg-[#0d1117] rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all"
                        style={{ width: `${dept.health_score}%`, backgroundColor: dept.color_hex }} />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mb-3">
                    <div className="text-gray-400">Open <span className="text-white font-medium">{m.open_count ?? 0}</span></div>
                    <div className="text-gray-400">Resolved <span className="text-white font-medium">{m.resolved_count ?? 0}</span></div>
                    <div className="text-gray-400">Rate <span className="text-white font-medium">{m.resolution_rate_pct ?? 0}%</span></div>
                    <div className="text-gray-400">Avg days <span className="text-white font-medium">{m.avg_resolution_days ?? "—"}</span></div>
                    <div className="text-gray-400">Overdue <span className="text-red-400 font-medium">{m.overdue_count ?? 0}</span></div>
                    <div className="text-gray-400">SLA <span className="text-gray-300 font-medium">{dept.sla_days}d</span></div>
                  </div>

                  {m.trend_direction && (
                    <div className="flex items-center gap-1 text-xs">
                      <span className={TREND_COLORS[m.trend_direction]}>{TREND_ICONS[m.trend_direction]}</span>
                      <span className={TREND_COLORS[m.trend_direction] + " capitalize"}>{m.trend_direction}</span>
                      {m.trend_delta_days != null && (
                        <span className="text-gray-500">({m.trend_delta_days > 0 ? "+" : ""}{m.trend_delta_days}d)</span>
                      )}
                    </div>
                  )}

                  {dept.ai_verdict && dept.ai_verdict !== "Analysis unavailable" && (
                    <p className="text-xs text-gray-400 mt-3 pt-3 border-t border-[#30363d] italic">"{dept.ai_verdict}"</p>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Detail side panel */}
      {selected && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex justify-end">
          <div className="w-full max-w-xl bg-[#0d1117] border-l border-[#30363d] h-full overflow-y-auto">
            <div className="sticky top-0 bg-[#0d1117] border-b border-[#30363d] px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-white">{selected.dept_name}</h2>
                <p className="text-xs text-gray-400">30-day deep dive</p>
              </div>
              <button onClick={() => { setSelected(null); setDetail(null); }} className="text-gray-400 hover:text-white text-xl">✕</button>
            </div>
            <div className="p-6 space-y-6">
              {detailLoading ? (
                <div className="flex justify-center py-10"><div className="animate-spin text-3xl">⟳</div></div>
              ) : detail ? (
                <>
                  {/* Weekly trend chart (simple bar) */}
                  {detail.weekly_trend?.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-3 uppercase tracking-wider">6-Week Trend</p>
                      <div className="flex items-end gap-2 h-24">
                        {detail.weekly_trend.map((w: any, i: number) => {
                          const maxV = Math.max(...detail.weekly_trend.map((x: any) => Math.max(x.created, x.resolved, 1)));
                          return (
                            <div key={i} className="flex-1 flex flex-col items-center gap-1">
                              <div className="w-full flex gap-0.5 items-end" style={{ height: "80px" }}>
                                <div className="flex-1 bg-gray-600 rounded-sm"
                                  style={{ height: `${(w.created / maxV) * 80}px` }} title={`Created: ${w.created}`} />
                                <div className="flex-1 bg-green-500 rounded-sm"
                                  style={{ height: `${(w.resolved / maxV) * 80}px` }} title={`Resolved: ${w.resolved}`} />
                              </div>
                              <span className="text-xs text-gray-500 text-center">{w.week_label}</span>
                            </div>
                          );
                        })}
                      </div>
                      <div className="flex gap-4 mt-2">
                        <div className="flex items-center gap-1 text-xs text-gray-400"><div className="w-2 h-2 bg-gray-600 rounded-sm" />Created</div>
                        <div className="flex items-center gap-1 text-xs text-gray-400"><div className="w-2 h-2 bg-green-500 rounded-sm" />Resolved</div>
                      </div>
                    </div>
                  )}

                  {/* Overdue tickets */}
                  {detail.overdue_tickets?.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">⚠️ Overdue Tickets ({detail.overdue_tickets.length})</p>
                      <div className="space-y-2">
                        {detail.overdue_tickets.slice(0, 8).map((t: any) => (
                          <div key={t.ticket_id} className="flex items-center justify-between py-1.5 border-b border-[#30363d]">
                            <p className="text-xs text-gray-300 truncate flex-1 mr-2">{t.title || t.ticket_id}</p>
                            <div className="text-right shrink-0">
                              <p className="text-xs text-red-400">{t.days_overdue}d overdue</p>
                              <p className="text-xs text-gray-500">Ward {t.ward_id}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Ward breakdown */}
                  {detail.ward_breakdown?.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">Ward Breakdown (worst first)</p>
                      <div className="space-y-2">
                        {detail.ward_breakdown.slice(0, 6).map((w: any) => (
                          <div key={w.ward_id} className="bg-[#161b22] border border-[#30363d] rounded-lg p-3">
                            <div className="flex items-center justify-between mb-1">
                              <p className="text-xs font-medium text-white">Ward {w.ward_id}</p>
                              <p className="text-xs text-gray-400">{w.resolution_rate_pct}% resolved</p>
                            </div>
                            <div className="h-1 bg-[#0d1117] rounded-full overflow-hidden">
                              <div className="h-full bg-green-500 rounded-full" style={{ width: `${w.resolution_rate_pct}%` }} />
                            </div>
                            <div className="flex justify-between text-xs text-gray-500 mt-1">
                              <span>Total: {w.total}</span>
                              <span>Overdue: <span className="text-red-400">{w.overdue_count}</span></span>
                              {w.avg_resolution_days != null && <span>Avg: {w.avg_resolution_days}d</span>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Technician breakdown */}
                  {detail.technician_breakdown?.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">Technician Load</p>
                      <div className="space-y-1">
                        {detail.technician_breakdown.filter((t: any) => t.technician_id !== "unassigned").slice(0, 8).map((t: any) => (
                          <div key={t.technician_id} className="flex items-center justify-between py-1.5 border-b border-[#30363d]">
                            <p className="text-xs text-gray-300">{t.technician_id.slice(0, 8)}…</p>
                            <div className="flex gap-4 text-xs">
                              <span className="text-gray-400">Active: <span className="text-white">{t.active_ticket_count}</span></span>
                              <span className="text-gray-400">Done: <span className="text-green-400">{t.resolved_count}</span></span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
