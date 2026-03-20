"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { commissionerApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const PATTERN_LABELS: Record<string, string> = {
  geographic_cluster: "Geographic Cluster",
  recurrence_spike: "Recurrence Spike",
  department_collapse: "Dept Collapse",
  sentiment_drop: "Sentiment Drop",
};
const SEVERITY_COLORS: Record<string, string> = {
  high: "bg-red-500/15 text-red-400 border-red-500/30",
  medium: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  low: "bg-blue-500/15 text-blue-400 border-blue-500/30",
};
const PATTERN_ICONS: Record<string, string> = {
  geographic_cluster: "📍",
  recurrence_spike: "🔁",
  department_collapse: "📉",
  sentiment_drop: "😟",
};

export default function IntelligencePage() {
  const { user, isCommissioner } = useAuth();
  const router = useRouter();
  const [alerts, setAlerts] = useState<any[]>([]);
  const [counts, setCounts] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [statusFilter, setStatusFilter] = useState("new,acknowledged");
  const [patternFilter, setPatternFilter] = useState("");
  const [selected, setSelected] = useState<any>(null);
  const [acknowledging, setAcknowledging] = useState(false);
  const [note, setNote] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [alertRes, countRes] = await Promise.all([
        commissionerApi.getIntelligenceAlerts(statusFilter, patternFilter || undefined, page, 20),
        commissionerApi.getIntelligenceAlertCounts(),
      ]);
      setAlerts(alertRes.data.alerts || []);
      setTotal(alertRes.data.total || 0);
      setCounts(countRes.data);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, patternFilter, page]);

  useEffect(() => { load(); }, [load]);

  const runDetection = async () => {
    setRunning(true);
    try {
      await commissionerApi.runDetection();
      await new Promise(r => setTimeout(r, 2000));
      await load();
    } finally { setRunning(false); }
  };

  const handleAcknowledge = async (action: string) => {
    if (!selected || !user) return;
    setAcknowledging(true);
    try {
      await commissionerApi.acknowledgeAlert(selected.alert_id, {
        commissioner_id: user.id, commissioner_name: user.name, note, action,
      });
      setSelected(null);
      setNote("");
      await load();
    } finally { setAcknowledging(false); }
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
        <div className="flex items-center justify-between mb-8">
          <div>
            <button onClick={() => router.push("/commissioner")} className="text-gray-400 text-sm mb-2 hover:text-white flex items-center gap-1">
              ← Back
            </button>
            <h1 className="text-2xl font-bold text-white">Systemic Issue Detector</h1>
            <p className="text-gray-400 text-sm mt-1">AI-detected patterns requiring commissioner attention</p>
          </div>
          <button
            onClick={runDetection}
            disabled={running}
            className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
          >
            {running ? (<><span className="animate-spin">⟳</span> Scanning…</>) : "⚡ Run Detection Now"}
          </button>
        </div>

        {/* Counts */}
        {counts && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {[
              { label: "New Alerts", value: counts.new, color: "text-red-400" },
              { label: "Acknowledged", value: counts.acknowledged, color: "text-amber-400" },
              { label: "High Severity", value: counts.high_severity, color: "text-orange-400" },
              { label: "Last Scan", value: counts.last_run ? new Date(counts.last_run).toLocaleDateString() : "Never", color: "text-gray-300" },
            ].map(c => (
              <div key={c.label} className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
                <p className="text-xs text-gray-400 mb-1">{c.label}</p>
                <p className={`text-2xl font-bold ${c.color}`}>{c.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap gap-3 mb-6">
          <div className="flex gap-2">
            {["new,acknowledged", "new", "acknowledged", "actioned,resolved"].map(s => (
              <button key={s} onClick={() => { setStatusFilter(s); setPage(1); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${statusFilter === s ? "bg-violet-600 border-violet-500 text-white" : "bg-[#161b22] border-[#30363d] text-gray-400 hover:text-white"}`}>
                {s === "new,acknowledged" ? "Active" : s === "actioned,resolved" ? "Resolved" : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
          <select
            value={patternFilter}
            onChange={e => { setPatternFilter(e.target.value); setPage(1); }}
            className="bg-[#161b22] border border-[#30363d] text-gray-300 rounded-lg px-3 py-1.5 text-xs"
          >
            <option value="">All Patterns</option>
            {Object.entries(PATTERN_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>

        {/* Alert list */}
        {loading ? (
          <div className="flex justify-center py-20"><div className="animate-spin text-3xl">⟳</div></div>
        ) : alerts.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            <p className="text-4xl mb-3">🛡️</p>
            <p className="font-medium">No alerts found</p>
            <p className="text-sm mt-1">Run detection to scan for systemic patterns</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert: any) => (
              <button
                key={alert.alert_id}
                onClick={() => setSelected(alert)}
                className="w-full text-left bg-[#161b22] border border-[#30363d] hover:border-[#58a6ff]/40 rounded-xl p-5 transition-all"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 flex-1">
                    <span className="text-2xl mt-0.5">{PATTERN_ICONS[alert.pattern_type] || "⚠️"}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className={`text-xs px-2 py-0.5 rounded border font-medium ${SEVERITY_COLORS[alert.severity] || ""}`}>
                          {alert.severity?.toUpperCase()}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded bg-[#0d1117] border border-[#30363d] text-gray-400">
                          {PATTERN_LABELS[alert.pattern_type] || alert.pattern_type}
                        </span>
                        {alert.affected_area_label && (
                          <span className="text-xs text-gray-500">{alert.affected_area_label}</span>
                        )}
                      </div>
                      <p className="text-sm text-white font-medium">{alert.summary}</p>
                      {alert.recommended_action && (
                        <p className="text-xs text-violet-400 mt-1">→ {alert.recommended_action}</p>
                      )}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs text-gray-500">{new Date(alert.created_at).toLocaleDateString()}</p>
                    <span className={`text-xs px-2 py-0.5 rounded mt-1 inline-block ${alert.status === "new" ? "bg-red-500/20 text-red-400" : "bg-gray-700 text-gray-400"}`}>
                      {alert.status}
                    </span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Pagination */}
        {total > 20 && (
          <div className="flex justify-center gap-3 mt-6">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="px-4 py-2 bg-[#161b22] border border-[#30363d] rounded-lg text-sm disabled:opacity-40">← Prev</button>
            <span className="px-4 py-2 text-sm text-gray-400">Page {page} of {Math.ceil(total / 20)}</span>
            <button onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / 20)}
              className="px-4 py-2 bg-[#161b22] border border-[#30363d] rounded-lg text-sm disabled:opacity-40">Next →</button>
          </div>
        )}
      </div>

      {/* Alert detail modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-end md:items-center justify-center p-4">
          <div className="bg-[#161b22] border border-[#30363d] rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-[#161b22] border-b border-[#30363d] px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xl">{PATTERN_ICONS[selected.pattern_type]}</span>
                <h2 className="font-semibold text-white">{PATTERN_LABELS[selected.pattern_type]}</h2>
                <span className={`text-xs px-2 py-0.5 rounded border ${SEVERITY_COLORS[selected.severity]}`}>{selected.severity?.toUpperCase()}</span>
              </div>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-white text-xl">✕</button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <p className="text-xs text-gray-400 mb-1 uppercase tracking-wider">Summary</p>
                <p className="text-white text-sm">{selected.summary}</p>
              </div>
              {selected.detail && (
                <div>
                  <p className="text-xs text-gray-400 mb-1 uppercase tracking-wider">Detail</p>
                  <p className="text-gray-300 text-sm">{selected.detail}</p>
                </div>
              )}
              {selected.recommended_action && (
                <div className="bg-violet-500/10 border border-violet-500/30 rounded-lg p-3">
                  <p className="text-xs text-violet-400 mb-1">Recommended Action</p>
                  <p className="text-white text-sm">{selected.recommended_action}</p>
                </div>
              )}
              {selected.evidence && Object.keys(selected.evidence).length > 0 && (
                <div>
                  <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">Evidence</p>
                  <pre className="bg-[#0d1117] rounded-lg p-3 text-xs text-gray-300 overflow-x-auto">
                    {JSON.stringify(selected.evidence, null, 2)}
                  </pre>
                </div>
              )}
              {selected.status === "new" || selected.status === "acknowledged" ? (
                <div className="border-t border-[#30363d] pt-4 space-y-3">
                  <p className="text-xs text-gray-400 uppercase tracking-wider">Your Response</p>
                  <textarea
                    value={note}
                    onChange={e => setNote(e.target.value)}
                    placeholder="Add a note (optional)…"
                    rows={2}
                    className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-white resize-none focus:border-violet-500 focus:outline-none"
                  />
                  <div className="flex gap-2 flex-wrap">
                    {selected.status === "new" && (
                      <button onClick={() => handleAcknowledge("acknowledge")} disabled={acknowledging}
                        className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                        Acknowledge
                      </button>
                    )}
                    <button onClick={() => handleAcknowledge("actioned")} disabled={acknowledging}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                      Mark Actioned
                    </button>
                    <button onClick={() => handleAcknowledge("resolved")} disabled={acknowledging}
                      className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                      Mark Resolved
                    </button>
                  </div>
                </div>
              ) : (
                <div className="border-t border-[#30363d] pt-4">
                  <p className="text-xs text-gray-500">Acknowledged by {selected.acknowledged_by_name} on {selected.acknowledged_at ? new Date(selected.acknowledged_at).toLocaleDateString() : "—"}</p>
                  {selected.commissioner_note && <p className="text-sm text-gray-400 mt-1">Note: {selected.commissioner_note}</p>}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
