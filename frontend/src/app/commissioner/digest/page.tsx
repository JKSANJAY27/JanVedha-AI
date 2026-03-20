"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { commissionerApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function DigestPage() {
  const { user, isCommissioner } = useAuth();
  const router = useRouter();
  const [latest, setLatest] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [activeDigest, setActiveDigest] = useState<any>(null);
  const [viewLoading, setViewLoading] = useState(false);

  const SECTION_ORDER = [
    ["executive_summary", "Executive Summary"],
    ["top_concern", "⚠️ Priority Concern"],
    ["ward_performance_narrative", "Ward Performance"],
    ["department_health_narrative", "Department Health"],
    ["escalations_narrative", "Escalations"],
    ["intelligence_alerts_narrative", "Intelligence Alerts"],
    ["cctv_narrative", "CCTV Monitoring"],
    ["recommended_priority_action", "Recommended Action"],
    ["positive_highlight", "This Week's Highlight"],
  ] as [string, string][];

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [latestRes, histRes] = await Promise.all([
        commissionerApi.getLatestDigest(),
        commissionerApi.getDigestHistory(),
      ]);
      setLatest(latestRes.data);
      setHistory(histRes.data.digests || []);
    } catch {
      setLatest(null);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleGenerate = async () => {
    if (!user) return;
    setGenerating(true);
    try {
      await commissionerApi.generateDigest(user.id);
      // Poll for result
      let attempts = 0;
      while (attempts < 12) {
        await new Promise(r => setTimeout(r, 5000));
        try {
          const res = await commissionerApi.getLatestDigest();
          if (res.data?.digest && Object.keys(res.data.digest).length > 0) {
            setLatest(res.data);
            await load();
            break;
          }
        } catch {}
        attempts++;
      }
    } finally { setGenerating(false); }
  };

  const openHistoric = async (digestId: string) => {
    setViewLoading(true);
    try {
      const res = await commissionerApi.getDigest(digestId);
      setActiveDigest(res.data);
    } finally { setViewLoading(false); }
  };

  if (!isCommissioner) return (
    <div className="min-h-screen bg-[#0d1117] flex items-center justify-center">
      <p className="text-red-400">Commissioner access required.</p>
    </div>
  );

  const displayDigest = activeDigest || latest;

  return (
    <div className="min-h-screen bg-[#0d1117] text-white">
      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
          <div>
            <button onClick={() => router.push("/commissioner")} className="text-gray-400 text-sm mb-2 hover:text-white">← Back</button>
            <h1 className="text-2xl font-bold">Weekly Commissioner Digest</h1>
            <p className="text-gray-400 text-sm mt-1">AI-generated performance report for the past 7 days</p>
          </div>
          <div className="flex gap-3">
            <button onClick={handleGenerate} disabled={generating}
              className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium flex items-center gap-2">
              {generating ? (<><span className="animate-spin">⟳</span><span>Generating…</span></>) : "⚡ Generate Now"}
            </button>
            {displayDigest?.pdf_available && (
              <a href={commissionerApi.getDigestPdfUrl(displayDigest.digest_id)} target="_blank" rel="noreferrer"
                className="px-4 py-2 bg-[#161b22] border border-[#30363d] text-gray-300 hover:text-white rounded-lg text-sm font-medium flex items-center gap-2">
                📄 Download PDF
              </a>
            )}
          </div>
        </div>

        {generating && (
          <div className="mb-6 bg-violet-500/10 border border-violet-500/30 rounded-xl p-4 flex items-center gap-3">
            <div className="animate-spin text-xl">⟳</div>
            <div>
              <p className="text-violet-400 font-medium text-sm">Generating digest…</p>
              <p className="text-xs text-gray-400">JanVedha AI is analysing 7 days of city data. This takes ~30 seconds.</p>
            </div>
          </div>
        )}

        <div className="flex gap-6">
          {/* Main content */}
          <div className="flex-1 min-w-0">
            {loading ? (
              <div className="flex justify-center py-20"><div className="animate-spin text-3xl">⟳</div></div>
            ) : !displayDigest ? (
              <div className="text-center py-20 bg-[#161b22] border border-[#30363d] rounded-2xl">
                <p className="text-4xl mb-3">📋</p>
                <p className="font-medium text-white">No digest available</p>
                <p className="text-sm text-gray-400 mt-1">Click "Generate Now" to create this week's digest</p>
              </div>
            ) : (
              <div className="space-y-5">
                {/* Meta */}
                <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div>
                      <p className="text-lg font-semibold text-white">{displayDigest.week_label}</p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        Generated {new Date(displayDigest.generated_at).toLocaleString()} · By {displayDigest.generated_by}
                      </p>
                    </div>
                    {displayDigest.generation_status === "generation_failed" && (
                      <span className="text-xs px-2 py-1 bg-red-500/15 border border-red-500/30 text-red-400 rounded">Generation failed — Raw data only</span>
                    )}
                  </div>
                </div>

                {/* Digest sections */}
                {displayDigest.digest && Object.keys(displayDigest.digest).length > 0 ? (
                  SECTION_ORDER.map(([key, label]) => {
                    const content = displayDigest.digest[key];
                    if (!content) return null;
                    const isHighlight = key === "positive_highlight";
                    const isConcern = key === "top_concern";
                    const isAction = key === "recommended_priority_action";
                    return (
                      <div key={key} className={`rounded-xl border p-5 ${
                        isConcern ? "bg-red-500/10 border-red-500/30" :
                        isAction ? "bg-violet-500/10 border-violet-500/30" :
                        isHighlight ? "bg-green-500/10 border-green-500/30" :
                        "bg-[#161b22] border-[#30363d]"
                      }`}>
                        <p className={`text-xs uppercase tracking-wider mb-2 ${
                          isConcern ? "text-red-400" : isAction ? "text-violet-400" : isHighlight ? "text-green-400" : "text-gray-400"
                        }`}>{label}</p>
                        <p className="text-sm text-white leading-relaxed">{content}</p>
                      </div>
                    );
                  })
                ) : displayDigest.raw_data ? (
                  <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5">
                    <p className="text-xs text-gray-400 mb-3">AI narrative unavailable. Raw metrics:</p>
                    <pre className="text-xs text-gray-300 overflow-x-auto">
                      {JSON.stringify(displayDigest.raw_data?.overall_metrics, null, 2)}
                    </pre>
                  </div>
                ) : null}
              </div>
            )}
          </div>

          {/* History sidebar */}
          <div className="w-56 shrink-0">
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-3">Previous Digests</p>
            <div className="space-y-2">
              {history.map(d => (
                <button key={d.digest_id} onClick={() => openHistoric(d.digest_id)}
                  className={`w-full text-left px-3 py-2.5 rounded-lg border text-sm transition-colors ${
                    activeDigest?.digest_id === d.digest_id
                      ? "bg-violet-600/20 border-violet-500/50 text-violet-300"
                      : "bg-[#161b22] border-[#30363d] text-gray-300 hover:text-white hover:border-[#58a6ff]/30"
                  }`}>
                  <p className="font-medium text-xs">{d.week_label}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{new Date(d.generated_at).toLocaleDateString()}</p>
                  {d.generation_status === "generation_failed" && (
                    <span className="text-xs text-red-400">⚠ Partial</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
