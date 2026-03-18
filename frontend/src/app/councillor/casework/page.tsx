"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { api, caseworkApi } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

interface CaseworkEntry {
  casework_id: string;
  constituent_name: string;
  constituent_phone_masked: string;
  complaint_category: string;
  complaint_description: string;
  status: string;
  escalation_flag: boolean;
  linked_ticket_id: string | null;
  created_at: string;
  how_received: string;
}

// ── Constants ──────────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  logged: "bg-gray-200",
  ticket_linked: "bg-blue-500",
  ticket_created: "bg-blue-500",
  follow_up_sent: "bg-emerald-500",
  escalated: "bg-red-500",
  resolved: "bg-gray-300",
};

const STATUS_LABELS: Record<string, string> = {
  logged: "Logged",
  ticket_linked: "Ticket linked",
  ticket_created: "Ticket created",
  follow_up_sent: "Follow-up sent",
  escalated: "Escalated",
  resolved: "Resolved",
};

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

const RECEIVED_LABELS: Record<string, string> = {
  walk_in: "Walk-in",
  phone_call: "Phone call",
  whatsapp: "WhatsApp",
  other: "Other",
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

// ── Log Modal Component ────────────────────────────────────────────────────────

function LogCaseworkModal({
  wardId,
  councillorId,
  councillorName,
  onClose,
  onSuccess,
}: {
  wardId: number;
  councillorId: string;
  councillorName: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [tab, setTab] = useState<"voice" | "text">("voice");
  const [recording, setRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [audioChunks, setAudioChunks] = useState<Blob[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const [recTimer, setRecTimer] = useState<NodeJS.Timeout | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [transcriptBanner, setTranscriptBanner] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  // Form fields
  const [form, setForm] = useState({
    name: "",
    phone: "",
    address: "",
    language: "both",
    description: "",
    category: "general",
    urgency: "medium",
    location: "",
    how_received: "other",
    notes: "",
    audioPath: "",
    transcript: "",
  });
  const [constituentHistory, setConstituentHistory] = useState<null | { total: number; casework: any[] }>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  // ── Voice recording ──────────────────────────────────────────────────────────

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      mr.ondataavailable = (e) => chunks.push(e.data);
      mr.onstop = async () => {
        const blob = new Blob(chunks, { type: "audio/webm" });
        stream.getTracks().forEach((t) => t.stop());
        setTranscribing(true);
        try {
          const fd = new FormData();
          fd.append("audio_file", blob, "recording.webm");
          fd.append("ward_id", String(wardId));
          const res = await api.post("/api/casework/transcribe", fd);
          const data = res.data;
          const e = data.extracted || {};
          setForm((f) => ({
            ...f,
            name: e.constituent_name || f.name,
            phone: e.constituent_phone || f.phone,
            address: e.constituent_address || f.address,
            description: e.issue_description || f.description,
            location: e.location_description || f.location,
            category: e.category || f.category,
            urgency: e.urgency || f.urgency,
            how_received: e.how_received || f.how_received,
            audioPath: data.audio_path || "",
            transcript: data.transcript || "",
          }));
          setTranscriptBanner(true);
          setTab("text");
        } catch {
          setToast({ type: "error", msg: "Transcription failed. Fill in the form manually." });
          setTab("text");
        } finally {
          setTranscribing(false);
        }
      };
      mr.start();
      setMediaRecorder(mr);
      setAudioChunks(chunks);
      setRecording(true);
      setElapsed(0);
      const t = setInterval(() => setElapsed((e) => e + 1), 1000);
      setRecTimer(t);
    } catch {
      setToast({ type: "error", msg: "Could not access microphone." });
    }
  };

  const stopRecording = () => {
    if (mediaRecorder) mediaRecorder.stop();
    if (recTimer) clearInterval(recTimer);
    setRecording(false);
  };

  const formatTime = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  // ── Phone blur → check history ───────────────────────────────────────────────

  const checkConstituentHistory = async () => {
    if (!form.phone || form.phone.length < 8) return;
    setHistoryLoading(true);
    try {
      const res = await caseworkApi.getConstituentHistory(form.phone, wardId);
      const data = res.data;
      if (data.total_entries > 0) setConstituentHistory(data);
    } catch {
      // ignore
    } finally {
      setHistoryLoading(false);
    }
  };

  // ── Save casework ─────────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!form.name || !form.phone || !form.description) {
      setToast({ type: "error", msg: "Name, phone, and description are required." });
      return;
    }
    setSaving(true);
    try {
      const res = await caseworkApi.log({
          ward_id: wardId,
          councillor_id: councillorId,
          councillor_name: councillorName,
          constituent_name: form.name,
          constituent_phone: form.phone,
          constituent_address: form.address,
          preferred_language: form.language,
          complaint_description: form.description,
          complaint_category: form.category,
          location_description: form.location,
          urgency: form.urgency,
          how_received: form.how_received,
          audio_path: form.audioPath,
          transcript: form.transcript,
          notes: form.notes,
      });
      const data = res.data;
      if (data.escalation_flag) {
        setToast({ type: "error", msg: `ESCALATION DETECTED: ${data.escalation_reason}` });
        setTimeout(() => { onSuccess(); onClose(); }, 3000);
      } else {
        onSuccess();
        onClose();
      }
    } catch {
      setToast({ type: "error", msg: "Failed to save casework." });
    } finally {
      setSaving(false);
    }
  };

  const PILLS_HOW = ["walk_in", "phone_call", "whatsapp", "other"];
  const PILLS_URGENCY = ["low", "medium", "high"];
  const PILLS_LANG = ["english", "tamil", "both"];
  const CATEGORIES = ["roads", "water", "lighting", "drainage", "waste", "scheme_enquiry", "general", "other"];

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/40" onClick={onClose} />

      {/* Drawer */}
      <div className="w-full max-w-[480px] bg-white h-full flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-emerald-700 to-teal-800 text-white px-5 py-4 flex items-center justify-between shrink-0">
          <div>
            <h2 className="font-bold text-base">Log new case</h2>
            <p className="text-emerald-200 text-xs mt-0.5">Record a constituent complaint</p>
          </div>
          <button onClick={onClose} className="text-white/70 hover:text-white transition-colors text-xl leading-none">✕</button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-100 shrink-0">
          {(["voice", "text"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2.5 text-sm font-semibold transition-colors ${tab === t ? "border-b-2 border-emerald-600 text-emerald-700" : "text-gray-500 hover:text-gray-700"}`}
            >
              {t === "voice" ? "🎤 Voice note" : "✏️ Type manually"}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {/* Voice tab */}
          {tab === "voice" && !transcribing && (
            <div className="flex flex-col items-center justify-center pt-10 pb-4 px-6">
              {!recording ? (
                <button
                  onClick={startRecording}
                  className="w-24 h-24 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white flex items-center justify-center shadow-lg transition-transform hover:scale-105 active:scale-95"
                >
                  <span className="text-3xl">🎤</span>
                </button>
              ) : (
                <button
                  onClick={stopRecording}
                  className="w-24 h-24 rounded-full bg-red-500 hover:bg-red-400 text-white flex items-center justify-center shadow-lg animate-pulse"
                >
                  <span className="text-3xl">⏹</span>
                </button>
              )}
              <p className="mt-4 text-sm font-medium text-gray-600">
                {recording ? `Recording… ${formatTime(elapsed)}` : "Tap to record voice note"}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {recording ? "Tap the button to stop recording" : "AI will extract complaint details automatically"}
              </p>
            </div>
          )}

          {transcribing && (
            <div className="flex flex-col items-center justify-center pt-20 pb-4">
              <div className="w-10 h-10 border-4 border-emerald-200 border-t-emerald-600 rounded-full animate-spin mb-4" />
              <p className="text-sm font-medium text-gray-600">Transcribing your note…</p>
            </div>
          )}

          {/* Form fields (always visible on text tab, also shown after voice) */}
          {(tab === "text" || transcriptBanner) && (
            <div className="px-5 py-4 space-y-4">
              {transcriptBanner && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800 flex items-start gap-2">
                  <span>⚡</span>
                  <span>Auto-filled from your voice note — please review before saving</span>
                </div>
              )}

              {/* Constituent Section */}
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">Constituent details</p>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Full name *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => set("name", e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                  placeholder="e.g. Murugan Rajan"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Phone number *</label>
                <input
                  type="tel"
                  value={form.phone}
                  onChange={(e) => set("phone", e.target.value)}
                  onBlur={checkConstituentHistory}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                  placeholder="e.g. 9876543210"
                />
                {historyLoading && <p className="text-xs text-gray-400 mt-1">Checking history…</p>}
                {constituentHistory && (
                  <div className="mt-2 bg-amber-50 border border-amber-200 rounded-lg p-2.5 text-xs text-amber-800">
                    <p className="font-semibold">Returning constituent — {constituentHistory.total_entries} previous cases</p>
                    {constituentHistory.casework.slice(0, 2).map((c: any) => (
                      <div key={c.casework_id} className="mt-1 text-amber-600 flex items-center gap-2">
                        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${CATEGORY_COLORS[c.complaint_category] || "bg-gray-100 text-gray-600"}`}>{c.complaint_category}</span>
                        <span>{c.status}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">How was this received?</label>
                <div className="flex flex-wrap gap-2">
                  {PILLS_HOW.map((m) => (
                    <button
                      key={m}
                      onClick={() => set("how_received", m)}
                      className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${form.how_received === m ? "bg-emerald-600 border-emerald-600 text-white" : "border-gray-200 text-gray-600 hover:border-emerald-400"}`}
                    >
                      {RECEIVED_LABELS[m]}
                    </button>
                  ))}
                </div>
              </div>

              {/* Complaint Section */}
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wider pt-2">Complaint details</p>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Describe the complaint *</label>
                <textarea
                  rows={4}
                  value={form.description}
                  onChange={(e) => set("description", e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 resize-none"
                  placeholder="Describe what the constituent told you…"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Category</label>
                <select
                  value={form.category}
                  onChange={(e) => set("category", e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1).replace("_", " ")}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Urgency</label>
                <div className="flex gap-2">
                  {PILLS_URGENCY.map((u) => (
                    <button
                      key={u}
                      onClick={() => set("urgency", u)}
                      className={`px-4 py-1.5 rounded-full text-xs font-semibold border transition-colors ${form.urgency === u ? (u === "high" ? "bg-red-500 border-red-500 text-white" : u === "medium" ? "bg-amber-500 border-amber-500 text-white" : "bg-green-500 border-green-500 text-white") : "border-gray-200 text-gray-600"}`}
                    >
                      {u.charAt(0).toUpperCase() + u.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Location mentioned</label>
                <input
                  type="text"
                  value={form.location}
                  onChange={(e) => set("location", e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                  placeholder="e.g. near SBI Bank on MG Road"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Follow-up language</label>
                <div className="flex gap-2">
                  {PILLS_LANG.map((lang) => (
                    <button
                      key={lang}
                      onClick={() => set("language", lang)}
                      className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${form.language === lang ? "bg-emerald-600 border-emerald-600 text-white" : "border-gray-200 text-gray-600"}`}
                    >
                      {lang.charAt(0).toUpperCase() + lang.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Internal notes</label>
                <textarea
                  rows={2}
                  value={form.notes}
                  onChange={(e) => set("notes", e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 resize-none"
                  placeholder="Any internal notes (not shared with constituent)"
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {(tab === "text" || transcriptBanner) && (
          <div className="border-t border-gray-100 px-5 py-4 flex items-center justify-between gap-3 shrink-0 bg-white">
            <button onClick={onClose} className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 transition-colors">
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex-1 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {saving ? <><span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />Saving…</> : "Save case"}
            </button>
          </div>
        )}

        {/* Toast */}
        {toast && (
          <div className={`absolute bottom-24 left-4 right-4 px-4 py-3 rounded-xl text-sm font-medium text-white shadow-lg ${toast.type === "error" ? "bg-red-600" : "bg-emerald-600"}`}>
            {toast.msg}
            <button onClick={() => setToast(null)} className="ml-2 opacity-70 hover:opacity-100">✕</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Casework Card ─────────────────────────────────────────────────────────────

function CaseworkCard({ cw, onClick }: { cw: CaseworkEntry; onClick: () => void }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm flex overflow-hidden hover:shadow-md transition-shadow cursor-pointer" onClick={onClick}>
      {/* Left accent bar */}
      <div className={`w-1.5 shrink-0 ${STATUS_COLORS[cw.status] ?? "bg-gray-200"}`} />

      <div className="flex-1 px-4 py-3 min-w-0">
        {/* Row 1 */}
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-semibold text-sm text-gray-800 truncate">{cw.constituent_name}</span>
            <span className="text-xs text-gray-400 shrink-0">{cw.constituent_phone_masked}</span>
          </div>
          <span className="text-xs text-gray-400 shrink-0 ml-2">{timeAgo(cw.created_at)}</span>
        </div>

        {/* Row 2 */}
        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${CATEGORY_COLORS[cw.complaint_category] ?? "bg-gray-100 text-gray-600"}`}>
            {cw.complaint_category}
          </span>
          <span className="text-[10px] text-gray-400">{RECEIVED_LABELS[cw.how_received] ?? cw.how_received}</span>
          {cw.escalation_flag && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700">🚨 Escalation</span>
          )}
        </div>

        {/* Row 3 — description */}
        <p className="text-xs text-gray-600 truncate">{cw.complaint_description.slice(0, 100)}</p>

        {/* Row 4 — status + badges */}
        <div className="flex items-center justify-between mt-2">
          <span className="text-[10px] text-gray-400">{STATUS_LABELS[cw.status] ?? cw.status}</span>
          <div className="flex items-center gap-1.5">
            {cw.linked_ticket_id ? (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">Ticket linked</span>
            ) : cw.status === "logged" ? (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">No ticket yet</span>
            ) : null}
            <span className="text-[10px] font-semibold text-emerald-700 hover:underline">View & act →</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function CaseworkInbox() {
  const { user, isCouncillor, isAdmin, isSupervisor } = useAuth();
  const router = useRouter();

  const [casework, setCasework] = useState<CaseworkEntry[]>([]);
  const [counts, setCounts] = useState({ total: 0, escalated: 0, needs_action: 0 });
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "needs_action" | "escalated" | "resolved">("all");
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);

  const wardId = user?.ward_id ?? 1;

  const fetchCasework = useCallback(async () => {
    setLoading(true);
    try {
      const [cwRes, countRes] = await Promise.allSettled([
        caseworkApi.list(wardId, { status: filter === "resolved" ? "resolved" : undefined, escalated_only: filter === "escalated" ? true : undefined, search: search || undefined }),
        caseworkApi.getCounts(wardId),
      ]);
      if (cwRes.status === "fulfilled") { setCasework(cwRes.value.data.casework ?? []); }
      if (countRes.status === "fulfilled") { setCounts(countRes.value.data); }
    } finally {
      setLoading(false);
    }
  }, [wardId, filter, search]);

  useEffect(() => {
    if (!user) return;
    if (!isCouncillor && !isAdmin && !isSupervisor) { router.push("/officer/dashboard"); return; }
    fetchCasework();
  }, [user, filter]);

  const filtered = casework.filter((cw) => {
    if (filter === "needs_action") {
      return ["logged", "ticket_created"].includes(cw.status);
    }
    return true;
  });

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top bar */}
      <div className="bg-gradient-to-r from-emerald-700 to-teal-800 text-white px-6 py-5">
        <div className="max-w-4xl mx-auto flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <a href="/councillor" className="text-emerald-300 hover:text-white text-sm transition-colors">← Dashboard</a>
            </div>
            <h1 className="text-2xl font-bold">Constituent casework</h1>
            <p className="text-emerald-200 text-xs mt-1">
              {counts.total} entries · {counts.escalated > 0 && <span className="text-red-300 font-semibold">{counts.escalated} escalations · </span>}{counts.needs_action} need action
            </p>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="bg-white text-emerald-700 font-bold text-sm px-4 py-2.5 rounded-xl hover:bg-emerald-50 transition-colors shadow-sm shrink-0 mt-1"
          >
            + Log new case
          </button>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-6">
        {/* Filter Row */}
        <div className="flex items-center gap-3 mb-5 flex-wrap">
          {[
            { key: "all", label: "All" },
            { key: "needs_action", label: `Needs action${counts.needs_action > 0 ? ` (${counts.needs_action})` : ""}` },
            { key: "escalated", label: `Escalated${counts.escalated > 0 ? ` (${counts.escalated})` : ""}` },
            { key: "resolved", label: "Resolved" },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setFilter(key as any)}
              className={`px-4 py-1.5 rounded-full text-sm font-semibold border transition-colors ${filter === key ? (key === "escalated" ? "bg-red-600 border-red-600 text-white" : "bg-emerald-600 border-emerald-600 text-white") : "border-gray-200 text-gray-600 bg-white hover:border-emerald-400"}`}
            >
              {label}
            </button>
          ))}
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchCasework()}
            placeholder="Search by name or issue…"
            className="ml-auto px-3 py-1.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 bg-white"
          />
        </div>

        {/* List */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="w-10 h-10 border-4 border-emerald-200 border-t-emerald-600 rounded-full animate-spin mb-4" />
            <p className="text-gray-400 text-sm">Loading casework…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none" className="mb-4 opacity-30">
              <rect x="8" y="4" width="48" height="56" rx="4" stroke="#6b7280" strokeWidth="2" />
              <rect x="16" y="16" width="32" height="3" rx="1.5" fill="#6b7280" />
              <rect x="16" y="24" width="24" height="3" rx="1.5" fill="#6b7280" />
              <rect x="16" y="32" width="28" height="3" rx="1.5" fill="#6b7280" />
              <circle cx="50" cy="50" r="10" fill="#6b7280" />
              <rect x="44" y="49" width="12" height="2" rx="1" fill="white" />
              <rect x="49" y="44" width="2" height="12" rx="1" fill="white" />
            </svg>
            <h2 className="font-bold text-gray-600 text-base">No casework logged yet</h2>
            <p className="text-gray-400 text-sm mt-1 max-w-sm">
              Use &ldquo;Log new case&rdquo; to record constituent complaints you receive directly — by phone, walk-in, or WhatsApp.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((cw) => (
              <CaseworkCard key={cw.casework_id} cw={cw} onClick={() => router.push(`/councillor/casework/${cw.casework_id}`)} />
            ))}
          </div>
        )}
      </div>

      {/* Modal */}
      {modalOpen && (
        <LogCaseworkModal
          wardId={wardId}
          councillorId={String(user?.id ?? "demo")}
          councillorName={user?.full_name ?? "Councillor"}
          onClose={() => setModalOpen(false)}
          onSuccess={fetchCasework}
        />
      )}
    </div>
  );
}
