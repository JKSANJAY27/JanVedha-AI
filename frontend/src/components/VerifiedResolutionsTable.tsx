"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { trustApi } from "@/lib/api";

interface VerifiedResolution {
  id: string;
  ticket_code: string;
  issue_type: string;
  area: string;
  ward_id: number;
  technician_id: string | null;
  verification_statement: string | null;
  confidence: "high" | "medium" | "low";
  verified: boolean | null;
  after_photo_url: string | null;
  resolved_at: string | null;
  needs_review: boolean;
}

interface Props {
  wardId?: number;
}

const CONF_CONFIG = {
  high: {
    badge: "bg-emerald-100 text-emerald-800 border-emerald-200",
    row: "",
    icon: "✅",
  },
  medium: {
    badge: "bg-amber-100 text-amber-800 border-amber-200",
    row: "",
    icon: "⚠️",
  },
  low: {
    badge: "bg-red-100 text-red-800 border-red-200",
    row: "bg-amber-50 border-l-4 border-l-amber-400",
    icon: "🔍",
  },
};

export default function VerifiedResolutionsTable({ wardId }: Props) {
  const [items, setItems] = useState<VerifiedResolution[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewPhoto, setPreviewPhoto] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "needs_review">("all");

  useEffect(() => {
    trustApi.getVerifiedResolutions(wardId, 100)
      .then(res => setItems(res.data))
      .catch(() => toast.error("Failed to load verified resolutions"))
      .finally(() => setLoading(false));
  }, [wardId]);

  const displayed = filter === "needs_review"
    ? items.filter(i => i.needs_review)
    : items;

  const reviewCount = items.filter(i => i.needs_review).length;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="font-extrabold text-gray-900 text-lg flex items-center gap-2">
            🛡️ Verified Resolutions
          </h3>
          <p className="text-sm text-gray-500">AI-verified work proof for closed tickets</p>
        </div>
        <div className="flex items-center gap-2">
          {reviewCount > 0 && (
            <span className="bg-amber-100 text-amber-800 text-xs font-bold px-3 py-1 rounded-full border border-amber-200">
              ⚠️ {reviewCount} needs review
            </span>
          )}
          <div className="flex rounded-xl overflow-hidden border border-gray-200">
            {(["all", "needs_review"] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`text-xs px-3 py-2 font-semibold transition-colors ${
                  filter === f ? "bg-gray-900 text-white" : "bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                {f === "all" ? "All Verified" : "Needs Review"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-10">
          <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-400">Loading...</p>
        </div>
      ) : displayed.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-2xl border border-gray-100">
          <p className="text-3xl mb-2">🎯</p>
          <p className="text-gray-500 font-medium">No verified resolutions yet</p>
          <p className="text-sm text-gray-400">They'll appear when technicians submit proof photos.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-gray-200 shadow-sm">
          <table className="min-w-full divide-y divide-gray-100 text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs font-semibold uppercase tracking-wide">
              <tr>
                <th className="px-4 py-3 text-left">Ticket</th>
                <th className="px-4 py-3 text-left">Issue</th>
                <th className="px-4 py-3 text-left">Area</th>
                <th className="px-4 py-3 text-left">Technician</th>
                <th className="px-4 py-3 text-left">AI Verdict</th>
                <th className="px-4 py-3 text-left">Confidence</th>
                <th className="px-4 py-3 text-left">Photo</th>
                <th className="px-4 py-3 text-left">Resolved</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 bg-white">
              {displayed.map((item, i) => {
                const conf = CONF_CONFIG[item.confidence];
                return (
                  <motion.tr
                    key={item.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.03 }}
                    className={`transition-colors hover:bg-gray-50 ${conf.row}`}
                  >
                    <td className="px-4 py-3 font-mono font-bold text-blue-600 whitespace-nowrap">
                      {item.ticket_code}
                    </td>
                    <td className="px-4 py-3 font-medium text-gray-800 max-w-[120px] truncate">
                      {item.issue_type}
                    </td>
                    <td className="px-4 py-3 text-gray-500 max-w-[120px] truncate">
                      {item.area}
                    </td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                      {item.technician_id ? `…${item.technician_id.slice(-6)}` : <span className="italic text-gray-300">N/A</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-700 max-w-[200px]">
                      <p className="text-xs leading-snug line-clamp-2">
                        {item.verification_statement || <span className="italic text-gray-400">No statement</span>}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border ${conf.badge}`}>
                        {conf.icon} {item.confidence.charAt(0).toUpperCase() + item.confidence.slice(1)}
                      </span>
                      {item.needs_review && (
                        <p className="text-[10px] text-amber-600 font-semibold mt-1">Needs Review</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {item.after_photo_url ? (
                        <button
                          onClick={() => setPreviewPhoto(item.after_photo_url)}
                          className="w-10 h-10 rounded-xl overflow-hidden border-2 border-gray-200 hover:border-blue-400 transition-colors"
                        >
                          <img
                            src={item.after_photo_url}
                            alt="proof"
                            className="w-full h-full object-cover"
                          />
                        </button>
                      ) : <span className="text-gray-300 text-xs italic">No photo</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                      {item.resolved_at
                        ? new Date(item.resolved_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
                        : "—"}
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Photo Preview Modal */}
      {previewPhoto && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          onClick={() => setPreviewPhoto(null)}
        >
          <motion.div
            initial={{ scale: 0.85, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="max-w-2xl w-full"
            onClick={e => e.stopPropagation()}
          >
            <img
              src={previewPhoto}
              alt="Proof photo"
              className="w-full rounded-3xl shadow-2xl border-4 border-white/20"
            />
            <button
              onClick={() => setPreviewPhoto(null)}
              className="mt-4 w-full py-2.5 rounded-2xl bg-white/20 text-white font-semibold hover:bg-white/30 transition-colors"
            >
              Close ✕
            </button>
          </motion.div>
        </div>
      )}
    </div>
  );
}
