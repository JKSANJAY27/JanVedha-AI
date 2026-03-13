"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { trustApi } from "@/lib/api";

interface MisinfoFlag {
  id: string;
  post_text: string;
  claim: string;
  risk_level: "high" | "medium" | "low";
  status: "pending" | "approved" | "dismissed";
  draft_response: string | null;
  approved_response: string | null;
  detected_at: string;
  platform: string;
  ward_id: number | null;
}

interface Props {
  wardId?: number;
}

const RISK_CONFIG = {
  high: {
    badge: "bg-red-100 text-red-800 border-red-300",
    card: "border-red-200 bg-red-50/30",
    icon: "🚨",
    label: "High Risk",
  },
  medium: {
    badge: "bg-amber-100 text-amber-800 border-amber-300",
    card: "border-amber-200 bg-amber-50/30",
    icon: "⚠️",
    label: "Medium Risk",
  },
  low: {
    badge: "bg-gray-100 text-gray-700 border-gray-200",
    card: "border-gray-200 bg-gray-50/30",
    icon: "ℹ️",
    label: "Low Risk",
  },
};

export default function MisinfoFlagsPanel({ wardId }: Props) {
  const [flags, setFlags] = useState<MisinfoFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [acting, setActing] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);

  const fetchFlags = () => {
    setLoading(true);
    const risk = riskFilter !== "all" ? riskFilter : undefined;
    const status = statusFilter !== "all" ? statusFilter : undefined;
    trustApi.getMisinfoFlags(wardId, risk, status, 50)
      .then(res => setFlags(res.data))
      .catch(() => toast.error("Failed to load misinformation flags"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchFlags(); }, [wardId, riskFilter, statusFilter]);

  const handleAction = async (flagId: string, action: "approve" | "dismiss" | "edit") => {
    setActing(flagId);
    try {
      const editedResponse = action === "edit" ? editText : undefined;
      await trustApi.actionMisinfoFlag(flagId, action === "edit" ? "edit" : action, editedResponse);
      toast.success(action === "dismiss" ? "Flag dismissed" : "Response approved!");
      setEditingId(null);
      fetchFlags();
    } catch {
      toast.error("Action failed");
    } finally {
      setActing(null);
    }
  };

  const handleRunScan = async () => {
    setScanning(true);
    try {
      const res = await trustApi.runMisinfoCheck(wardId);
      const count = res.data.new_flags ?? 0;
      toast.success(count > 0 ? `${count} new flag(s) detected!` : "No new suspicious posts found.");
      fetchFlags();
    } catch {
      toast.error("Scan failed");
    } finally {
      setScanning(false);
    }
  };

  const highCount = flags.filter(f => f.risk_level === "high").length;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="font-extrabold text-gray-900 text-lg flex items-center gap-2">
            🚨 Flagged Claims
          </h3>
          <p className="text-sm text-gray-500">AI-detected misinformation on social media</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {highCount > 0 && (
            <span className="bg-red-100 text-red-800 text-xs font-bold px-3 py-1.5 rounded-full border border-red-200 animate-pulse">
              🚨 {highCount} HIGH RISK
            </span>
          )}
          <button
            onClick={handleRunScan}
            disabled={scanning}
            id="run-misinfo-scan-btn"
            className="text-xs bg-violet-600 hover:bg-violet-700 text-white font-semibold px-4 py-2 rounded-xl transition-colors disabled:opacity-50 flex items-center gap-1.5"
          >
            {scanning ? (
              <><span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" /> Scanning...</>
            ) : (
              <><span>🔍</span> Run Scan</>
            )}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-1.5">
          <p className="text-xs text-gray-500 font-medium">Risk:</p>
          {["all", "high", "medium", "low"].map(r => (
            <button
              key={r}
              onClick={() => setRiskFilter(r)}
              className={`text-xs px-3 py-1.5 rounded-full font-semibold border transition-all ${
                riskFilter === r
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}
            >
              {r === "all" ? "All" : r.charAt(0).toUpperCase() + r.slice(1)}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <p className="text-xs text-gray-500 font-medium">Status:</p>
          {["pending", "approved", "dismissed", "all"].map(s => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`text-xs px-3 py-1.5 rounded-full font-semibold border transition-all ${
                statusFilter === s
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="text-center py-10">
          <div className="w-8 h-8 border-4 border-violet-200 border-t-violet-500 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-400">Checking social feeds...</p>
        </div>
      ) : flags.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-2xl border border-gray-100">
          <p className="text-4xl mb-3">✅</p>
          <p className="text-gray-600 font-semibold">No flagged content found</p>
          <p className="text-sm text-gray-400">Social media appears clean for this filter.</p>
        </div>
      ) : (
        <div className="space-y-3">
          <AnimatePresence>
            {flags.map((flag, i) => {
              const cfg = RISK_CONFIG[flag.risk_level];
              const isExpanded = expanded === flag.id;
              const isEditing = editingId === flag.id;

              return (
                <motion.div
                  key={flag.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className={`rounded-2xl border-2 overflow-hidden ${cfg.card}`}
                >
                  {/* Card header */}
                  <button
                    onClick={() => setExpanded(isExpanded ? null : flag.id)}
                    className="w-full flex items-start gap-4 p-4 text-left hover:bg-black/5 transition-colors"
                  >
                    <span className="text-2xl mt-0.5">{cfg.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${cfg.badge}`}>
                          {cfg.label}
                        </span>
                        <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
                          flag.status === "pending" ? "bg-blue-100 text-blue-700 border-blue-200"
                          : flag.status === "approved" ? "bg-emerald-100 text-emerald-700 border-emerald-200"
                          : "bg-gray-100 text-gray-500 border-gray-200"
                        }`}>
                          {flag.status.charAt(0).toUpperCase() + flag.status.slice(1)}
                        </span>
                        <span className="text-xs text-gray-400">
                          {new Date(flag.detected_at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                      <p className="font-bold text-gray-800 text-sm line-clamp-1">{flag.claim}</p>
                    </div>
                    <span className="text-gray-400 text-sm">{isExpanded ? "▲" : "▼"}</span>
                  </button>

                  {/* Expanded content */}
                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: "auto" }}
                        exit={{ height: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="border-t border-current/10 p-4 space-y-4 bg-white/70">
                          {/* Original post */}
                          <div>
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">Original Post</p>
                            <div className="bg-gray-50 border border-gray-200 rounded-xl p-3 text-sm text-gray-700 leading-relaxed italic">
                              "{flag.post_text}"
                            </div>
                          </div>

                          {/* AI Draft Response */}
                          {flag.draft_response && (
                            <div>
                              <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">
                                🤖 AI-drafted Counter-Response
                              </p>
                              {isEditing ? (
                                <textarea
                                  value={editText}
                                  onChange={e => setEditText(e.target.value)}
                                  rows={4}
                                  className="w-full border-2 border-violet-300 rounded-xl p-3 text-sm focus:outline-none focus:border-violet-500 resize-none"
                                  placeholder="Edit the response..."
                                />
                              ) : (
                                <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-sm text-blue-900 leading-relaxed">
                                  {flag.approved_response || flag.draft_response}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Actions */}
                          {flag.status === "pending" && (
                            <div className="flex flex-wrap gap-2 pt-1">
                              {isEditing ? (
                                <>
                                  <button
                                    onClick={() => handleAction(flag.id, "edit")}
                                    disabled={acting === flag.id}
                                    className="flex-1 py-2 bg-emerald-600 text-white text-sm font-bold rounded-xl hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                                  >
                                    ✅ Approve Edited Response
                                  </button>
                                  <button
                                    onClick={() => { setEditingId(null); setEditText(""); }}
                                    className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-semibold rounded-xl hover:bg-gray-200 transition-colors"
                                  >
                                    Cancel
                                  </button>
                                </>
                              ) : (
                                <>
                                  <button
                                    onClick={() => handleAction(flag.id, "approve")}
                                    disabled={acting === flag.id || !flag.draft_response}
                                    className="flex-1 py-2 bg-emerald-600 text-white text-sm font-bold rounded-xl hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                                    id={`approve-flag-${flag.id}`}
                                  >
                                    ✅ Approve & Post
                                  </button>
                                  <button
                                    onClick={() => { setEditingId(flag.id); setEditText(flag.draft_response || ""); }}
                                    className="flex-1 py-2 bg-violet-600 text-white text-sm font-semibold rounded-xl hover:bg-violet-700 transition-colors"
                                  >
                                    ✏️ Edit Response
                                  </button>
                                  <button
                                    onClick={() => handleAction(flag.id, "dismiss")}
                                    disabled={acting === flag.id}
                                    className="px-4 py-2 bg-gray-100 text-gray-600 text-sm font-semibold rounded-xl hover:bg-gray-200 transition-colors"
                                    id={`dismiss-flag-${flag.id}`}
                                  >
                                    Dismiss
                                  </button>
                                </>
                              )}
                            </div>
                          )}

                          {flag.status === "approved" && flag.approved_response && (
                            <div className="flex gap-2">
                              <button
                                onClick={() => {
                                  navigator.clipboard.writeText(flag.approved_response!);
                                  toast.success("Copied to clipboard!");
                                }}
                                className="py-2 px-4 bg-emerald-100 text-emerald-800 text-sm font-semibold rounded-xl hover:bg-emerald-200 transition-colors"
                              >
                                📋 Copy to Clipboard
                              </button>
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
