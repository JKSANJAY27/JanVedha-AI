"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { trustApi } from "@/lib/api";

interface TrustScoreData {
  ward_id: number;
  month: string;
  trust_score: number;
  grade: "green" | "amber" | "red";
  components: {
    on_time_rate: { value: number; label: string; weight: number };
    verified_completion_rate: { value: number; label: string; weight: number };
    citizen_satisfaction: { value: number; label: string; weight: number };
    quality_score: { value: number; label: string; weight: number };
  };
  avg_resolution_hours: number;
}

interface HistoryPoint {
  month: string;
  trust_score: number;
  grade: "green" | "amber" | "red";
}

interface Props {
  wardId: number;
  showInsights?: boolean;       // Councillor-only
  isPublic?: boolean;           // Simpler citizen view
}

const GRADE_CONFIG = {
  green: {
    ring: "from-emerald-400 to-teal-500",
    text: "text-emerald-600",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    badge: "bg-emerald-100 text-emerald-800 border-emerald-200",
    label: "Excellent",
    emoji: "🌟",
  },
  amber: {
    ring: "from-amber-400 to-orange-500",
    text: "text-amber-600",
    bg: "bg-amber-50",
    border: "border-amber-200",
    badge: "bg-amber-100 text-amber-800 border-amber-200",
    label: "Average",
    emoji: "📊",
  },
  red: {
    ring: "from-red-400 to-rose-500",
    text: "text-red-600",
    bg: "bg-red-50",
    border: "border-red-200",
    badge: "bg-red-100 text-red-800 border-red-200",
    label: "Needs Improvement",
    emoji: "⚠️",
  },
};

function Sparkline({ history }: { history: HistoryPoint[] }) {
  if (history.length < 2) return null;

  const values = history.map(h => h.trust_score);
  const min = Math.min(...values) - 5;
  const max = Math.max(...values) + 5;
  const range = max - min || 1;
  const W = 200;
  const H = 48;
  const stepX = W / (values.length - 1);

  const points = values.map((v, i) => ({
    x: i * stepX,
    y: H - ((v - min) / range) * H,
  }));

  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  const areaD = `${pathD} L ${W} ${H} L 0 ${H} Z`;

  const last = history[history.length - 1];
  const prev = history[history.length - 2];
  const diff = Math.round(last.trust_score - prev.trust_score);

  return (
    <div className="flex items-end gap-4">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
        <defs>
          <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6366f1" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaD} fill="url(#sparkGrad)" />
        <path d={pathD} fill="none" stroke="#6366f1" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={i === points.length - 1 ? 4 : 2}
            fill={i === points.length - 1 ? "#6366f1" : "#a5b4fc"} />
        ))}
      </svg>
      <div className="text-right">
        <p className={`text-sm font-extrabold ${diff >= 0 ? "text-emerald-600" : "text-red-500"}`}>
          {diff >= 0 ? "↑" : "↓"} {Math.abs(diff)} pts
        </p>
        <p className="text-xs text-gray-400">vs last month</p>
      </div>
    </div>
  );
}

function ProgressBar({ value, colorClass }: { value: number; colorClass: string }) {
  return (
    <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(value, 100)}%` }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className={`h-full rounded-full ${colorClass}`}
      />
    </div>
  );
}

export default function WardTrustScoreCard({ wardId, showInsights = false, isPublic = false }: Props) {
  const [score, setScore] = useState<TrustScoreData | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [insight, setInsight] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingInsight, setLoadingInsight] = useState(false);

  useEffect(() => {
    Promise.all([
      trustApi.getTrustScore(wardId),
      trustApi.getTrustScoreHistory(wardId, 6),
    ])
      .then(([scoreRes, histRes]) => {
        setScore(scoreRes.data);
        setHistory(histRes.data);
      })
      .catch(() => toast.error("Failed to load trust score"))
      .finally(() => setLoading(false));
  }, [wardId]);

  const fetchInsight = async () => {
    if (!showInsights) return;
    setLoadingInsight(true);
    try {
      const res = await trustApi.getTrustScoreInsights(wardId);
      setInsight(res.data.insight);
    } catch {
      toast.error("Failed to generate insight");
    } finally {
      setLoadingInsight(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-8 flex items-center justify-center gap-4">
        <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-500 rounded-full animate-spin" />
        <p className="text-gray-400 text-sm">Computing trust score...</p>
      </div>
    );
  }

  if (!score) return null;

  const cfg = GRADE_CONFIG[score.grade];
  const components = [
    { key: "on_time_rate", color: "bg-blue-500", ...score.components.on_time_rate },
    { key: "verified_completion_rate", color: "bg-emerald-500", ...score.components.verified_completion_rate },
    { key: "citizen_satisfaction", color: "bg-violet-500", ...score.components.citizen_satisfaction },
    { key: "quality_score", color: "bg-amber-500", ...score.components.quality_score },
  ];

  return (
    <div className={`rounded-3xl border-2 overflow-hidden shadow-lg ${cfg.bg} ${cfg.border}`}>
      {/* Top header */}
      <div className="px-6 py-5 border-b border-current/10 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-1">
            {isPublic ? "📊 Ward Report Card" : "🏆 Public Trust Score"}
          </p>
          <h2 className="text-lg font-extrabold text-gray-900">Ward {wardId} · {score.month}</h2>
        </div>
        <span className={`text-xs font-bold px-3 py-1.5 rounded-full border ${cfg.badge}`}>
          {cfg.emoji} {cfg.label}
        </span>
      </div>

      {/* Score + sparkline */}
      <div className="px-6 py-6 flex items-center gap-6 flex-wrap">
        {/* Big score circle */}
        <div className={`relative w-28 h-28 rounded-full flex items-center justify-center bg-gradient-to-br ${cfg.ring} shadow-xl flex-shrink-0`}>
          <div className="w-20 h-20 rounded-full bg-white flex flex-col items-center justify-center">
            <span className={`text-3xl font-extrabold ${cfg.text}`}>{Math.round(score.trust_score)}</span>
            <span className="text-xs text-gray-400 font-semibold">/ 100</span>
          </div>
        </div>

        {/* Right: label + sparkline */}
        <div className="flex-1 min-w-0">
          <p className={`text-2xl font-extrabold ${cfg.text} mb-1`}>{cfg.label}</p>
          <p className="text-sm text-gray-500 mb-4">
            Avg resolution: <span className="font-bold text-gray-700">{score.avg_resolution_hours.toFixed(0)}h</span>
          </p>
          {history.length >= 2 && <Sparkline history={history} />}
        </div>
      </div>

      {/* Component metrics */}
      <div className="px-6 pb-6 space-y-4">
        <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">Score Breakdown</p>
        <div className="space-y-3">
          {components.map(comp => (
            <div key={comp.key}>
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-semibold text-gray-700">{comp.label}</p>
                <span className={`text-sm font-extrabold ${
                  comp.value >= 75 ? "text-emerald-600"
                  : comp.value >= 50 ? "text-amber-600"
                  : "text-red-600"
                }`}>{comp.value.toFixed(0)}%</span>
              </div>
              <ProgressBar value={comp.value} colorClass={comp.color} />
            </div>
          ))}
        </div>
      </div>

      {/* Councillor-only: AI Insight */}
      {showInsights && (
        <div className="px-6 pb-6">
          <div className="border-t border-current/10 pt-5">
            {insight ? (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-white/80 border border-indigo-200 rounded-2xl p-4"
              >
                <p className="text-xs font-bold text-indigo-600 uppercase tracking-wide mb-2">🤖 Gemini Insight</p>
                <p className="text-sm text-gray-700 leading-relaxed">{insight}</p>
              </motion.div>
            ) : (
              <button
                onClick={fetchInsight}
                disabled={loadingInsight}
                id="generate-trust-insight-btn"
                className="w-full py-3 rounded-2xl border-2 border-indigo-200 text-indigo-700 font-bold text-sm hover:bg-indigo-50 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loadingInsight ? (
                  <><span className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" /> Generating insight...</>
                ) : (
                  <><span>🤖</span> Generate AI Insight</>
                )}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
