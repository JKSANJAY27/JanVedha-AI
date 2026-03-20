"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import { proposalsApi } from "@/lib/api";

interface Proposal {
  proposal_id: string;
  title: string;
  development_type: string;
  estimated_cost: number;
  total_complaints_evidence: number;
  created_at: string;
  status: string;
}

const TYPE_ICONS: Record<string, string> = {
  road_resurfacing: "🛣️",
  streetlight_installation: "💡",
  drainage_improvement: "🌊",
  park_open_space: "🌳",
  water_pipeline: "🚰",
  waste_collection_point: "♻️",
  community_center: "🏛️",
};

export default function ProposalsListPage() {
  const { user, isCouncillor, isAdmin, isSupervisor } = useAuth();
  const router = useRouter();
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const allowed = isCouncillor || isAdmin || isSupervisor;
    if (!user) return;
    if (!allowed) { router.push("/officer/dashboard"); return; }

    proposalsApi.list(user.ward_id)
      .then((r) => setProposals(r.data ?? []))
      .catch(() => setProposals([]))
      .finally(() => setLoading(false));
  }, [user]);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-emerald-700 to-teal-800 text-white px-6 py-5">
        <div className="max-w-4xl mx-auto flex items-center gap-4 flex-wrap">
          <div>
            <p className="text-emerald-300 text-sm">Development · Ward {user?.ward_id}</p>
            <h1 className="text-xl font-bold mt-0.5">Past Proposals 📋</h1>
            <p className="text-emerald-200 text-xs mt-0.5">AI-generated ward development proposals</p>
          </div>
          <div className="ml-auto flex gap-3">
            <a
              href="/councillor/proposal"
              className="text-xs font-bold px-4 py-2 rounded-lg bg-white text-emerald-800 hover:bg-emerald-50 transition-colors"
            >
              + New Proposal
            </a>
            <a href="/dashboard" className="text-xs text-emerald-300 hover:text-white underline self-center">
              ← Dashboard
            </a>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-8">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-48">
            <div className="w-10 h-10 border-4 border-emerald-200 border-t-emerald-600 rounded-full animate-spin mb-3" />
            <p className="text-gray-500 text-sm">Loading proposals…</p>
          </div>
        ) : proposals.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 bg-white rounded-2xl border border-dashed border-gray-200">
            <span className="text-4xl mb-4">📄</span>
            <p className="text-gray-600 font-semibold">No proposals yet</p>
            <p className="text-gray-400 text-sm mt-1 mb-4">Generate your first proposal using the Opportunity Spotter</p>
            <a
              href="/councillor/opportunity"
              className="text-xs font-bold px-4 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
            >
              Open Opportunity Map →
            </a>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-gray-500 font-medium">
              {proposals.length} proposal{proposals.length !== 1 ? "s" : ""} for Ward {user?.ward_id}
            </p>
            {proposals.map((p, idx) => {
              const typeIcon = TYPE_ICONS[p.development_type] ?? "🏗️";
              const typeLabel = p.development_type.replace(/_/g, " ");

              return (
                <motion.div
                  key={p.proposal_id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col sm:flex-row sm:items-center gap-4"
                >
                  {/* Icon */}
                  <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center text-2xl shrink-0">
                    {typeIcon}
                  </div>

                  {/* Details */}
                  <div className="flex-1 min-w-0">
                    <p className="font-bold text-gray-800 text-sm line-clamp-2">{p.title}</p>
                    <div className="flex items-center gap-3 flex-wrap mt-1">
                      <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full capitalize">
                        {typeLabel}
                      </span>
                      {p.estimated_cost && (
                        <span className="text-xs text-gray-500">
                          ₹{(p.estimated_cost / 100000).toFixed(1)}L
                        </span>
                      )}
                      <span className="text-xs text-gray-400">
                        {p.total_complaints_evidence} complaints backed
                      </span>
                      <span className="text-xs text-gray-400">
                        {new Date(p.created_at).toLocaleDateString("en-IN", {
                          day: "2-digit", month: "short", year: "numeric",
                        })}
                      </span>
                    </div>
                  </div>

                  {/* Status + View button */}
                  <div className="flex items-center gap-3 shrink-0">
                    <span
                      className={`text-[10px] font-bold px-2 py-1 rounded-lg capitalize ${
                        p.status === "approved"
                          ? "bg-green-100 text-green-700"
                          : p.status === "submitted"
                          ? "bg-blue-100 text-blue-700"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {p.status}
                    </span>
                    <a
                      href={`/councillor/proposal?view=${p.proposal_id}`}
                      className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
                    >
                      View
                    </a>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
