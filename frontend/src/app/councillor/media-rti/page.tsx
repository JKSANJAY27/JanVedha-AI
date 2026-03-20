"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import toast from "react-hot-toast";

// ─── Types ──────────────────────────────────────────────────────────────────

interface DataPoint {
  description: string;
  data: Record<string, any>;
}

interface AnalysisResult {
  query_intent: string;
  is_answerable: boolean;
  data_points: DataPoint[];
  outside_scope: string[];
  sensitivity_flag: boolean;
  sensitivity_note: string | null;
}

interface MediaOutput {
  quotable_statement: string;
  supporting_data_points: string[];
  full_response_letter: string;
  data_gaps_note: string | null;
}

interface RtiInfoItem {
  query_item: string;
  response: string;
  data_basis?: string;
}

interface RtiNotAvailableItem {
  query_item: string;
  reason: string;
}

interface RtiDocument {
  header: { office_name: string; application_number: string; date_of_receipt: string; date_of_response: string; response_deadline: string };
  applicant_reference: string;
  acknowledgment_paragraph: string;
  information_provided: RtiInfoItem[];
  information_not_held: RtiNotAvailableItem[];
  closing_paragraph: string;
  signature_block: { name: string; designation: string; ward: string; date: string };
}

interface RtiOutput {
  rti_response_document: RtiDocument;
  internal_note: string | null;
}

interface HistoryItem {
  response_id: string;
  type: "media" | "rti";
  query_text: string;
  query_source: string | null;
  created_at: string;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function relativeDate(isoStr: string): string {
  const diff = Date.now() - new Date(isoStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return `${days}d ago`;
}

function countDaysFromToday(isoStr: string): number {
  return Math.round((new Date(isoStr).getTime() - Date.now()) / 86400000);
}

function getDeadlineDisplay(dateStr: string): { text: string; urgent: boolean } | null {
  try {
    const days = countDaysFromToday(dateStr + "T00:00:00");
    const deadlineDate = new Date(dateStr);
    deadlineDate.setDate(deadlineDate.getDate() + 30);
    const deadlineStr = deadlineDate.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
    const daysLeft = Math.round((deadlineDate.getTime() - Date.now()) / 86400000);
    return { text: daysLeft <= 0 ? `Overdue — was due ${deadlineStr}` : `Due ${deadlineStr} (${daysLeft} days)`, urgent: daysLeft <= 7 };
  } catch { return null; }
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function MediaRtiPage() {
  const { user, isCouncillor, isAdmin, isSupervisor } = useAuth();
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [activeTab, setActiveTab] = useState<"media" | "rti">("media");

  // Media state
  const [mediaQuery, setMediaQuery] = useState("");
  const [mediaSource, setMediaSource] = useState("");
  const [mediaTone, setMediaTone] = useState<"data_forward" | "empathetic" | "firm">("data_forward");
  const [mediaAnalysis, setMediaAnalysis] = useState<AnalysisResult | null>(null);
  const [mediaOutput, setMediaOutput] = useState<MediaOutput | null>(null);
  const [mediaResponseId, setMediaResponseId] = useState<string | null>(null);
  const [mediaAnalyzing, setMediaAnalyzing] = useState(false);
  const [mediaGenerating, setMediaGenerating] = useState(false);

  // RTI state
  const [rtiQuery, setRtiQuery] = useState("");
  const [rtiAppNumber, setRtiAppNumber] = useState("");
  const [rtiDateReceived, setRtiDateReceived] = useState("");
  const [rtiApplicant, setRtiApplicant] = useState("");
  const [rtiAnalysis, setRtiAnalysis] = useState<AnalysisResult | null>(null);
  const [rtiOutput, setRtiOutput] = useState<RtiOutput | null>(null);
  const [rtiResponseId, setRtiResponseId] = useState<string | null>(null);
  const [rtiAnalyzing, setRtiAnalyzing] = useState(false);
  const [rtiGenerating, setRtiGenerating] = useState(false);
  const [imageExtracting, setImageExtracting] = useState(false);
  const [infoBannerDismissed, setInfoBannerDismissed] = useState(false);

  // History
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    if (!isCouncillor && !isAdmin && !isSupervisor) { router.push("/dashboard"); }
  }, [user, isCouncillor, isAdmin, isSupervisor, router]);

  const loadHistory = useCallback(async () => {
    if (!user?.ward_id) return;
    try {
      const res = await api.get("/api/media-rti", { params: { ward_id: String(user.ward_id), limit: 10 } });
      setHistory(res.data?.responses || []);
      setHistoryLoaded(true);
    } catch { setHistory([]); }
  }, [user?.ward_id]);

  const copyText = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // ── Media: analyze ──────────────────────────────────────────────────────
  const analyzeMediaQuery = async () => {
    if (!mediaQuery.trim()) { toast.error("Please enter a media query"); return; }
    setMediaAnalyzing(true);
    setMediaAnalysis(null); setMediaOutput(null);
    try {
      const res = await api.post("/api/media-rti/analyze-query", {
        ward_id: String(user?.ward_id), query_text: mediaQuery, type: "media",
      });
      setMediaAnalysis(res.data);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not analyze query. Try simplifying it.");
    } finally { setMediaAnalyzing(false); }
  };

  // ── Media: generate full response ──────────────────────────────────────
  const generateMediaResponse = async () => {
    if (!mediaQuery.trim()) { toast.error("Please enter a media query"); return; }
    setMediaGenerating(true);
    try {
      const res = await api.post("/api/media-rti/generate", {
        ward_id: String(user?.ward_id),
        councillor_id: String(user?.id),
        councillor_name: user?.name || "Councillor",
        ward_name: `Ward ${user?.ward_id}`,
        type: "media",
        query_text: mediaQuery,
        query_source: mediaSource || undefined,
        tone_preference: mediaTone,
        data_analysis: mediaAnalysis || undefined,
      });
      setMediaOutput(res.data.output);
      setMediaResponseId(res.data.response_id);
      if (!mediaAnalysis) setMediaAnalysis(null);
      loadHistory();
      toast.success("Response drafted!");
    } catch (e: any) {
      toast.error("Failed to generate response");
    } finally { setMediaGenerating(false); }
  };

  // ── RTI: analyze ───────────────────────────────────────────────────────
  const analyzeRtiQuery = async () => {
    if (!rtiQuery.trim()) { toast.error("Please enter the RTI application text"); return; }
    setRtiAnalyzing(true);
    setRtiAnalysis(null); setRtiOutput(null);
    try {
      const res = await api.post("/api/media-rti/analyze-query", {
        ward_id: String(user?.ward_id), query_text: rtiQuery, type: "rti",
      });
      setRtiAnalysis(res.data);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not analyze application.");
    } finally { setRtiAnalyzing(false); }
  };

  // ── RTI: generate full response ───────────────────────────────────────
  const generateRtiResponse = async () => {
    if (!rtiQuery.trim()) { toast.error("Please enter the RTI application text"); return; }
    setRtiGenerating(true);
    try {
      const res = await api.post("/api/media-rti/generate", {
        ward_id: String(user?.ward_id),
        councillor_id: String(user?.id),
        councillor_name: user?.name || "Councillor",
        ward_name: `Ward ${user?.ward_id}`,
        type: "rti",
        query_text: rtiQuery,
        query_source: rtiApplicant || undefined,
        date_received: rtiDateReceived || undefined,
        rti_application_number: rtiAppNumber || undefined,
        data_analysis: rtiAnalysis || undefined,
      });
      setRtiOutput(res.data.output);
      setRtiResponseId(res.data.response_id);
      loadHistory();
      toast.success("RTI response drafted!");
    } catch (e: any) {
      toast.error("Failed to generate RTI response");
    } finally { setRtiGenerating(false); }
  };

  // ── Image upload for RTI ──────────────────────────────────────────────
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { toast.error("File too large. Max 5 MB."); return; }
    setImageExtracting(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("/api/media-rti/extract-query-from-image", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setRtiQuery(res.data.extracted_text || "");
      toast.success("Text extracted from document!");
    } catch {
      toast.error("Could not read the document clearly. Please type the application text manually.");
    } finally {
      setImageExtracting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // ── Download RTI PDF ──────────────────────────────────────────────────
  const downloadRtiPdf = async () => {
    if (!rtiResponseId) return;
    try {
      const res = await api.post(`/api/media-rti/${rtiResponseId}/generate-pdf`, null, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = `RTI_Response_${rtiResponseId}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("PDF download failed"); }
  };

  // ── Load past response ────────────────────────────────────────────────
  const loadPastResponse = async (responseId: string, type: "media" | "rti") => {
    try {
      const res = await api.get(`/api/media-rti/${responseId}`);
      const d = res.data;
      if (type === "media") {
        setActiveTab("media");
        setMediaQuery(d.query_text || "");
        setMediaSource(d.query_source || "");
        setMediaTone(d.tone_preference || "data_forward");
        setMediaAnalysis(d.data_analysis);
        setMediaOutput(d.output);
        setMediaResponseId(d.response_id);
      } else {
        setActiveTab("rti");
        setRtiQuery(d.query_text || "");
        setRtiApplicant(d.query_source || "");
        setRtiAppNumber(d.rti_application_number || "");
        setRtiAnalysis(d.data_analysis);
        setRtiOutput(d.output);
        setRtiResponseId(d.response_id);
      }
      toast.success("Past response loaded");
    } catch { toast.error("Could not load response"); }
  };

  if (!user) return null;

  const deadlineInfo = rtiDateReceived ? getDeadlineDisplay(rtiDateReceived) : null;

  // ─── Analysis Panel ────────────────────────────────────────────────────
  const AnalysisPanel = ({ analysis }: { analysis: AnalysisResult }) => (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-sm font-bold text-gray-700">What we found in your ward data</span>
        <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${analysis.is_answerable ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
          {analysis.is_answerable ? "Answerable from ticket data" : "Partial data available"}
        </span>
      </div>
      {analysis.query_intent && (
        <p className="text-xs text-gray-500 italic bg-gray-50 rounded-lg px-3 py-2">{analysis.query_intent}</p>
      )}
      {analysis.sensitivity_flag && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3">
          <p className="text-xs font-bold text-amber-800">⚠️ Sensitive query detected</p>
          <p className="text-xs text-amber-700 mt-1">{analysis.sensitivity_note}</p>
          <p className="text-xs text-amber-600 mt-1 italic">Review the generated response carefully before sending.</p>
        </div>
      )}
      {analysis.data_points.map((dp, i) => (
        <div key={i} className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
          <p className="text-xs font-semibold text-gray-600 mb-2">{dp.description}</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {dp.data.total_count !== undefined && (
              <div className="text-center">
                <p className="text-lg font-bold text-indigo-700">{dp.data.total_count}</p>
                <p className="text-[10px] text-gray-400">Total</p>
              </div>
            )}
            {dp.data.resolved_count !== undefined && (
              <div className="text-center">
                <p className="text-lg font-bold text-emerald-700">{dp.data.resolved_count}</p>
                <p className="text-[10px] text-gray-400">Resolved ({dp.data.resolution_rate_pct}%)</p>
              </div>
            )}
            {dp.data.avg_resolution_days !== null && dp.data.avg_resolution_days !== undefined && (
              <div className="text-center">
                <p className="text-lg font-bold text-blue-700">{dp.data.avg_resolution_days}</p>
                <p className="text-[10px] text-gray-400">Avg days</p>
              </div>
            )}
          </div>
        </div>
      ))}
      {analysis.outside_scope && analysis.outside_scope.length > 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-3">
          <p className="text-xs font-semibold text-gray-600 mb-2">Data not available in this system:</p>
          <ul className="space-y-1">
            {analysis.outside_scope.map((s, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-gray-500">
                <span className="text-gray-400 mt-0.5">—</span> {s}
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-gray-400 mt-2 italic">These will be noted as unavailable in your response</p>
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-violet-700 to-indigo-800 text-white px-6 py-5">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <a href="/dashboard" className="text-violet-300 hover:text-white text-sm">← Dashboard</a>
            <span className="text-violet-400">·</span>
            <span className="text-violet-200 text-sm">Communication</span>
          </div>
          <h1 className="text-2xl font-bold mt-2">Media & RTI Response Assistant 🎙️</h1>
          <p className="text-violet-200 text-sm mt-0.5">Data-backed responses to journalist queries and RTI applications</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-6">
        <div className="max-w-7xl mx-auto flex">
          {[
            { id: "media", label: "Media response", icon: "📰" },
            { id: "rti", label: "RTI response", icon: "📜" },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as "media" | "rti")}
              className={`flex items-center gap-2 px-6 py-4 text-sm font-semibold border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-violet-600 text-violet-700"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              <span>{tab.icon}</span> {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-[45%_55%] gap-8">

          {/* ─────────────── LEFT: Input form ──────────────────────────── */}
          <div className="space-y-5">

            {/* ══ MEDIA TAB ═══════════════════════════════════════════════ */}
            {activeTab === "media" && (
              <>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1.5">Media query</label>
                  <textarea
                    rows={6}
                    value={mediaQuery}
                    onChange={e => setMediaQuery(e.target.value)}
                    placeholder={`Paste or type the journalist's question here...\n\nExamples:\n· How many potholes were reported and fixed in your ward last year?\n· Why has the streetlight outside the school been broken for months?\n· What is your response to allegations about drainage work delays?`}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-violet-400 text-sm resize-none bg-white"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1.5">Query source <span className="font-normal text-gray-400">(optional)</span></label>
                  <input
                    type="text"
                    value={mediaSource}
                    onChange={e => setMediaSource(e.target.value)}
                    placeholder="Journalist name, publication, or outlet"
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-violet-400 text-sm bg-white"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">How do you want to respond?</label>
                  <div className="grid grid-cols-3 gap-2">
                    {([
                      { id: "data_forward", label: "Data-forward", desc: "Lead with statistics. Let numbers speak." },
                      { id: "empathetic", label: "Empathetic", desc: "Acknowledge issue, show action taken." },
                      { id: "firm", label: "Firm", desc: "Address premise directly with data." },
                    ] as const).map(t => (
                      <button
                        key={t.id}
                        onClick={() => setMediaTone(t.id)}
                        className={`p-3 rounded-xl border-2 text-left transition-all ${
                          mediaTone === t.id ? "border-violet-500 bg-violet-50" : "border-gray-200 bg-white hover:border-violet-200"
                        }`}
                      >
                        <p className="text-xs font-bold text-gray-800">{t.label}</p>
                        <p className="text-[11px] text-gray-500 mt-0.5 leading-tight">{t.desc}</p>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={analyzeMediaQuery}
                    disabled={mediaAnalyzing || mediaGenerating}
                    className="flex-1 py-3 rounded-xl text-sm font-semibold border-2 border-violet-200 text-violet-700 hover:bg-violet-50 disabled:opacity-50 transition-all"
                  >
                    {mediaAnalyzing ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="w-4 h-4 border-2 border-violet-300 border-t-violet-600 rounded-full animate-spin" />
                        Checking data...
                      </span>
                    ) : "Analyze query"}
                  </button>
                  <button
                    onClick={generateMediaResponse}
                    disabled={mediaGenerating || mediaAnalyzing || !mediaQuery.trim()}
                    className="flex-1 py-3 rounded-xl text-sm font-bold text-white bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:opacity-50 transition-all"
                  >
                    {mediaGenerating ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                        Drafting...
                      </span>
                    ) : "Generate response"}
                  </button>
                </div>
              </>
            )}

            {/* ══ RTI TAB ═════════════════════════════════════════════════ */}
            {activeTab === "rti" && (
              <>
                {!infoBannerDismissed && (
                  <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 flex items-start gap-3">
                    <span className="text-indigo-500 text-lg shrink-0">ℹ️</span>
                    <div className="flex-1">
                      <p className="text-xs text-indigo-800 leading-relaxed">
                        Under the RTI Act 2005, responses must be provided within <strong>30 days</strong> of receiving the application. 
                        This tool helps you draft a compliant response using your ward's ticket data.
                      </p>
                    </div>
                    <button onClick={() => setInfoBannerDismissed(true)} className="text-indigo-400 font-bold text-lg leading-none shrink-0">×</button>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1.5">RTI application text *</label>
                  <textarea
                    rows={7}
                    value={rtiQuery}
                    onChange={e => setRtiQuery(e.target.value)}
                    placeholder="Paste the full text of the RTI application here.&#10;&#10;Include the exact information requested by the applicant."
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-violet-400 text-sm resize-none bg-white"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1.5">Upload application document <span className="font-normal text-gray-400">(optional)</span></label>
                  <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp,application/pdf" onChange={handleImageUpload} className="hidden" />
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={imageExtracting}
                    className="w-full py-3 rounded-xl border-2 border-dashed border-gray-300 text-sm text-gray-500 hover:border-violet-300 hover:text-violet-600 transition-all"
                  >
                    {imageExtracting ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="w-4 h-4 border-2 border-violet-300 border-t-violet-600 rounded-full animate-spin" />
                        Extracting text...
                      </span>
                    ) : "📎 Upload photo or scan of application (max 5MB)"}
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-1.5">Application number</label>
                    <input
                      type="text"
                      value={rtiAppNumber}
                      onChange={e => setRtiAppNumber(e.target.value)}
                      placeholder="RTI/WC/2025/001"
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-violet-400 text-sm bg-white"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-1.5">Applicant name</label>
                    <input
                      type="text"
                      value={rtiApplicant}
                      onChange={e => setRtiApplicant(e.target.value)}
                      placeholder="Applicant name"
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-violet-400 text-sm bg-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1.5">Date received</label>
                  <input
                    type="date"
                    value={rtiDateReceived}
                    onChange={e => setRtiDateReceived(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-violet-400 text-sm bg-white"
                  />
                  {deadlineInfo && (
                    <p className={`text-xs mt-1.5 font-semibold ${deadlineInfo.urgent ? "text-red-600" : "text-gray-500"}`}>
                      {deadlineInfo.urgent ? "🚨 " : "📅 "}Response due: {deadlineInfo.text}
                    </p>
                  )}
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={analyzeRtiQuery}
                    disabled={rtiAnalyzing || rtiGenerating}
                    className="flex-1 py-3 rounded-xl text-sm font-semibold border-2 border-violet-200 text-violet-700 hover:bg-violet-50 disabled:opacity-50 transition-all"
                  >
                    {rtiAnalyzing ? (
                      <span className="flex items-center justify-center gap-2"><span className="w-4 h-4 border-2 border-violet-300 border-t-violet-600 rounded-full animate-spin" />Checking...</span>
                    ) : "Analyze application"}
                  </button>
                  <button
                    onClick={generateRtiResponse}
                    disabled={rtiGenerating || rtiAnalyzing || !rtiQuery.trim()}
                    className="flex-1 py-3 rounded-xl text-sm font-bold text-white bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 disabled:opacity-50 transition-all"
                  >
                    {rtiGenerating ? (
                      <span className="flex items-center justify-center gap-2"><span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />Drafting...</span>
                    ) : "Generate response"}
                  </button>
                </div>
              </>
            )}
          </div>

          {/* ─────────────── RIGHT: Output panel ───────────────────────── */}
          <div className="space-y-4">
            {/* ══ MEDIA OUTPUT ═══════════════════════════════════════════ */}
            {activeTab === "media" && (
              <>
                {!mediaAnalysis && !mediaOutput && !mediaAnalyzing && !mediaGenerating && (
                  <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 flex flex-col items-center justify-center text-center">
                    <span className="text-5xl mb-4">📰</span>
                    <p className="text-gray-700 font-semibold">Enter a media query on the left to get started</p>
                    <p className="text-gray-400 text-sm mt-1">Real ward data will be used to ground your response</p>
                  </div>
                )}
                {(mediaAnalyzing || mediaGenerating) && !mediaOutput && (
                  <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 flex flex-col items-center justify-center">
                    <div className="w-10 h-10 border-4 border-violet-200 border-t-violet-600 rounded-full animate-spin mb-4" />
                    <p className="text-gray-600 font-semibold">{mediaAnalyzing ? "Checking what data we have..." : "Drafting your response..."}</p>
                  </div>
                )}
                {mediaAnalysis && !mediaOutput && (
                  <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                    <AnalysisPanel analysis={mediaAnalysis} />
                  </div>
                )}
                {mediaOutput && (
                  <div className="space-y-4">
                    {/* Quotable statement */}
                    <div className="bg-violet-50 border border-violet-200 rounded-2xl p-5">
                      <p className="text-xs font-bold text-violet-700 uppercase tracking-wide mb-2">Your quote for the journalist</p>
                      <p className="text-sm text-violet-900 font-medium leading-relaxed italic">&ldquo;{mediaOutput.quotable_statement}&rdquo;</p>
                      <button onClick={() => copyText(mediaOutput.quotable_statement, "quote")} className="mt-3 text-xs font-semibold bg-violet-100 text-violet-700 hover:bg-violet-200 px-3 py-1.5 rounded-lg transition-all">
                        {copiedKey === "quote" ? "✅ Copied!" : "📋 Copy quote"}
                      </button>
                    </div>

                    {/* Supporting data points */}
                    <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
                      <p className="text-xs font-bold text-gray-600 uppercase tracking-wide mb-3">Key facts to reference</p>
                      <div className="space-y-2">
                        {mediaOutput.supporting_data_points.map((pt, i) => (
                          <div key={i} className="flex items-start gap-3">
                            <div className="w-0.5 h-full bg-indigo-300 rounded-full shrink-0 mt-1.5 self-stretch" />
                            <p className="text-sm text-gray-700 leading-relaxed">{pt}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Full response letter */}
                    <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
                      <p className="text-xs font-bold text-gray-600 uppercase tracking-wide mb-3">Complete response letter</p>
                      <p className="text-sm text-gray-800 leading-[1.8] whitespace-pre-wrap">{mediaOutput.full_response_letter}</p>
                      <div className="flex gap-2 mt-4">
                        <button onClick={() => copyText(mediaOutput.full_response_letter, "letter")} className="text-xs font-semibold bg-gray-100 text-gray-600 hover:bg-gray-200 px-3 py-1.5 rounded-lg transition-all">
                          {copiedKey === "letter" ? "✅ Copied!" : "📋 Copy letter"}
                        </button>
                      </div>
                    </div>

                    {/* Data gaps */}
                    {mediaOutput.data_gaps_note && (
                      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                        <p className="text-xs font-bold text-amber-800 mb-1">Note for councillor:</p>
                        <p className="text-xs text-amber-700 leading-relaxed">{mediaOutput.data_gaps_note}</p>
                        <p className="text-[11px] text-amber-500 mt-2 italic">Consider adding this information manually before sending</p>
                      </div>
                    )}

                    {/* Regenerate */}
                    <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
                      <p className="text-xs font-semibold text-gray-600 mb-2">Regenerate with different tone:</p>
                      <div className="flex gap-2">
                        {(["data_forward", "empathetic", "firm"] as const).map(t => (
                          <button key={t} onClick={() => { setMediaTone(t); }} className={`flex-1 py-1.5 rounded-lg text-xs font-semibold border transition-all ${mediaTone === t ? "bg-violet-600 text-white border-violet-600" : "border-gray-300 text-gray-600 hover:border-violet-300"}`}>
                            {t === "data_forward" ? "Data-forward" : t.charAt(0).toUpperCase() + t.slice(1)}
                          </button>
                        ))}
                      </div>
                      <button onClick={generateMediaResponse} disabled={mediaGenerating} className="mt-2 w-full py-2 rounded-lg text-xs font-bold bg-violet-100 text-violet-700 hover:bg-violet-200 transition-all disabled:opacity-50">
                        {mediaGenerating ? "Regenerating..." : "Regenerate →"}
                      </button>
                    </div>

                    <p className="text-[11px] text-gray-400 italic text-center">Review all figures before sending. This is an AI-generated draft.</p>
                  </div>
                )}
              </>
            )}

            {/* ══ RTI OUTPUT ═══════════════════════════════════════════════ */}
            {activeTab === "rti" && (
              <>
                {!rtiAnalysis && !rtiOutput && !rtiAnalyzing && !rtiGenerating && (
                  <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 flex flex-col items-center justify-center text-center">
                    <span className="text-5xl mb-4">📜</span>
                    <p className="text-gray-700 font-semibold">Paste the RTI application text to get started</p>
                    <p className="text-gray-400 text-sm mt-1">A compliant RTI Act 2005 response will be drafted</p>
                  </div>
                )}
                {(rtiAnalyzing || rtiGenerating) && !rtiOutput && (
                  <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 flex flex-col items-center justify-center">
                    <div className="w-10 h-10 border-4 border-violet-200 border-t-violet-600 rounded-full animate-spin mb-4" />
                    <p className="text-gray-600 font-semibold">{rtiAnalyzing ? "Analyzing application..." : "Drafting RTI response..."}</p>
                  </div>
                )}
                {rtiAnalysis && !rtiOutput && (
                  <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                    <AnalysisPanel analysis={rtiAnalysis} />
                  </div>
                )}
                {rtiOutput?.rti_response_document && (
                  <div className="space-y-4">
                    {/* Document preview */}
                    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
                      {/* Letterhead */}
                      <div className="bg-gradient-to-r from-gray-800 to-gray-900 text-white px-6 py-5 text-center">
                        <p className="text-xs font-bold tracking-widest text-gray-300 uppercase">Office of the Ward Councillor</p>
                        <p className="text-base font-bold mt-0.5">Ward {user?.ward_id}</p>
                        <div className="h-px bg-gray-600 my-3" />
                        {/* Metadata */}
                        <div className="grid grid-cols-2 text-left gap-x-4 gap-y-1 text-xs">
                          <span className="text-gray-400">App No:</span>
                          <span className="text-white font-medium">{rtiOutput.rti_response_document.header.application_number || "—"}</span>
                          <span className="text-gray-400">Date Received:</span>
                          <span className="text-white font-medium">{rtiOutput.rti_response_document.header.date_of_receipt || "—"}</span>
                          <span className="text-gray-400">Response Date:</span>
                          <span className="text-white font-medium">{rtiOutput.rti_response_document.header.date_of_response}</span>
                          <span className="text-gray-400">Deadline:</span>
                          <span className="text-white font-medium">{rtiOutput.rti_response_document.header.response_deadline || "—"}</span>
                        </div>
                      </div>

                      <div className="px-6 py-5 space-y-4">
                        <p className="text-center text-xs font-bold text-gray-800 uppercase tracking-wide border-y border-gray-200 py-2">
                          Response to Application under Right to Information Act, 2005
                        </p>

                        <p className="text-sm font-medium text-gray-700">{rtiOutput.rti_response_document.applicant_reference}</p>
                        <p className="text-sm text-gray-600 leading-relaxed">{rtiOutput.rti_response_document.acknowledgment_paragraph}</p>

                        {rtiOutput.rti_response_document.information_provided.length > 0 && (
                          <div>
                            <p className="text-xs font-bold text-gray-800 uppercase tracking-wide mb-3">Information Provided</p>
                            <div className="space-y-4">
                              {rtiOutput.rti_response_document.information_provided.map((item, i) => (
                                <div key={i} className="pl-4 border-l-2 border-indigo-200">
                                  <p className="text-xs font-bold text-gray-700">{i + 1}. {item.query_item}</p>
                                  <p className="text-sm text-gray-600 mt-1 leading-relaxed">{item.response}</p>
                                  {item.data_basis && <p className="text-[11px] text-gray-400 mt-1 italic">Source: {item.data_basis}</p>}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {rtiOutput.rti_response_document.information_not_held.length > 0 && (
                          <div>
                            <p className="text-xs font-bold text-gray-800 uppercase tracking-wide mb-3">Information Not Available</p>
                            <div className="space-y-3">
                              {rtiOutput.rti_response_document.information_not_held.map((item, i) => (
                                <div key={i} className="pl-4 border-l-2 border-amber-200">
                                  <p className="text-xs font-bold text-amber-800">{i + 1}. {item.query_item}</p>
                                  <p className="text-sm text-gray-600 mt-0.5">{item.reason}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        <p className="text-sm text-gray-600 leading-relaxed">{rtiOutput.rti_response_document.closing_paragraph}</p>

                        <div className="text-right">
                          <p className="text-sm font-bold text-gray-800">{rtiOutput.rti_response_document.signature_block.name}</p>
                          <p className="text-xs text-gray-500">{rtiOutput.rti_response_document.signature_block.designation}</p>
                          <p className="text-xs text-gray-400">{rtiOutput.rti_response_document.signature_block.ward}</p>
                          <p className="text-xs text-gray-400">{rtiOutput.rti_response_document.signature_block.date}</p>
                        </div>
                      </div>
                    </div>

                    {/* Internal note */}
                    {rtiOutput.internal_note && (
                      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                        <p className="text-xs font-bold text-amber-800">Internal note (not in the document):</p>
                        <p className="text-xs text-amber-700 mt-1 leading-relaxed">{rtiOutput.internal_note}</p>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-3">
                      <button
                        onClick={() => {
                          const doc = rtiOutput.rti_response_document;
                          const text = `${doc.applicant_reference}\n\n${doc.acknowledgment_paragraph}\n\n${doc.information_provided.map((i, n) => `${n+1}. ${i.query_item}\n${i.response}`).join("\n\n")}\n\n${doc.closing_paragraph}\n\n${doc.signature_block.name}\n${doc.signature_block.designation}`;
                          copyText(text, "rti-doc");
                        }}
                        className="flex-1 py-2.5 text-sm font-semibold bg-gray-100 text-gray-700 hover:bg-gray-200 rounded-xl transition-all"
                      >
                        {copiedKey === "rti-doc" ? "✅ Copied!" : "📋 Copy full document"}
                      </button>
                      <button onClick={downloadRtiPdf} className="flex-1 py-2.5 text-sm font-bold bg-violet-600 text-white hover:bg-violet-700 rounded-xl transition-all">
                        ↓ Download as PDF
                      </button>
                    </div>

                    <p className="text-[11px] text-gray-400 italic text-center">
                      Review all figures before signing. This is an AI-assisted draft — you are responsible for the accuracy of the final signed document.
                    </p>
                  </div>
                )}
              </>
            )}

            {/* ══ History ══════════════════════════════════════════════════ */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <button
                onClick={() => { setHistoryExpanded(e => !e); if (!historyLoaded) loadHistory(); }}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span>🕐</span>
                  <span className="text-sm font-semibold text-gray-700">Past responses</span>
                </div>
                <span className="text-gray-400 text-sm">{historyExpanded ? "▲" : "▼"}</span>
              </button>
              {historyExpanded && (
                <div className="border-t border-gray-100">
                  {history.length === 0 ? (
                    <p className="text-sm text-gray-400 text-center py-6 italic">No past responses yet</p>
                  ) : (
                    <div className="divide-y divide-gray-50">
                      {history.map(h => (
                        <div key={h.response_id} className="flex items-center justify-between px-5 py-3 hover:bg-gray-50">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-0.5">
                              <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${h.type === "media" ? "bg-blue-100 text-blue-700" : "bg-purple-100 text-purple-700"}`}>
                                {h.type === "media" ? "Media" : "RTI"}
                              </span>
                              {h.query_source && <span className="text-[11px] text-gray-400">{h.query_source}</span>}
                            </div>
                            <p className="text-sm text-gray-700 truncate">{h.query_text}</p>
                            <p className="text-[11px] text-gray-400 mt-0.5">{relativeDate(h.created_at)}</p>
                          </div>
                          <button onClick={() => loadPastResponse(h.response_id, h.type)} className="ml-3 text-xs font-semibold text-violet-600 hover:text-violet-800 shrink-0">
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
