"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { commissionerApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const URGENCY_COLORS: Record<string, string> = {
  high: "bg-red-500/15 text-red-400 border-red-500/30",
  medium: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  normal: "bg-blue-500/15 text-blue-400 border-blue-500/30",
};
const STATUS_COLORS: Record<string, string> = {
  received: "text-blue-400",
  acknowledged: "text-yellow-400",
  in_progress: "text-orange-400",
  responded: "text-green-400",
  closed: "text-gray-500",
};
const ESCALATION_TYPES: Record<string, string> = {
  constituent_complaint: "Constituent Complaint",
  infrastructure_failure: "Infrastructure Failure",
  contractor_dispute: "Contractor Dispute",
  inter_department: "Inter-department",
  scheme_issue: "Scheme Issue",
  other: "Other",
};

export default function EscalationsPage() {
  const { user, isCommissioner } = useAuth();
  const router = useRouter();
  const [escalations, setEscalations] = useState<any[]>([]);
  const [counts, setCounts] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [urgencyFilter, setUrgencyFilter] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [responding, setResponding] = useState(false);
  const [responseForm, setResponseForm] = useState({ action_type: "response_sent", response_text: "", assigned_dept_id: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [escRes, countRes] = await Promise.all([
        commissionerApi.getEscalations({ status: statusFilter || undefined, urgency: urgencyFilter || undefined, page, limit: 20 }),
        commissionerApi.getEscalationCounts(),
      ]);
      setEscalations(escRes.data.escalations || []);
      setTotal(escRes.data.total || 0);
      setCounts(countRes.data);
    } finally { setLoading(false); }
  }, [statusFilter, urgencyFilter, page]);

  useEffect(() => { load(); }, [load]);

  const openDetail = async (esc: any) => {
    setDetailLoading(true);
    setSelected(null);
    try {
      const res = await commissionerApi.getEscalation(esc.escalation_id);
      setSelected(res.data);
    } finally { setDetailLoading(false); }
  };

  const handleRespond = async () => {
    if (!selected || !user) return;
    setResponding(true);
    try {
      await commissionerApi.respondEscalation(selected.escalation_id, {
        commissioner_id: user.id, commissioner_name: user.name,
        ...responseForm,
      });
      const res = await commissionerApi.getEscalation(selected.escalation_id);
      setSelected(res.data);
      await load();
    } finally { setResponding(false); }
  };

  const handleClose = async () => {
    if (!selected || !user) return;
    if (!confirm("Close this escalation?")) return;
    try {
      await commissionerApi.closeEscalation(selected.escalation_id, user.id);
      setSelected(null);
      await load();
    } catch {}
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
          <button onClick={() => router.push("/commissioner")} className="text-gray-400 text-sm mb-2 hover:text-white flex items-center gap-1">
            ← Back
          </button>
          <h1 className="text-2xl font-bold">Councillor Escalation Manager</h1>
          <p className="text-gray-400 text-sm mt-1">Manage issues escalated from ward councillors</p>
        </div>

        {/* Counts */}
        {counts && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {[
              { label: "Total Open", value: counts.total_open, color: "text-white" },
              { label: "High Urgency", value: counts.high_urgency, color: "text-red-400" },
              { label: "SLA Breached", value: counts.sla_breached, color: "text-orange-400" },
              { label: "Awaiting Response", value: counts.awaiting_response, color: "text-amber-400" },
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
            {[
              { label: "All Open", value: "" },
              { label: "Received", value: "received" },
              { label: "In Progress", value: "in_progress" },
              { label: "Responded", value: "responded" },
              { label: "Closed", value: "closed" },
            ].map(f => (
              <button key={f.value} onClick={() => { setStatusFilter(f.value); setPage(1); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${statusFilter === f.value ? "bg-violet-600 border-violet-500 text-white" : "bg-[#161b22] border-[#30363d] text-gray-400 hover:text-white"}`}>
                {f.label}
              </button>
            ))}
          </div>
          <select value={urgencyFilter} onChange={e => { setUrgencyFilter(e.target.value); setPage(1); }}
            className="bg-[#161b22] border border-[#30363d] text-gray-300 rounded-lg px-3 py-1.5 text-xs">
            <option value="">All Urgency</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="normal">Normal</option>
          </select>
        </div>

        {/* List */}
        {loading ? (
          <div className="flex justify-center py-20"><div className="animate-spin text-3xl">⟳</div></div>
        ) : escalations.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            <p className="text-4xl mb-3">📬</p>
            <p className="font-medium">No escalations found</p>
          </div>
        ) : (
          <div className="space-y-3">
            {escalations.map((esc: any) => (
              <button key={esc.escalation_id} onClick={() => openDetail(esc)}
                className="w-full text-left bg-[#161b22] border border-[#30363d] hover:border-[#58a6ff]/40 rounded-xl p-5 transition-all">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className={`text-xs px-2 py-0.5 rounded border font-medium ${URGENCY_COLORS[esc.urgency] || ""}`}>
                        {esc.urgency?.toUpperCase()}
                      </span>
                      {esc.sla_breached && (
                        <span className="text-xs px-2 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/30 font-bold">
                          SLA BREACHED
                        </span>
                      )}
                      <span className="text-xs text-gray-500">{ESCALATION_TYPES[esc.escalation_type] || esc.escalation_type}</span>
                    </div>
                    <p className="font-medium text-white text-sm">{esc.subject}</p>
                    <p className="text-gray-400 text-xs mt-0.5">From: {esc.from_councillor_name} · Ward: {esc.ward_name}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className={`text-xs font-medium ${STATUS_COLORS[esc.status] || "text-gray-400"}`}>{esc.status?.replace("_", " ")}</p>
                    {esc.hours_remaining != null && esc.status !== "closed" && (
                      <p className={`text-xs mt-0.5 ${esc.sla_breached ? "text-red-400" : "text-gray-500"}`}>
                        {esc.sla_breached ? `${Math.abs(esc.hours_remaining).toFixed(0)}h overdue` : `${esc.hours_remaining.toFixed(0)}h left`}
                      </p>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

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

      {/* Detail modal */}
      {(selected || detailLoading) && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-end md:items-center justify-center p-4">
          {detailLoading ? (
            <div className="bg-[#161b22] rounded-2xl p-8"><div className="animate-spin text-3xl">⟳</div></div>
          ) : selected ? (
            <div className="bg-[#161b22] border border-[#30363d] rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
              <div className="sticky top-0 bg-[#161b22] border-b border-[#30363d] px-6 py-4 flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-white">{selected.subject}</h2>
                  <p className="text-xs text-gray-400">#{selected.escalation_id} · By {selected.from_councillor_name} · Ward {selected.ward_name}</p>
                </div>
                <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-white text-xl">✕</button>
              </div>
              <div className="p-6 space-y-4">
                <div className="flex gap-2 flex-wrap">
                  <span className={`text-xs px-2 py-1 rounded border ${URGENCY_COLORS[selected.urgency]}`}>{selected.urgency?.toUpperCase()} URGENCY</span>
                  <span className={`text-xs px-2 py-1 rounded bg-[#0d1117] border-[#30363d] border ${STATUS_COLORS[selected.status]}`}>{selected.status?.replace("_", " ")}</span>
                  {selected.sla_breached && <span className="text-xs px-2 py-1 rounded bg-red-500/20 text-red-300 border border-red-500/30">SLA BREACHED</span>}
                </div>

                <div>
                  <p className="text-xs text-gray-400 mb-1">Description</p>
                  <p className="text-sm text-white">{selected.description}</p>
                </div>

                {selected.commissioner_response?.response_text && (
                  <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                    <p className="text-xs text-green-400 mb-1">Commissioner Response</p>
                    <p className="text-sm text-white">{selected.commissioner_response.response_text}</p>
                    <p className="text-xs text-gray-400 mt-1">By {selected.commissioner_response.responding_commissioner_name} · {new Date(selected.commissioner_response.responded_at).toLocaleDateString()}</p>
                  </div>
                )}

                {/* Timeline */}
                {selected.timeline?.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">Timeline</p>
                    <div className="space-y-2">
                      {selected.timeline.map((ev: any, i: number) => (
                        <div key={i} className="flex gap-2 text-xs text-gray-300">
                          <span className="text-gray-500 shrink-0">{new Date(ev.timestamp).toLocaleString()}</span>
                          <span className="text-violet-400 shrink-0">{ev.actor}:</span>
                          <span>{ev.event}{ev.note ? ` — ${ev.note}` : ""}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Respond form */}
                {["received", "acknowledged", "in_progress"].includes(selected.status) && (
                  <div className="border-t border-[#30363d] pt-4 space-y-3">
                    <p className="text-xs text-gray-400 uppercase tracking-wider">Respond</p>
                    <select value={responseForm.action_type} onChange={e => setResponseForm(f => ({ ...f, action_type: e.target.value }))}
                      className="w-full bg-[#0d1117] border border-[#30363d] text-gray-300 rounded-lg px-3 py-2 text-sm">
                      <option value="response_sent">Send Response</option>
                      <option value="direct_resolution">Direct Resolution</option>
                      <option value="dept_assignment">Assign to Department</option>
                    </select>
                    {responseForm.action_type === "dept_assignment" && (
                      <select value={responseForm.assigned_dept_id} onChange={e => setResponseForm(f => ({ ...f, assigned_dept_id: e.target.value }))}
                        className="w-full bg-[#0d1117] border border-[#30363d] text-gray-300 rounded-lg px-3 py-2 text-sm">
                        <option value="">Select department…</option>
                        {[["roads", "Roads & Infrastructure"], ["water_drainage", "Water & Drainage"], ["electrical", "Electrical"],
                          ["sanitation", "Sanitation"], ["general", "General Services"]].map(([id, name]) => (
                          <option key={id} value={id}>{name}</option>
                        ))}
                      </select>
                    )}
                    <textarea value={responseForm.response_text} onChange={e => setResponseForm(f => ({ ...f, response_text: e.target.value }))}
                      placeholder="Your response…" rows={3}
                      className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-white resize-none focus:border-violet-500 focus:outline-none" />
                    <div className="flex gap-2">
                      <button onClick={handleRespond} disabled={responding || !responseForm.response_text}
                        className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                        {responding ? "Sending…" : "Send Response"}
                      </button>
                      <button onClick={handleClose}
                        className="px-4 py-2 bg-[#0d1117] border border-[#30363d] text-gray-400 hover:text-white rounded-lg text-sm">
                        Close Escalation
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
