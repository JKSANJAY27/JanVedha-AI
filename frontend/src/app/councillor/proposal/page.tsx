"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";
import { proposalsApi } from "@/lib/api";

// Mini static map for zone preview
const MiniMap = dynamic(() => import("../opportunity/MapView"), { ssr: false });

// ── Constants ─────────────────────────────────────────────────────────────────
const DEV_TYPES = [
  { value: "road_resurfacing", label: "Road Resurfacing", icon: "◈" },
  { value: "streetlight_installation", label: "Streetlight Installation", icon: "◈" },
  { value: "drainage_improvement", label: "Drainage Improvement", icon: "◈" },
  { value: "park_open_space", label: "Park / Open Space", icon: "◈" },
  { value: "water_pipeline", label: "Water Pipeline", icon: "◈" },
  { value: "waste_collection_point", label: "Waste Collection Point", icon: "◈" },
  { value: "community_center", label: "Community Center", icon: "◈" },
];

const CAT_TO_DEV: Record<string, string> = {
  roads: "road_resurfacing",
  road: "road_resurfacing",
  water: "water_pipeline",
  lighting: "streetlight_installation",
  drainage: "drainage_improvement",
  waste: "waste_collection_point",
  other: "community_center",
};

const LOADING_MSGS = [
  "Analysing zone data…",
  "Reviewing 12 months of complaints…",
  "Drafting proposal sections with AI…",
  "Formatting official document…",
];

// ── Types ─────────────────────────────────────────────────────────────────────
interface ProposalJSON {
  title?: string;
  reference_number_placeholder?: string;
  date?: string;
  executive_summary?: string;
  problem_statement?: string;
  proposed_solution?: string;
  location_justification?: string;
  beneficiary_analysis?: string;
  budget_breakdown?: Array<{item: string; quantity: string; unit_cost: string; total: string}>;
  total_budget_requested?: string;
  expected_outcomes?: string[];
  implementation_timeline?: Array<{phase: string; activity: string; duration: string}>;
  recommendation?: string;
}

interface ProposalResult {
  proposal_id: string;
  title: string;
  proposal_json: ProposalJSON;
  download_url: string;
  created_at: string;
  estimated_cost: number;
  total_complaints_evidence: number;
  low_data_warning?: string;
  evidence: {
    total_complaints: number;
    complaints_by_category: Record<string, number>;
    unresolved_count: number;
    avg_resolution_days: number | string;
    oldest_unresolved_date: string;
    most_recent_complaint_date: string;
  };
}

interface PastProposal {
  proposal_id: string;
  title: string;
  development_type: string;
  estimated_cost: number;
  created_at: string;
  status: string;
}

// ── Section renderer ──────────────────────────────────────────────────────────
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <div className="border-b-2 border-[#003366] pb-1 mb-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-[#003366]">{title}</h3>
      </div>
      <div className="text-sm text-gray-700 leading-relaxed">{children}</div>
    </div>
  );
}

// ── Inner page that uses searchParams ─────────────────────────────────────────
function ProposalPageContent() {
  const { user, isCouncillor, isAdmin, isSupervisor } = useAuth();
  const router = useRouter();
  const params = useSearchParams();

  // Pre-fill from opportunity spotter params
  const prefillLat = params.get("cell_center_lat") ? parseFloat(params.get("cell_center_lat")!) : null;
  const prefillLng = params.get("cell_center_lng") ? parseFloat(params.get("cell_center_lng")!) : null;
  const prefillCat = params.get("dominant_category") ?? "";
  const prefillZoneId = params.get("zone_id") ?? "";
  const prefillRec = params.get("recommendation_text") ?? "";
  const isPrefilled = prefillLat !== null && prefillLng !== null;

  // Form state
  const [devType, setDevType] = useState(CAT_TO_DEV[prefillCat] ?? "road_resurfacing");
  const [estimatedCost, setEstimatedCost] = useState("");
  const [additionalContext, setAdditionalContext] = useState(
    prefillRec ? `Recommended: ${decodeURIComponent(prefillRec)}` : ""
  );
  const [councillorName, setCouncillorName] = useState(user?.name ?? "");
  const [wardName, setWardName] = useState(`Ward ${user?.ward_id ?? ""}`);
  const [manualLat, setManualLat] = useState("");
  const [manualLng, setManualLng] = useState("");

  // Page state
  const [state, setState] = useState<"form" | "loading" | "preview">("form");
  const [loadingMsgIdx, setLoadingMsgIdx] = useState(0);
  const [result, setResult] = useState<ProposalResult | null>(null);
  const [pastProposals, setPastProposals] = useState<PastProposal[]>([]);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  useEffect(() => {
    if (user) {
      setCouncillorName(user.name ?? "");
      setWardName(`Ward ${user.ward_id ?? ""}`);
    }
    const allowed = isCouncillor || isAdmin || isSupervisor;
    if (user && !allowed) router.push("/officer/dashboard");
  }, [user]);

  useEffect(() => {
    if (user?.ward_id) {
      proposalsApi.list(user.ward_id).then((r) => setPastProposals(r.data ?? [])).catch(() => {});
    }
  }, [user?.ward_id]);

  // Cycle loading messages
  useEffect(() => {
    if (state !== "loading") return;
    const iv = setInterval(() => {
      setLoadingMsgIdx((i) => Math.min(i + 1, LOADING_MSGS.length - 1));
    }, 3000);
    return () => clearInterval(iv);
  }, [state]);

  const handleGenerate = useCallback(async () => {
    const lat = isPrefilled ? prefillLat! : parseFloat(manualLat);
    const lng = isPrefilled ? prefillLng! : parseFloat(manualLng);

    if (!lat || !lng || isNaN(lat) || isNaN(lng)) {
      toast.error("Please provide valid zone coordinates");
      return;
    }
    if (!councillorName.trim()) { toast.error("Please enter councillor name"); return; }

    setState("loading");
    setLoadingMsgIdx(0);

    try {
      const res = await proposalsApi.generate({
        ward_id: user?.ward_id,
        zone_cell_id: prefillZoneId || undefined,
        zone_lat: lat,
        zone_lng: lng,
        development_type: devType,
        estimated_cost: estimatedCost ? parseFloat(estimatedCost) : undefined,
        councillor_name: councillorName,
        ward_name: wardName,
        additional_context: additionalContext || undefined,
      });
      setResult(res.data);
      setState("preview");
      // Refresh past proposals list
      if (user?.ward_id) {
        proposalsApi.list(user.ward_id).then((r) => setPastProposals(r.data ?? [])).catch(() => {});
      }
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? "Failed to generate proposal. Please try again.");
      setState("form");
    }
  }, [isPrefilled, prefillLat, prefillLng, manualLat, manualLng, devType, estimatedCost, additionalContext, councillorName, wardName, user]);

  const handleDownload = useCallback(async () => {
    if (!result) return;
    try {
      const res = await proposalsApi.download(result.proposal_id);
      const blob = new Blob([res.data], {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Ward_Proposal_${result.proposal_id}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Download failed. The document may not have been generated.");
    }
  }, [result]);

  if (!user) return null;

  // ── LOADING STATE ──────────────────────────────────────────────────────────
  if (state === "loading") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="bg-white rounded-3xl shadow-xl border border-gray-100 p-12 max-w-md w-full mx-4 text-center">
          <div className="w-16 h-16 border-4 border-emerald-200 border-t-emerald-600 rounded-full animate-spin mx-auto mb-6" />
          <AnimatePresence mode="wait">
            <motion.p
              key={loadingMsgIdx}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="text-gray-700 font-semibold text-lg mb-2"
            >
              {LOADING_MSGS[loadingMsgIdx]}
            </motion.p>
          </AnimatePresence>
          <p className="text-gray-400 text-sm">This takes 8–15 seconds. Please wait.</p>
          <div className="mt-6 flex gap-1 justify-center">
            {LOADING_MSGS.map((_, i) => (
              <div
                key={i}
                className={`h-1.5 rounded-full transition-all duration-300 ${i <= loadingMsgIdx ? "bg-emerald-500 w-8" : "bg-gray-200 w-4"}`}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ── PREVIEW STATE ──────────────────────────────────────────────────────────
  if (state === "preview" && result) {
    const p = result.proposal_json;
    const catTotal = Object.values(result.evidence.complaints_by_category).reduce((a, b) => a + b, 0) || 1;

    return (
      <div className="min-h-screen bg-slate-50">
        {/* Top bar */}
        <div className="bg-gradient-to-r from-emerald-700 to-teal-800 text-white px-6 py-4 sticky top-0 z-50">
          <div className="max-w-5xl mx-auto flex items-center gap-4 flex-wrap">
            <div>
              <p className="text-emerald-300 text-xs">Proposal Preview</p>
              <h1 className="font-bold text-sm truncate max-w-md">{result.title}</h1>
            </div>
            <div className="ml-auto flex gap-3 flex-wrap">
              <button
                onClick={() => setState("form")}
                className="text-xs font-semibold px-4 py-2 rounded-lg border border-emerald-400 text-emerald-200 hover:bg-emerald-600 transition-colors"
              >
                ← Edit & Regenerate
              </button>
              <button
                onClick={handleDownload}
                className="text-xs font-bold px-4 py-2 rounded-lg bg-white text-emerald-800 hover:bg-emerald-50 transition-colors flex items-center gap-2"
              >
                ↓ Download .docx
              </button>
            </div>
          </div>
        </div>

        <div className="max-w-5xl mx-auto px-4 py-8 flex flex-col lg:flex-row gap-6">
          {/* ── A4 document preview ────────────────────────────────────────── */}
          <div className="flex-1 min-w-0">
            {result.low_data_warning && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-4 text-xs text-amber-800 flex gap-2">
                <span>⚠️</span>
                <span>{result.low_data_warning}</span>
              </div>
            )}

            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8 lg:p-12">
              {/* Document header */}
              <div className="text-center mb-6">
                <h1 className="text-lg font-extrabold text-[#003366] uppercase tracking-wider">Ward Development Proposal</h1>
                <h2 className="text-base font-semibold text-gray-800 mt-1">{p.title}</h2>
              </div>

              {/* Metadata grid */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mb-6 pb-4 border-b border-gray-200">
                {[
                  ["Reference", p.reference_number_placeholder],
                  ["Ward", result.proposal_json.title ? wardName : ""],
                  ["Councillor", result.proposal_json.recommendation ? councillorName : ""],
                  ["Date", p.date],
                ].map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <span className="text-gray-400 font-semibold w-20 shrink-0">{k}:</span>
                    <span className="text-gray-700">{v}</span>
                  </div>
                ))}
              </div>

              {/* Sections */}
              {p.executive_summary && <Section title="Executive Summary">{p.executive_summary}</Section>}
              {p.problem_statement && <Section title="Problem Statement"><span style={{ whiteSpace: "pre-line" }}>{p.problem_statement}</span></Section>}
              {p.proposed_solution && <Section title="Proposed Solution"><span style={{ whiteSpace: "pre-line" }}>{p.proposed_solution}</span></Section>}
              {p.location_justification && <Section title="Location Justification">{p.location_justification}</Section>}
              {p.beneficiary_analysis && <Section title="Beneficiary Analysis">{p.beneficiary_analysis}</Section>}

              {/* Budget table */}
              {p.budget_breakdown && p.budget_breakdown.length > 0 && (
                <Section title="Budget Breakdown">
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr className="bg-[#003366] text-white">
                          {["Item", "Quantity", "Unit Cost", "Total"].map((h) => (
                            <th key={h} className="px-3 py-2 text-left font-semibold">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {p.budget_breakdown.map((item, i) => (
                          <tr key={i} className={i % 2 === 1 ? "bg-blue-50" : "bg-white"}>
                            <td className="px-3 py-2 border border-gray-100">{item.item}</td>
                            <td className="px-3 py-2 border border-gray-100">{item.quantity}</td>
                            <td className="px-3 py-2 border border-gray-100">{item.unit_cost}</td>
                            <td className="px-3 py-2 border border-gray-100 font-semibold">{item.total}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="font-bold text-sm mt-3 text-[#003366]">
                    Total: {p.total_budget_requested}
                  </p>
                  <p className="text-[10px] text-gray-400 mt-1">
                    Cost estimate is approximate. Subject to detailed survey and tender process.
                  </p>
                </Section>
              )}

              {/* Expected outcomes */}
              {p.expected_outcomes && (
                <Section title="Expected Outcomes">
                  <ul className="list-disc ml-4 space-y-1">
                    {p.expected_outcomes.map((o, i) => <li key={i}>{o}</li>)}
                  </ul>
                </Section>
              )}

              {/* Timeline */}
              {p.implementation_timeline && (
                <Section title="Implementation Timeline">
                  <table className="w-full text-xs border-collapse">
                    <thead>
                      <tr className="bg-[#003366] text-white">
                        {["Phase", "Activity", "Duration"].map((h) => (
                          <th key={h} className="px-3 py-2 text-left font-semibold">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {p.implementation_timeline.map((ph, i) => (
                        <tr key={i} className="border-b border-gray-100">
                          <td className="px-3 py-2 font-semibold text-[#003366]">{ph.phase}</td>
                          <td className="px-3 py-2">{ph.activity}</td>
                          <td className="px-3 py-2 whitespace-nowrap">{ph.duration}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Section>
              )}

              {/* Recommendation */}
              {p.recommendation && (
                <Section title="Recommendation">
                  <p className="italic">{p.recommendation}</p>
                </Section>
              )}

              {/* Footer */}
              <div className="mt-8 pt-4 border-t border-gray-200 text-center text-[10px] text-gray-400">
                {wardName} Ward · JanVedha AI Generated · {p.date} · Costs are estimates subject to survey
              </div>
            </div>

            {/* Evidence summary */}
            <div className="mt-4 bg-white rounded-xl border border-gray-100 shadow-sm">
              <button
                onClick={() => setEvidenceOpen(!evidenceOpen)}
                className="w-full px-5 py-3 flex items-center gap-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 rounded-xl"
              >
                <span>📊 Evidence Summary</span>
                <span className="ml-auto text-gray-400">{evidenceOpen ? "▲" : "▼"}</span>
              </button>
              {evidenceOpen && (
                <div className="px-5 pb-4 border-t border-gray-50 text-xs text-gray-600 space-y-2 pt-3">
                  <div className="flex gap-6">
                    <div><p className="font-bold text-gray-800 text-base">{result.evidence.total_complaints}</p><p className="text-gray-400">Complaints analysed</p></div>
                    <div><p className="font-bold text-gray-800 text-base">{result.evidence.unresolved_count}</p><p className="text-gray-400">Currently unresolved</p></div>
                    <div><p className="font-bold text-gray-800 text-base">{result.evidence.avg_resolution_days}</p><p className="text-gray-400">Avg resolution days</p></div>
                  </div>
                  <div>
                    <p className="font-semibold text-gray-700 mb-1">Category breakdown</p>
                    {Object.entries(result.evidence.complaints_by_category).map(([cat, count]) => (
                      <div key={cat} className="flex items-center gap-2 mb-1">
                        <div className="h-2 bg-emerald-400 rounded" style={{ width: `${(count / catTotal) * 120}px` }} />
                        <span className="text-gray-600">{cat}: {count}</span>
                      </div>
                    ))}
                  </div>
                  <p className="text-gray-400">Date range: {result.evidence.most_recent_complaint_date} · Oldest unresolved: {result.evidence.oldest_unresolved_date}</p>
                </div>
              )}
            </div>
          </div>

          {/* ── Past proposals sidebar ────────────────────────────────────── */}
          {pastProposals.length > 0 && (
            <div className="w-full lg:w-72 shrink-0">
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 sticky top-24">
                <h3 className="font-bold text-gray-800 text-sm mb-3">Past Proposals</h3>
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {pastProposals.slice(0, 5).map((p) => (
                    <a
                      key={p.proposal_id}
                      href={`/councillor/proposal?view=${p.proposal_id}`}
                      className="block p-3 rounded-xl border border-gray-100 hover:border-emerald-200 hover:bg-emerald-50 transition-colors"
                    >
                      <p className="text-xs font-semibold text-gray-800 line-clamp-2">{p.title}</p>
                      <p className="text-[10px] text-emerald-700 font-medium mt-1">{p.development_type.replace(/_/g, " ")}</p>
                      <p className="text-[10px] text-gray-400 mt-0.5">{new Date(p.created_at).toLocaleDateString("en-IN")}</p>
                    </a>
                  ))}
                </div>
                <a href="/councillor/proposals" className="block text-center text-xs text-emerald-600 font-semibold mt-3 hover:underline">
                  View all proposals →
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── FORM STATE ─────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-gradient-to-r from-emerald-700 to-teal-800 text-white px-6 py-5">
        <div className="max-w-3xl mx-auto">
          <p className="text-emerald-300 text-sm">Development · Ward {user?.ward_id}</p>
          <h1 className="text-xl font-bold mt-0.5">Generate Development Proposal 📄</h1>
          <p className="text-emerald-200 text-xs mt-0.5">AI-powered formal council proposal with evidence from ticket data</p>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        {/* Zone information */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-lg">📍</span>
            <h2 className="font-bold text-gray-800">Zone Location</h2>
            {isPrefilled && (
              <span className="ml-2 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                Pre-filled from opportunity analysis
              </span>
            )}
          </div>

          {isPrefilled ? (
            <div className="space-y-2">
              <div className="flex gap-4 text-sm">
                <div className="flex-1 bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">Latitude</p>
                  <p className="font-mono font-bold text-gray-800">{prefillLat?.toFixed(6)}</p>
                </div>
                <div className="flex-1 bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">Longitude</p>
                  <p className="font-mono font-bold text-gray-800">{prefillLng?.toFixed(6)}</p>
                </div>
              </div>
              {prefillZoneId && (
                <p className="text-xs text-gray-400">Zone {prefillZoneId} · {prefillCat} priority cluster</p>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Latitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={manualLat}
                  onChange={(e) => setManualLat(e.target.value)}
                  placeholder="12.9716"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-400"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Longitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={manualLng}
                  onChange={(e) => setManualLng(e.target.value)}
                  placeholder="80.2443"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-400"
                />
              </div>
            </div>
          )}
        </div>

        {/* Development details */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-lg">🏗️</span>
            <h2 className="font-bold text-gray-800">Development Details</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-2">Development Type</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {DEV_TYPES.map((dt) => (
                  <button
                    key={dt.value}
                    onClick={() => setDevType(dt.value)}
                    className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-medium border transition-all text-left ${
                      devType === dt.value
                        ? "border-emerald-500 bg-emerald-50 text-emerald-800"
                        : "border-gray-200 text-gray-700 hover:border-gray-300"
                    }`}
                  >
                    <span className="text-emerald-600">{dt.icon}</span>
                    {dt.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Estimated Budget (₹)</label>
              <input
                type="number"
                value={estimatedCost}
                onChange={(e) => setEstimatedCost(e.target.value)}
                placeholder="Leave blank for AI estimate"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-400"
              />
              <p className="text-[10px] text-gray-400 mt-1">A budget estimate will be auto-calculated from municipal cost tables if left blank</p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Additional Context</label>
              <textarea
                value={additionalContext}
                onChange={(e) => setAdditionalContext(e.target.value)}
                rows={3}
                placeholder="Any specific concerns, local landmarks, or context the proposal should mention..."
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-400 resize-none"
              />
            </div>
          </div>
        </div>

        {/* Councillor details */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-lg">🏛️</span>
            <h2 className="font-bold text-gray-800">Councillor Details</h2>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Your Name</label>
              <input
                type="text"
                value={councillorName}
                onChange={(e) => setCouncillorName(e.target.value)}
                placeholder="Councillor name"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-400"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Ward Name</label>
              <input
                type="text"
                value={wardName}
                onChange={(e) => setWardName(e.target.value)}
                placeholder="e.g. Ward 12 Adyar"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-400"
              />
            </div>
          </div>
        </div>

        {/* Generate button */}
        <button
          onClick={handleGenerate}
          className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-bold py-4 rounded-2xl text-base hover:shadow-lg hover:scale-[1.01] active:scale-[0.99] transition-all"
        >
          Generate Proposal with AI →
        </button>

        <p className="text-center text-xs text-gray-400">
          This takes approximately 8–15 seconds. The AI will analyse 12 months of ticket data from this location.
        </p>

        {/* Past proposals */}
        {pastProposals.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <h3 className="font-bold text-gray-800 text-sm mb-3">Recent Proposals</h3>
            <div className="space-y-2">
              {pastProposals.slice(0, 5).map((p) => (
                <a
                  key={p.proposal_id}
                  href={`/councillor/proposals`}
                  className="flex items-center justify-between p-3 rounded-xl border border-gray-100 hover:border-emerald-200 hover:bg-emerald-50 transition-colors"
                >
                  <div>
                    <p className="text-xs font-semibold text-gray-800 truncate max-w-xs">{p.title}</p>
                    <p className="text-[10px] text-gray-400 mt-0.5">{new Date(p.created_at).toLocaleDateString("en-IN")}</p>
                  </div>
                  <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full shrink-0 ml-2">
                    {p.development_type.replace(/_/g, " ")}
                  </span>
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Wrap with Suspense for useSearchParams ────────────────────────────────────
export default function ProposalPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-50 flex items-center justify-center"><div className="w-8 h-8 border-4 border-emerald-200 border-t-emerald-600 rounded-full animate-spin"/></div>}>
      <ProposalPageContent />
    </Suspense>
  );
}

