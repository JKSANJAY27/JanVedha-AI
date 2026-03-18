"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import toast from "react-hot-toast";

// ─── Types ─────────────────────────────────────────────────────────────────

interface TopicType {
  id: string;
  label: string;
  description: string;
  icon: string;
}

interface TicketResult {
  id: string;
  title: string;
  status: string;
  created_at: string;
}

interface CommOutputs {
  formal_notice: { english: string; tamil: string };
  whatsapp_post: { english: string; tamil: string };
  sms: { english: string; tamil: string };
}

interface CommHistory {
  comm_id: string;
  topic_type: string;
  topic_label: string;
  linked_ticket_id: string | null;
  created_at: string;
}

// ─── Constants ──────────────────────────────────────────────────────────────

const TOPIC_TYPES: TopicType[] = [
  { id: "work_completed", label: "Work completed", description: "Road fixed, light installed, complaint resolved", icon: "✅" },
  { id: "upcoming_disruption", label: "Upcoming disruption", description: "Water cut, road closure, power outage", icon: "⚠️" },
  { id: "scheme_announcement", label: "Scheme announcement", description: "New program, enrollment, benefits", icon: "📋" },
  { id: "ward_event", label: "Ward event", description: "Public meeting, consultation, celebration", icon: "📅" },
  { id: "general_update", label: "General update", description: "Any other ward communication", icon: "📢" },
];

const LOADING_MESSAGES = [
  "Preparing your content...",
  "Drafting formal notice...",
  "Writing WhatsApp and SMS versions...",
  "Translating to Tamil...",
];

const FORMAT_TABS = [
  { id: "formal_notice", label: "Formal notice", icon: "📄" },
  { id: "whatsapp_post", label: "WhatsApp post", icon: "💬" },
  { id: "sms", label: "SMS", icon: "📱" },
];

function relativeDate(isoStr: string): string {
  const diff = Date.now() - new Date(isoStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days} days ago`;
  return new Date(isoStr).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function charCount(text: string): number {
  return [...text].length; // handles multi-byte Tamil chars properly
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function CommunicationsPage() {
  const { user, isCouncillor, isAdmin, isSupervisor } = useAuth();
  const router = useRouter();

  // Form state
  const [topicType, setTopicType] = useState<string>("work_completed");
  const [topicSummary, setTopicSummary] = useState("");
  const [specificDetails, setSpecificDetails] = useState("");
  const [ticketSearch, setTicketSearch] = useState("");
  const [ticketResults, setTicketResults] = useState<TicketResult[]>([]);
  const [linkedTicket, setLinkedTicket] = useState<TicketResult | null>(null);
  const [showTicketDropdown, setShowTicketDropdown] = useState(false);

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [loadingMsgIdx, setLoadingMsgIdx] = useState(0);
  const [outputs, setOutputs] = useState<CommOutputs | null>(null);
  const [currentCommId, setCurrentCommId] = useState<string | null>(null);

  // Display state
  const [activeFormat, setActiveFormat] = useState<"formal_notice" | "whatsapp_post" | "sms">("formal_notice");
  const [activeLang, setActiveLang] = useState<"english" | "tamil" | "both">("english");
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // AI Suggestions
  const [suggestions, setSuggestions] = useState<{ title: string; topic_type: string; summary: string; additional_details?: string; linked_ticket_id: string | null; linked_ticket_code?: string | null }[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  // History
  const [history, setHistory] = useState<CommHistory[]>([]);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  const ticketDebounceRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!user) return;
    const allowed = isCouncillor || isAdmin || isSupervisor;
    if (!allowed) { router.push("/councillor"); }
  }, [user, isCouncillor, isAdmin, isSupervisor, router]);

  // ── Load Suggestions ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!user?.ward_id) return;
    const fetchSuggestions = async () => {
      setLoadingSuggestions(true);
      try {
        const res = await api.get("/api/communications/suggestions", { params: { ward_id: String(user.ward_id) } });
        setSuggestions(res.data.suggestions || []);
      } catch (e) {
        console.error("Failed to load suggestions", e);
      } finally {
        setLoadingSuggestions(false);
      }
    };
    fetchSuggestions();
  }, [user?.ward_id]);

  // ── Ticket search (debounced) ───────────────────────────────────────────────
  const searchTickets = useCallback(async (q: string) => {
    if (!q.trim() || q.length < 2) { setTicketResults([]); return; }
    try {
      const res = await api.get("/api/officer/tickets", {
        params: { ward_id: user?.ward_id, search: q, status: "RESOLVED", limit: 8 },
      });
      const tickets = res.data?.tickets || res.data || [];
      setTicketResults(
        tickets.slice(0, 8).map((t: any) => ({
          id: String(t.id || t._id),
          title: t.description?.slice(0, 80) || t.ticket_code || "Unnamed ticket",
          status: t.status || "RESOLVED",
          created_at: t.created_at || "",
        }))
      );
    } catch {
      setTicketResults([]);
    }
  }, [user?.ward_id]);

  useEffect(() => {
    if (ticketDebounceRef.current) clearTimeout(ticketDebounceRef.current);
    ticketDebounceRef.current = setTimeout(() => searchTickets(ticketSearch), 400);
    return () => { if (ticketDebounceRef.current) clearTimeout(ticketDebounceRef.current); };
  }, [ticketSearch, searchTickets]);

  // ── Load history ────────────────────────────────────────────────────────────
  const loadHistory = useCallback(async () => {
    if (!user?.ward_id) return;
    try {
      const res = await api.get("/api/communications", { params: { ward_id: String(user.ward_id), limit: 10 } });
      setHistory(res.data?.communications || []);
      setHistoryLoaded(true);
    } catch {
      setHistory([]);
    }
  }, [user?.ward_id]);

  // ── Generate ─────────────────────────────────────────────────────────────────
  const handleGenerate = async () => {
    if (!topicSummary.trim()) { toast.error("Please describe what you want to announce"); return; }
    if (!user) return;

    setGenerating(true);
    setOutputs(null);
    setLoadingMsgIdx(0);

    // Rotate loading messages
    const interval = setInterval(() => {
      setLoadingMsgIdx(i => (i + 1) % LOADING_MESSAGES.length);
    }, 2000);

    try {
      const res = await api.post("/api/communications/generate", {
        ward_id: String(user.ward_id),
        councillor_id: String(user.id),
        councillor_name: user.name || "Councillor",
        ward_name: `Ward ${user.ward_id}`,
        topic_type: topicType,
        topic_summary: topicSummary,
        specific_details: specificDetails || undefined,
        linked_ticket_id: linkedTicket?.id || null,
      });
      setOutputs(res.data.outputs);
      setCurrentCommId(res.data.comm_id);
      toast.success("Drafts generated successfully!");
      // Reload history
      loadHistory();
    } catch (e: any) {
      const msg = e?.response?.data?.detail?.message || "Generation failed. Please try again.";
      toast.error(msg);
    } finally {
      clearInterval(interval);
      setGenerating(false);
    }
  };

  // ── Load a past communication ─────────────────────────────────────────────
  const loadPastComm = async (commId: string) => {
    try {
      const res = await api.get(`/api/communications/${commId}`);
      setOutputs(res.data.outputs);
      setCurrentCommId(commId);
      setActiveFormat("formal_notice");
      setActiveLang("english");
      toast.success("Past communication loaded");
    } catch {
      toast.error("Could not load communication");
    }
  };

  // ── Copy to clipboard ─────────────────────────────────────────────────────
  const copyText = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // ── Download PDF ───────────────────────────────────────────────────────────
  const downloadPdf = async (lang: "english" | "tamil") => {
    if (!currentCommId) return;
    try {
      const res = await api.post(`/api/communications/${currentCommId}/pdf`, null, {
        params: { language: lang },
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `PublicNotice_${lang}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("PDF download failed");
    }
  };

  // ── Render content for a format+language ─────────────────────────────────
  const getContent = (format: keyof CommOutputs, lang: "english" | "tamil"): string => {
    return outputs?.[format]?.[lang] || "";
  };

  const TOPIC_TYPE_LABELS: Record<string, string> = {
    work_completed: "Work Completed",
    upcoming_disruption: "Disruption",
    scheme_announcement: "Scheme",
    ward_event: "Event",
    general_update: "Update",
  };

  if (!user) return null;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-teal-700 to-emerald-800 text-white px-6 py-5">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <a href="/councillor" className="text-teal-300 hover:text-white text-sm">← Dashboard</a>
            <span className="text-teal-400">·</span>
            <span className="text-teal-200 text-sm">Communication</span>
          </div>
          <h1 className="text-2xl font-bold mt-2">Constituent Communications 📣</h1>
          <p className="text-teal-200 text-sm mt-0.5">Draft ward announcements in English and Tamil — one action, multiple formats</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

          {/* ── LEFT: Input Form ─────────────────────────────────────────── */}
          <div className="space-y-6">

            {/* AI Suggestions */}
            <div className="bg-gradient-to-br from-indigo-50 to-purple-50 p-5 rounded-2xl border border-indigo-100 mb-2">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xl">💡</span>
                <h3 className="font-bold text-indigo-900">AI Ideas from Recent Tickets</h3>
              </div>
              
              {loadingSuggestions ? (
                <div className="flex items-center gap-2 text-indigo-600 text-sm py-2">
                  <span className="w-4 h-4 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
                  Analyzing ward data...
                </div>
              ) : suggestions.length > 0 ? (
                <div className="grid grid-cols-1 gap-3">
                  {suggestions.map((s, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        setTopicType(s.topic_type);
                        setTopicSummary(s.summary);
                        setSpecificDetails(s.additional_details || "");
                        if (s.linked_ticket_id && s.linked_ticket_id !== "null") {
                          setLinkedTicket({
                            id: s.linked_ticket_id,
                            title: s.linked_ticket_code ? `Ticket #${s.linked_ticket_code}` : `Ticket #${s.linked_ticket_id.slice(-6).toUpperCase()}`,
                            status: "RESOLVED",
                            created_at: new Date().toISOString()
                          });
                        } else {
                          setLinkedTicket(null);
                        }
                        toast.success("Applied suggestion!");
                      }}
                      className="text-left bg-white p-3 rounded-xl border border-indigo-100 hover:border-indigo-300 hover:shadow-sm transition-all flex flex-col gap-1"
                    >
                      <div className="flex justify-between items-start gap-2">
                        <span className="font-semibold text-indigo-800 text-sm leading-tight">{s.title}</span>
                        {s.linked_ticket_id && s.linked_ticket_id !== "null" && (
                          <span className="text-[10px] font-bold text-indigo-500 bg-indigo-50 px-2 py-0.5 rounded flex-shrink-0">
                            🎫 {s.linked_ticket_code || "TICKET"}
                          </span>
                        )}
                      </div>
                      <span className="text-gray-600 text-xs line-clamp-2">{s.summary}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-indigo-400 italic">No recent ticket trends found.</p>
              )}
            </div>

            {/* Topic type picker */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-3">What are you communicating about?</label>
              <div className="grid grid-cols-2 gap-3">
                {TOPIC_TYPES.map(t => (
                  <button
                    key={t.id}
                    onClick={() => setTopicType(t.id)}
                    className={`text-left p-4 rounded-xl border-2 transition-all ${
                      topicType === t.id
                        ? "border-teal-500 bg-teal-50 shadow-sm"
                        : "border-gray-200 bg-white hover:border-teal-200 hover:bg-teal-50/50"
                    }`}
                  >
                    <div className="text-xl mb-1">{t.icon}</div>
                    <div className="text-sm font-semibold text-gray-800">{t.label}</div>
                    <div className="text-xs text-gray-500 mt-0.5 leading-tight">{t.description}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Topic description */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">Describe what you want to announce *</label>
              <textarea
                rows={4}
                value={topicSummary}
                onChange={e => setTopicSummary(e.target.value)}
                placeholder="e.g. The pothole near Gandhi School has been repaired. Work was completed yesterday by the roads department."
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-teal-400 text-sm resize-none bg-white"
              />
            </div>

            {/* Additional details */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">Any additional details? <span className="font-normal text-gray-400">(optional)</span></label>
              <textarea
                rows={2}
                value={specificDetails}
                onChange={e => setSpecificDetails(e.target.value)}
                placeholder="Dates, times, contact numbers, office locations, deadlines, or anything else to include..."
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-teal-400 text-sm resize-none bg-white"
              />
            </div>

            {/* Ticket link */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">Link to a resolved ticket <span className="font-normal text-gray-400">(optional)</span></label>
              {linkedTicket ? (
                <div className="flex items-start justify-between bg-blue-50 border border-blue-200 rounded-xl px-4 py-3">
                  <div>
                    <p className="text-sm font-semibold text-blue-800 leading-tight">{linkedTicket.title}</p>
                    <p className="text-xs text-blue-600 mt-0.5">Reported {relativeDate(linkedTicket.created_at)} · {linkedTicket.status}</p>
                    <p className="text-xs text-blue-500 mt-1 italic">Real dates from this ticket will be used in your drafts</p>
                  </div>
                  <button onClick={() => { setLinkedTicket(null); setTicketSearch(""); }} className="text-blue-400 hover:text-blue-600 ml-2 mt-0.5 text-lg font-bold leading-none">×</button>
                </div>
              ) : (
                <div className="relative">
                  <input
                    type="text"
                    value={ticketSearch}
                    onChange={e => { setTicketSearch(e.target.value); setShowTicketDropdown(true); }}
                    onFocus={() => setShowTicketDropdown(true)}
                    placeholder="Search tickets by description..."
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-teal-400 text-sm bg-white"
                  />
                  {showTicketDropdown && ticketResults.length > 0 && (
                    <div className="absolute z-20 left-0 right-0 bg-white border border-gray-200 rounded-xl shadow-lg mt-1 max-h-48 overflow-y-auto">
                      {ticketResults.map(t => (
                        <button
                          key={t.id}
                          onClick={() => { setLinkedTicket(t); setTicketSearch(""); setShowTicketDropdown(false); setTicketResults([]); }}
                          className="w-full text-left px-4 py-2.5 hover:bg-teal-50 border-b border-gray-50 last:border-0"
                        >
                          <p className="text-sm text-gray-800 font-medium truncate">{t.title}</p>
                          <p className="text-xs text-gray-400 mt-0.5">{t.status} · {relativeDate(t.created_at)}</p>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Generate button */}
            <button
              onClick={handleGenerate}
              disabled={generating || !topicSummary.trim()}
              className="w-full py-4 rounded-xl font-bold text-white text-base transition-all bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 disabled:opacity-60 disabled:cursor-not-allowed shadow-sm"
            >
              {generating ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  {LOADING_MESSAGES[loadingMsgIdx]}
                </span>
              ) : "Generate drafts ✨"}
            </button>
          </div>

          {/* ── RIGHT: Output Panel ──────────────────────────────────────── */}
          <div>
            {!outputs ? (
              /* Empty state */
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-10 flex flex-col items-center justify-center text-center h-full min-h-80">
                {generating ? (
                  <>
                    <div className="w-12 h-12 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin mb-4" />
                    <p className="text-gray-700 font-semibold">{LOADING_MESSAGES[loadingMsgIdx]}</p>
                    <p className="text-gray-400 text-sm mt-1">Generating six format variants in English and Tamil…</p>
                  </>
                ) : (
                  <>
                    <svg className="w-16 h-16 text-teal-200 mb-4" viewBox="0 0 64 64" fill="none">
                      <rect x="8" y="18" width="48" height="32" rx="4" fill="currentColor" opacity="0.4"/>
                      <rect x="20" y="10" width="24" height="14" rx="3" fill="currentColor" opacity="0.6"/>
                      <rect x="26" y="4" width="12" height="8" rx="2" fill="currentColor" opacity="0.8"/>
                      <rect x="16" y="28" width="32" height="3" rx="1.5" fill="white" opacity="0.6"/>
                      <rect x="16" y="35" width="24" height="3" rx="1.5" fill="white" opacity="0.4"/>
                      <rect x="16" y="42" width="18" height="3" rx="1.5" fill="white" opacity="0.3"/>
                    </svg>
                    <p className="text-gray-700 font-semibold text-base">Your drafted communications will appear here</p>
                    <p className="text-gray-400 text-sm mt-1">Fill in the form and click Generate drafts</p>
                  </>
                )}
              </div>
            ) : (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
                {/* Format tabs */}
                <div className="flex border-b border-gray-100">
                  {FORMAT_TABS.map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => { setActiveFormat(tab.id as any); setActiveLang("english"); }}
                      className={`flex-1 py-3 text-sm font-semibold transition-colors flex items-center justify-center gap-1.5 ${
                        activeFormat === tab.id
                          ? "text-teal-700 border-b-2 border-teal-600 bg-teal-50/50"
                          : "text-gray-500 hover:text-gray-700"
                      }`}
                    >
                      <span>{tab.icon}</span> {tab.label}
                    </button>
                  ))}
                </div>

                {/* Language toggle */}
                <div className="flex gap-2 p-4 border-b border-gray-50">
                  {(["english", "tamil", "both"] as const).map(lang => (
                    <button
                      key={lang}
                      onClick={() => setActiveLang(lang)}
                      className={`px-4 py-1.5 rounded-full text-xs font-semibold capitalize transition-all ${
                        activeLang === lang
                          ? "bg-teal-600 text-white shadow-sm"
                          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >
                      {lang === "both" ? "Show both" : lang.charAt(0).toUpperCase() + lang.slice(1)}
                    </button>
                  ))}
                </div>

                {/* Content */}
                <div className="p-4 space-y-4">
                  {(activeLang === "both" ? ["english", "tamil"] : [activeLang]).map(lang => {
                    const text = getContent(activeFormat as keyof CommOutputs, lang as any);
                    const copyKey = `${activeFormat}-${lang}`;
                    const chars = charCount(text);
                    return (
                      <div key={lang} className="border border-gray-100 rounded-xl overflow-hidden">
                        <div className="px-4 py-2 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
                          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                            {lang === "english" ? "English" : "Tamil"}
                          </span>
                          {activeFormat === "sms" && (
                            <span className={`text-xs font-bold ${chars > 160 ? "text-red-600" : "text-emerald-600"}`}>
                              {chars} / 160 chars
                            </span>
                          )}
                        </div>
                        <div className={`px-4 py-4 ${activeFormat === "formal_notice" ? "font-serif" : ""}`}>
                          <p
                            className={`text-sm leading-[1.75] whitespace-pre-wrap text-gray-800 ${
                              lang === "tamil" ? "font-[system-ui]" : ""
                            }`}
                          >
                            {text || <span className="text-gray-300 italic">No content generated</span>}
                          </p>
                        </div>
                        <div className="px-4 pb-3 flex gap-2 flex-wrap">
                          <button
                            onClick={() => copyText(text, copyKey)}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-all"
                          >
                            {copiedKey === copyKey ? "✅ Copied!" : "📋 Copy"}
                          </button>
                          {activeFormat === "formal_notice" && (
                            <button
                              onClick={() => downloadPdf(lang as "english" | "tamil")}
                              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-teal-100 text-teal-700 hover:bg-teal-200 transition-all"
                            >
                              ↓ Download PDF
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* History panel */}
            <div className="mt-6 bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <button
                onClick={() => {
                  setHistoryExpanded(e => !e);
                  if (!historyLoaded) loadHistory();
                }}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-base">🗂️</span>
                  <span className="text-sm font-semibold text-gray-700">Past communications</span>
                </div>
                <span className="text-gray-400 text-sm">{historyExpanded ? "▲" : "▼"}</span>
              </button>

              {historyExpanded && (
                <div className="border-t border-gray-100">
                  {history.length === 0 ? (
                    <p className="text-sm text-gray-400 text-center py-6 italic">No past communications yet</p>
                  ) : (
                    <div className="divide-y divide-gray-50">
                      {history.map(h => (
                        <div key={h.comm_id} className="flex items-center justify-between px-5 py-3 hover:bg-gray-50">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-800 truncate">{h.topic_label}</p>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-[11px] bg-teal-100 text-teal-700 font-semibold px-2 py-0.5 rounded-full">
                                {TOPIC_TYPE_LABELS[h.topic_type] || h.topic_type}
                              </span>
                              <span className="text-[11px] text-gray-400">{relativeDate(h.created_at)}</span>
                            </div>
                          </div>
                          <button
                            onClick={() => loadPastComm(h.comm_id)}
                            className="ml-3 text-xs font-semibold text-teal-600 hover:text-teal-800 shrink-0"
                          >
                            View →
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
