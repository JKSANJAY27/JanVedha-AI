"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { caseworkApi } from "@/lib/api";

interface FollowUp {
  follow_up_id: string;
  generated_at: string;
  language: string;
  english_text: string | null;
  tamil_text: string | null;
  sent: boolean;
  sent_at: string | null;
  sent_via: string | null;
}

interface LinkedTicket {
  id: string;
  ticket_code: string;
  description: string;
  issue_category: string;
  status: string;
  priority_label: string | null;
  assigned_officer_id: string | null;
  created_at: string;
}

interface CaseworkDetail {
  casework_id: string;
  ward_id: number;
  councillor_name: string | null;
  constituent: {
    name: string | null;
    phone: string | null;
    address: string | null;
    preferred_language: string;
  };
  complaint: {
    description: string;
    category: string | null;
    location_description: string | null;
    urgency: string;
    how_received: string;
  };
  voice_note: { transcript: string | null };
  linked_ticket_id: string | null;
  ticket_created: boolean;
  follow_ups: FollowUp[];
  status: string;
  escalation_flag: boolean;
  escalation_reason: string | null;
  notes: string | null;
  created_at: string;
  linked_ticket?: LinkedTicket;
}

interface TicketCandidate {
  ticket_id: string;
  title: string;
  description: string;
  category: string;
  status: string;
  created_at: string;
  match_score: number;
}

const CATEGORY_COLORS: Record<string, string> = {
  roads: "bg-orange-100 text-orange-700",
  water: "bg-blue-100 text-blue-700",
  lighting: "bg-yellow-100 text-yellow-700",
  drainage: "bg-teal-100 text-teal-700",
  waste: "bg-green-100 text-green-700",
  scheme_enquiry: "bg-purple-100 text-purple-700",
  general: "bg-gray-100 text-gray-700",
  other: "bg-slate-100 text-slate-700",
};

const STATUS_BADGE: Record<string, string> = {
  logged: "bg-gray-100 text-gray-600",
  ticket_linked: "bg-blue-100 text-blue-700",
  ticket_created: "bg-blue-100 text-blue-700",
  follow_up_sent: "bg-emerald-100 text-emerald-700",
  escalated: "bg-red-100 text-red-700",
  resolved: "bg-gray-100 text-gray-500",
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days === 1) return "Yesterday";
  return `${days}d ago`;
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).catch(() => {});
}

export default function CaseworkDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();

  const [cw, setCw] = useState<CaseworkDetail | null>(null);
  const [candidates, setCandidates] = useState<TicketCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [followUpLang, setFollowUpLang] = useState<"english" | "tamil" | "both">("both");
  const [draftLoading, setDraftLoading] = useState(false);
  const [currentDraft, setCurrentDraft] = useState<{ id: string; english: string | null; tamil: string | null } | null>(null);
  const [sentPicker, setSentPicker] = useState(false);
  const [constituentHistory, setConstituentHistory] = useState<any[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [isFallback, setIsFallback] = useState(false);

  // New ticket form
  const [createTitle, setCreateTitle] = useState("");
  const [creatingTicket, setCreatingTicket] = useState(false);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const loadDetail = async () => {
    setLoading(true);
    try {
      const res = await caseworkApi.get(id);
      const data: CaseworkDetail = res.data;
      setCw(data);
      if (data.follow_ups.length > 0) {
        const last = data.follow_ups[data.follow_ups.length - 1];
        setCurrentDraft({ id: last.follow_up_id, english: last.english_text, tamil: last.tamil_text });
      }
      // Load ticket candidates if not yet linked
      if (!data.linked_ticket_id && data.complaint.category && data.complaint.description) {
        const cRes = await caseworkApi.matchTickets(data.ward_id, data.complaint.category, data.complaint.description.slice(0, 200));
        setCandidates(cRes.data.candidates ?? []);
      }
      // Load constituent history
      if (data.constituent.phone) {
        const hRes = await caseworkApi.getConstituentHistory(data.constituent.phone, data.ward_id);
        setConstituentHistory(hRes.data.casework ?? []);
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { loadDetail(); }, [id]);

  const linkTicket = async (ticketId: string) => {
    try {
      await caseworkApi.linkTicket(id, ticketId);
      showToast("Ticket linked successfully!");
      loadDetail();
    } catch {
      showToast("Failed to link ticket.");
    }
  };

  const createTicket = async () => {
    setCreatingTicket(true);
    try {
      const res = await caseworkApi.createTicket(id, createTitle || undefined);
      showToast(`Ticket created: ${res.data.ticket_code}`);
      loadDetail();
    } catch { showToast("Failed to create ticket."); }
    setCreatingTicket(false);
  };

  const generateDraft = async () => {
    setDraftLoading(true);
    try {
      const res = await caseworkApi.draftFollowup(id, followUpLang);
      const d = res.data;
      setCurrentDraft({ id: d.follow_up_id, english: d.english, tamil: d.tamil });
      setIsFallback(d.is_fallback ?? false);
      loadDetail();
    } catch { showToast("Failed to generate draft."); }
    setDraftLoading(false);
  };

  const markSent = async (via: string) => {
    if (!currentDraft) return;
    try {
      await caseworkApi.markSent(id, currentDraft.id, via);
      setSentPicker(false); showToast("Marked as sent!"); loadDetail();
    } catch { showToast("Failed to update."); }
  };

  const matchLabel = (score: number) =>
    score >= 70 ? { label: "Strong match", cls: "bg-emerald-100 text-emerald-700" }
      : score >= 50 ? { label: "Possible match", cls: "bg-yellow-100 text-yellow-700" }
        : { label: "Weak match", cls: "bg-gray-100 text-gray-500" };

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="w-10 h-10 border-4 border-emerald-200 border-t-emerald-600 rounded-full animate-spin" />
    </div>
  );

  if (!cw) return (
    <div className="flex items-center justify-center min-h-screen text-gray-400">Casework entry not found.</div>
  );

  const lastFollowUpSent = cw.follow_ups.find((f) => f.sent);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-emerald-600 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg">
          {toast}
        </div>
      )}

      {/* Page header */}
      <div className="bg-gradient-to-r from-emerald-700 to-teal-800 text-white px-6 py-4">
        <div className="max-w-6xl mx-auto">
          <button onClick={() => router.push("/councillor/casework")} className="text-emerald-300 hover:text-white text-sm transition-colors mb-1">← Back to inbox</button>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold">{cw.constituent.name ?? "Constituent"}</h1>
            <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${STATUS_BADGE[cw.status] ?? "bg-gray-100 text-gray-500"}`}>
              {cw.status.replace("_", " ")}
            </span>
            {cw.escalation_flag && <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-red-100 text-red-700">🚨 Escalation</span>}
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── LEFT SIDEBAR ── */}
        <div className="space-y-4">
          {cw.escalation_flag && (
            <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-sm">
              <p className="font-bold text-red-700 mb-1">⚠️ Escalation active</p>
              <p className="text-red-600">{cw.escalation_reason}</p>
            </div>
          )}

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 space-y-3">
            <div>
              <p className="text-xs text-gray-400 font-semibold">Phone</p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="font-mono text-sm text-gray-800">{cw.constituent.phone}</span>
                <button onClick={() => copyToClipboard(cw.constituent.phone ?? "")} className="text-xs text-gray-400 hover:text-gray-700">📋</button>
                {cw.constituent.phone && (
                  <a
                    href={`https://wa.me/91${cw.constituent.phone}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-emerald-600 hover:underline"
                  >
                    WhatsApp →
                  </a>
                )}
              </div>
            </div>

            {cw.constituent.address && (
              <div>
                <p className="text-xs text-gray-400 font-semibold">Address</p>
                <p className="text-sm text-gray-700">{cw.constituent.address}</p>
              </div>
            )}

            <div className="flex gap-4">
              <div>
                <p className="text-xs text-gray-400 font-semibold">Received via</p>
                <p className="text-sm text-gray-700 capitalize">{cw.complaint.how_received.replace("_", " ")}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400 font-semibold">Logged</p>
                <p className="text-sm text-gray-700">{timeAgo(cw.created_at)}</p>
              </div>
            </div>

            <div className="flex gap-4">
              <div>
                <p className="text-xs text-gray-400 font-semibold">Category</p>
                <span className={`inline-block text-xs font-bold mt-0.5 px-2 py-0.5 rounded-full ${CATEGORY_COLORS[cw.complaint.category ?? ""] ?? "bg-gray-100 text-gray-600"}`}>
                  {cw.complaint.category}
                </span>
              </div>
              <div>
                <p className="text-xs text-gray-400 font-semibold">Urgency</p>
                <p className="text-sm font-semibold text-gray-700 capitalize mt-0.5">{cw.complaint.urgency}</p>
              </div>
            </div>

            {cw.notes && (
              <div>
                <p className="text-xs text-gray-400 font-semibold">Notes</p>
                <p className="text-sm text-gray-700 mt-0.5">{cw.notes}</p>
              </div>
            )}
          </div>
        </div>

        {/* ── MAIN CONTENT ── */}
        <div className="lg:col-span-1 space-y-5">
          {/* Section 1: Complaint */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <h2 className="font-bold text-gray-800 text-sm mb-3">📋 What they told you</h2>
            <div className="bg-slate-50 rounded-xl p-3 text-sm text-gray-700 leading-relaxed border border-slate-100">
              {cw.complaint.description}
            </div>
            {cw.complaint.location_description && (
              <p className="text-xs text-gray-400 mt-2">📍 {cw.complaint.location_description}</p>
            )}
            {cw.voice_note.transcript && (
              <details className="mt-3">
                <summary className="text-xs text-indigo-600 font-semibold cursor-pointer">Voice note transcript</summary>
                <p className="text-xs text-gray-500 mt-2 leading-relaxed">{cw.voice_note.transcript}</p>
              </details>
            )}
          </div>

          {/* Section 2: Ticket */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <h2 className="font-bold text-gray-800 text-sm mb-4">🎫 Ticket</h2>

            {cw.linked_ticket_id ? (
              /* Linked ticket status card */
              <div className="border border-blue-100 rounded-xl p-4 bg-blue-50">
                <p className="text-xs text-blue-500 font-semibold mb-1">Linked ticket</p>
                {cw.linked_ticket ? (
                  <>
                    <p className="font-bold text-blue-900 text-sm">{cw.linked_ticket.ticket_code}</p>
                    <p className="text-xs text-gray-600 mt-0.5 mb-2">{cw.linked_ticket.description?.slice(0, 100)}</p>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${CATEGORY_COLORS[cw.linked_ticket.issue_category ?? ""] ?? "bg-gray-100 text-gray-600"}`}>
                        {cw.linked_ticket.issue_category}
                      </span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-white border border-blue-200 text-blue-700 capitalize">
                        {cw.linked_ticket.status.toLowerCase().replace("_", " ")}
                      </span>
                      {cw.linked_ticket.assigned_officer_id && (
                        <span className="text-[10px] text-gray-500">👤 {cw.linked_ticket.assigned_officer_id}</span>
                      )}
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-gray-600">Ticket ID: {cw.linked_ticket_id}</p>
                )}
              </div>
            ) : (
              /* Link or create options */
              <div className="space-y-4">
                {/* Candidate matching */}
                <div>
                  <p className="text-xs font-semibold text-gray-500 mb-2">Match existing ticket</p>
                  {candidates.length === 0 ? (
                    <p className="text-xs text-gray-400 italic">No matching tickets found in this ward.</p>
                  ) : (
                    <div className="space-y-2">
                      {candidates.map((tc) => {
                        const ml = matchLabel(tc.match_score);
                        return (
                          <div key={tc.ticket_id} className="border border-gray-100 rounded-xl p-3 flex items-start gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1 flex-wrap">
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${ml.cls}`}>{ml.label}</span>
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${CATEGORY_COLORS[tc.category ?? ""] ?? "bg-gray-100 text-gray-600"}`}>{tc.category}</span>
                              </div>
                              <p className="text-xs text-gray-700 line-clamp-2">{tc.description?.slice(0, 120)}</p>
                            </div>
                            <button
                              onClick={() => linkTicket(tc.ticket_id)}
                              className="shrink-0 text-xs font-bold text-emerald-700 border border-emerald-200 rounded-lg px-2.5 py-1.5 hover:bg-emerald-50 transition-colors"
                            >
                              Link
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Create ticket */}
                <div>
                  <p className="text-xs font-semibold text-gray-500 mb-2">Or create a new ticket</p>
                  <input
                    type="text"
                    value={createTitle}
                    onChange={(e) => setCreateTitle(e.target.value)}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-400 mb-2"
                    placeholder="Ticket title (leave blank for AI-generated)"
                  />
                  <button
                    onClick={createTicket}
                    disabled={creatingTicket}
                    className="w-full py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-colors disabled:opacity-50"
                  >
                    {creatingTicket ? "Creating…" : "Create ticket"}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Section 3: Follow-up */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <h2 className="font-bold text-gray-800 text-sm mb-4">✉️ Draft follow-up message</h2>

            {/* Language selector */}
            <div className="flex gap-2 mb-4">
              {(["english", "tamil", "both"] as const).map((l) => (
                <button
                  key={l}
                  onClick={() => setFollowUpLang(l)}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${followUpLang === l ? "bg-emerald-600 border-emerald-600 text-white" : "border-gray-200 text-gray-600"}`}
                >
                  {l.charAt(0).toUpperCase() + l.slice(1)}
                </button>
              ))}
            </div>

            {!currentDraft ? (
              <div className="text-center py-4">
                <button
                  onClick={generateDraft}
                  disabled={draftLoading}
                  className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold transition-colors disabled:opacity-50 flex items-center gap-2 mx-auto"
                >
                  {draftLoading ? <><span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />Drafting…</> : "Generate follow-up draft"}
                </button>
                <p className="text-xs text-gray-400 mt-2">AI will draft based on complaint details and ticket status</p>
              </div>
            ) : (
              <div className="space-y-4">
                {isFallback && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 text-xs text-amber-700">
                    AI drafting unavailable — showing template. Please edit before sending.
                  </div>
                )}

                {(followUpLang === "english" || followUpLang === "both") && currentDraft.english && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 mb-1">English version</p>
                    <textarea
                      rows={4}
                      defaultValue={currentDraft.english}
                      className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 resize-none"
                    />
                    {currentDraft.english.length > 320 && (
                      <p className="text-[10px] text-amber-600 mt-1">⚠️ Over 320 chars — WhatsApp may truncate</p>
                    )}
                  </div>
                )}

                {(followUpLang === "tamil" || followUpLang === "both") && currentDraft.tamil && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 mb-1">Tamil version</p>
                    <textarea
                      rows={4}
                      defaultValue={currentDraft.tamil}
                      className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 resize-none"
                    />
                    <p className="text-[10px] text-gray-400 mt-1">Review Tamil text before sending</p>
                  </div>
                )}

                {/* Sent info or action buttons */}
                {lastFollowUpSent ? (
                  <p className="text-xs text-emerald-600 font-semibold">✅ Follow-up sent {timeAgo(lastFollowUpSent.sent_at ?? "")}</p>
                ) : (
                  <div className="flex flex-wrap gap-2 pt-1">
                    <button onClick={generateDraft} disabled={draftLoading} className="px-3 py-1.5 text-xs font-semibold text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                      🔄 Regenerate
                    </button>
                    <button
                      onClick={() => copyToClipboard([followUpLang !== "tamil" ? currentDraft.english : null, followUpLang !== "english" ? currentDraft.tamil : null].filter(Boolean).join("\n\n"))}
                      className="px-3 py-1.5 text-xs font-semibold text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      📋 Copy
                    </button>
                    <div className="relative">
                      <button
                        onClick={() => setSentPicker(!sentPicker)}
                        className="px-3 py-1.5 text-xs font-bold bg-emerald-600 text-white rounded-lg hover:bg-emerald-500 transition-colors"
                      >
                        ✓ Mark as sent
                      </button>
                      {sentPicker && (
                        <div className="absolute left-0 top-9 bg-white border border-gray-200 rounded-xl shadow-lg text-xs z-10 overflow-hidden">
                          {["whatsapp_manual", "other"].map((via) => (
                            <button
                              key={via}
                              onClick={() => markSent(via)}
                              className="block w-full text-left px-4 py-2.5 hover:bg-gray-50 font-medium text-gray-700"
                            >
                              {via === "whatsapp_manual" ? "WhatsApp (manual)" : "Other"}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {cw.follow_ups.length > 1 && (
                  <details>
                    <summary className="text-xs text-indigo-600 font-semibold cursor-pointer">Previous drafts ({cw.follow_ups.length - 1})</summary>
                    <div className="mt-2 space-y-1">
                      {cw.follow_ups.slice(0, -1).map((fu) => (
                        <div key={fu.follow_up_id} className="text-xs text-gray-400 flex items-center gap-2">
                          <span>{timeAgo(fu.generated_at)}</span>
                          {fu.sent && <span className="text-emerald-500 font-semibold">Sent</span>}
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT PANEL: Constituent History ── */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 h-fit">
          <h2 className="font-bold text-gray-800 text-sm mb-4">🕒 Constituent history</h2>

          {cw.escalation_flag && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-xs text-red-700 mb-4">
              <p className="font-bold mb-1">Escalation — repeat complaint detected</p>
              <p>{cw.escalation_reason}</p>
            </div>
          )}

          {constituentHistory.length <= 1 ? (
            <p className="text-xs text-gray-400 italic">First interaction with this constituent</p>
          ) : (
            <div className="space-y-3">
              {constituentHistory.map((h) => (
                <div
                  key={h.casework_id}
                  onClick={() => h.casework_id !== cw.casework_id && router.push(`/councillor/casework/${h.casework_id}`)}
                  className={`border border-gray-100 rounded-xl p-3 text-xs transition-colors ${h.casework_id !== cw.casework_id ? "cursor-pointer hover:bg-gray-50" : "bg-slate-50 border-slate-200"}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-gray-400">{timeAgo(h.created_at)}</span>
                    {h.casework_id === cw.casework_id && <span className="text-[10px] bg-indigo-100 text-indigo-600 rounded px-1 font-bold">Current</span>}
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${CATEGORY_COLORS[h.complaint_category ?? ""] ?? "bg-gray-100 text-gray-600"}`}>
                      {h.complaint_category}
                    </span>
                    <span className="text-gray-500 capitalize">{h.status.replace("_", " ")}</span>
                    {h.linked_ticket_id && <span className="text-[10px] text-blue-600">🎫 Ticket</span>}
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
