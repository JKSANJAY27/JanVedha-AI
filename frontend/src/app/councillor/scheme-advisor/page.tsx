"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";
import { schemeAdvisorApi } from "@/lib/api";

type SchemeConfidence = "HIGH" | "MEDIUM" | "LOW";

interface SchemeResult {
    scheme_name: string;
    confidence: SchemeConfidence;
    reason: string;
    documents_required: string[];
    application_process: string;
    contact_office: string;
    financial_benefit: string;
    source_citations: string[];
}

interface AssessmentResponse {
    eligible_schemes: SchemeResult[];
    partial_schemes: SchemeResult[];
    ineligible_schemes: SchemeResult[];
    missing_info: string[];
}

interface QueryHistoryRecord {
    id: string;
    profile: string;
    created_at: string;
    feedback_score: number | null;
    eligible_count: number;
}

export default function SchemeAdvisorPage() {
    const { user, isCouncillor, isAdmin, isSupervisor } = useAuth();
    const router = useRouter();

    const [profileInput, setProfileInput] = useState("");
    const [loading, setLoading] = useState(false);
    
    const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
    const [currentQueryId, setCurrentQueryId] = useState<string | null>(null);
    const [currentTraceId, setCurrentTraceId] = useState<string | null>(null);
    const [feedbackGiven, setFeedbackGiven] = useState<number | null>(null);
    
    const [history, setHistory] = useState<QueryHistoryRecord[]>([]);
    const [historyLoading, setHistoryLoading] = useState(true);

    useEffect(() => {
        const allowed = isCouncillor || isAdmin || isSupervisor;
        if (!user) return;
        if (!allowed) { router.push("/officer/dashboard"); return; }
        loadHistory();
    }, [user]);

    const loadHistory = async () => {
        try {
            const res = await schemeAdvisorApi.getHistory(15, 0);
            setHistory(res.data);
        } catch {
            toast.error("Failed to load query history");
        } finally {
            setHistoryLoading(false);
        }
    };

    const handleQuery = async () => {
        if (!profileInput.trim()) {
            toast.error("Please enter a constituent profile");
            return;
        }

        setLoading(true);
        setAssessment(null);
        setCurrentQueryId(null);
        setCurrentTraceId(null);
        setFeedbackGiven(null);

        try {
            const res = await schemeAdvisorApi.query({
                constituent_profile: profileInput,
                ward_id: user?.ward_id
            });
            setAssessment(res.data.assessment);
            setCurrentQueryId(res.data.query_id);
            setCurrentTraceId(res.data.trace_id);
            loadHistory(); // refresh sidebar silently
        } catch (e: any) {
            toast.error(e.response?.data?.detail || "AI Advisor encountered an error");
        } finally {
            setLoading(false);
        }
    };

    const handleFeedback = async (score: number) => {
        if (!currentQueryId) return;
        setFeedbackGiven(score);
        try {
            await schemeAdvisorApi.submitFeedback(currentQueryId, score);
            toast.success("Feedback submitted. This improves the AI!");
            loadHistory();
        } catch {
            toast.error("Failed to submit feedback");
            setFeedbackGiven(null);
        }
    };
    
    const handleLoadPastQuery = async (id: string) => {
        setLoading(true);
        try {
            const res = await schemeAdvisorApi.getDetails(id);
            setProfileInput(res.data.profile);
            setAssessment(res.data.result);
            setCurrentQueryId(res.data.id);
            setCurrentTraceId(null); // not exposed on raw history endpoint currently
            setFeedbackGiven(res.data.feedback_score);
        } catch {
            toast.error("Failed to load past assessment");
        } finally {
            setLoading(false);
        }
    };

    const SchemeCard = ({ scheme, type }: { scheme: SchemeResult, type: "eligible" | "partial" | "ineligible" }) => {
        const colorMap = {
            eligible: "bg-emerald-50 border-emerald-200 text-emerald-900",
            partial: "bg-amber-50 border-amber-200 text-amber-900",
            ineligible: "bg-rose-50 border-rose-200 text-rose-900",
        };
        const badgeMap = {
            eligible: "bg-emerald-100 text-emerald-700",
            partial: "bg-amber-100 text-amber-700",
            ineligible: "bg-rose-100 text-rose-700",
        };

        return (
            <div className={`p-4 rounded-xl border ${colorMap[type]} shadow-sm`}>
                <div className="flex justify-between items-start mb-2">
                    <h3 className="font-bold text-base">{scheme.scheme_name}</h3>
                    <span className={`text-[10px] font-bold px-2 py-1 rounded border uppercase ${badgeMap[type]}`}>
                        {scheme.confidence} CONFIDENCE
                    </span>
                </div>
                
                <p className="text-sm opacity-90 leading-relaxed mb-3">{scheme.reason}</p>
                
                {scheme.financial_benefit && scheme.financial_benefit !== "Not applicable" && (
                    <div className="mb-3">
                        <span className="text-xs font-bold uppercase tracking-wide opacity-70">Financial Benefit</span>
                        <p className="text-sm font-medium">{scheme.financial_benefit}</p>
                    </div>
                )}
                
                {(type === "eligible" || type === "partial") && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 text-xs">
                        <div className="bg-white/60 p-3 rounded-lg border border-black/5">
                            <span className="font-bold flex items-center gap-1 mb-1">
                                📋 Docs Needed
                            </span>
                            <ul className="list-disc pl-4 space-y-0.5">
                                {scheme.documents_required.slice(0, 4).map((d, i) => (
                                    <li key={i}>{d}</li>
                                ))}
                            </ul>
                        </div>
                        <div className="bg-white/60 p-3 rounded-lg border border-black/5">
                            <span className="font-bold flex items-center gap-1 mb-1">
                                🏢 Application & Contact
                            </span>
                            <p className="line-clamp-2">{scheme.application_process}</p>
                            <p className="mt-1 font-medium">{scheme.contact_office}</p>
                        </div>
                    </div>
                )}
                
                {scheme.source_citations.length > 0 && (
                    <div className="mt-3 text-[10px] opacity-60 flex gap-1 flex-wrap">
                        <span className="font-bold">Citations:</span>
                        {scheme.source_citations.map(c => (
                            <span key={c} className="font-mono bg-black/5 px-1 rounded">{c.split(":")[0]}</span>
                        ))}
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="min-h-screen bg-slate-50 flex flex-col">
            {/* Header */}
            <header className="bg-gradient-to-r from-indigo-700 to-purple-800 text-white px-6 py-5 shadow-sm">
                <div className="max-w-7xl mx-auto flex items-center gap-3">
                    <button 
                        onClick={() => router.push("/dashboard")}
                        className="p-1.5 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                    >
                        ←
                    </button>
                    <div>
                        <h1 className="text-xl font-bold flex items-center gap-2">
                            🏛️ Constituent Scheme Advisor
                            <span className="text-[10px] bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full uppercase tracking-wider font-bold">RAG Powered</span>
                        </h1>
                        <p className="text-xs text-indigo-200 mt-0.5">Instant demographic assessment against State & Central Gov. schemes</p>
                    </div>
                </div>
            </header>

            <div className="flex-1 max-w-7xl mx-auto w-full flex flex-col md:flex-row gap-6 p-4 sm:p-6 h-[calc(100vh-88px)] overflow-hidden">
                
                {/* LEFT Sidebar - Input & History */}
                <div className="w-full md:w-1/3 flex flex-col gap-4 overflow-y-auto pr-2 custom-scrollbar">
                    
                    {/* Input Card */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 shrink-0">
                        <h2 className="font-bold text-gray-800 mb-2">Constituent Profile</h2>
                        <p className="text-xs text-gray-500 mb-3">Type unstructured details about the constituent here. The AI will parse income, age, housing, marital status, and caste.</p>
                        
                        <textarea
                            value={profileInput}
                            onChange={(e) => setProfileInput(e.target.value)}
                            placeholder="e.g. 62 year old widow, no children, BPL family, lives in a hut, SC category, income around Rs. 2000 per month."
                            className="w-full h-32 rounded-xl border border-gray-200 p-3 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-shadow resize-none bg-gray-50"
                        />
                        
                        <button
                            onClick={handleQuery}
                            disabled={loading || !profileInput.trim()}
                            className="w-full mt-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white font-bold py-2.5 rounded-xl text-sm transition-colors flex items-center justify-center gap-2 shadow-sm"
                        >
                            {loading ? (
                                <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Analyzing Knowledge Base...</>
                            ) : (
                                <>🔍 Assess Eligibility</>
                            )}
                        </button>
                    </div>
                    
                    {/* History Sidebar */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 shrink-0 flex-1 flex flex-col min-h-[300px]">
                        <h3 className="text-xs font-bold text-gray-800 uppercase tracking-wider mb-3">Recent Assessments</h3>
                        
                        <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
                            {historyLoading ? (
                                <p className="text-xs text-center text-gray-400 py-4">Loading history...</p>
                            ) : history.length === 0 ? (
                                <p className="text-xs text-center text-gray-400 py-4 italic">No past queries</p>
                            ) : (
                                history.map(h => (
                                    <div 
                                        key={h.id} 
                                        onClick={() => handleLoadPastQuery(h.id)}
                                        className={`p-3 border rounded-xl cursor-pointer transition-all ${
                                            currentQueryId === h.id ? 'border-indigo-300 bg-indigo-50 shadow-sm' : 'border-gray-100 hover:border-gray-300 hover:bg-gray-50'
                                        }`}
                                    >
                                        <p className="text-xs text-gray-700 line-clamp-2 mb-1.5 leading-snug">{h.profile}</p>
                                        <div className="flex items-center justify-between text-[10px]">
                                            <span className="text-gray-400">
                                                {new Date(h.created_at).toLocaleDateString("en-IN", { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'})}
                                            </span>
                                            <span className="font-bold bg-white px-1.5 py-0.5 rounded border border-gray-200 text-emerald-700">
                                                {h.eligible_count} Eligible
                                            </span>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>

                {/* RIGHT Panel - Results */}
                <div className="w-full md:w-2/3 flex flex-col bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                    {!assessment && !loading ? (
                        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-gray-400">
                            <span className="text-6xl mb-4 opacity-50">⚖️</span>
                            <h2 className="text-lg font-bold text-gray-700">Ready to Assess</h2>
                            <p className="text-sm mt-2 max-w-sm">Enter the demographic details of the constituent to instantly cross-reference against state and central welfare schemes.</p>
                        </div>
                    ) : loading ? (
                        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                            <div className="w-12 h-12 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin mb-4" />
                            <p className="font-bold text-gray-700">Retrieving Govt Policies...</p>
                            <p className="text-xs text-gray-500 mt-2">Running Reciprocal Rank Fusion on Vector + Keyword search.</p>
                        </div>
                    ) : (
                        <div className="flex-1 overflow-y-auto p-6 md:p-8 custom-scrollbar">
                            
                            {/* Trace / Dev Info */}
                            {currentTraceId && (
                                <div className="mb-6 bg-slate-50 border border-slate-200 rounded-lg p-3 flex items-center justify-between text-xs">
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold text-slate-700">Langfuse Traced</span>
                                        <span className="font-mono text-[10px] bg-slate-200 text-slate-800 px-1.5 py-0.5 rounded">{currentTraceId.substring(0,8)}...</span>
                                    </div>
                                    <span className="text-emerald-600 font-bold bg-emerald-100 px-2 py-0.5 rounded">Results Verified</span>
                                </div>
                            )}

                            {/* Missing Info Alert */}
                            {assessment?.missing_info && assessment.missing_info.length > 0 && (
                                <div className="mb-8 bg-blue-50 border border-blue-200 rounded-xl p-4 flex gap-3">
                                    <span className="text-xl">ℹ️</span>
                                    <div>
                                        <h4 className="font-bold text-blue-900 text-sm mb-1">Missing Information Discovered</h4>
                                        <p className="text-xs text-blue-800 mb-2">The AI noted that the following details were missing from your profile description, which could affect the assessment:</p>
                                        <ul className="list-disc pl-4 text-xs text-blue-700 space-y-0.5">
                                            {assessment.missing_info.map((info, i) => <li key={i}>{info}</li>)}
                                        </ul>
                                    </div>
                                </div>
                            )}

                            {/* Eligible Schemes */}
                            {assessment?.eligible_schemes && assessment.eligible_schemes.length > 0 && (
                                <div className="mb-8">
                                    <div className="flex items-center gap-2 mb-4 border-b border-gray-100 pb-2">
                                        <span className="text-2xl">🟢</span>
                                        <h2 className="text-xl font-extrabold text-gray-800">Highly Eligible Schemes</h2>
                                        <span className="ml-2 bg-emerald-100 text-emerald-800 font-bold text-xs px-2 py-1 rounded-full">{assessment.eligible_schemes.length}</span>
                                    </div>
                                    <div className="space-y-4">
                                        {assessment.eligible_schemes.map((scheme, i) => (
                                            <SchemeCard key={`el-${i}`} scheme={scheme} type="eligible" />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Partial / Possible Schemes */}
                            {assessment?.partial_schemes && assessment.partial_schemes.length > 0 && (
                                <div className="mb-8">
                                    <div className="flex items-center gap-2 mb-4 border-b border-gray-100 pb-2">
                                        <span className="text-2xl">🟡</span>
                                        <h2 className="text-xl font-extrabold text-gray-800">Possible Matches / Needs Data</h2>
                                        <span className="ml-2 bg-amber-100 text-amber-800 font-bold text-xs px-2 py-1 rounded-full">{assessment.partial_schemes.length}</span>
                                    </div>
                                    <div className="space-y-4">
                                        {assessment.partial_schemes.map((scheme, i) => (
                                            <SchemeCard key={`pa-${i}`} scheme={scheme} type="partial" />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Ineligible */}
                            {assessment?.ineligible_schemes && assessment.ineligible_schemes.length > 0 && (
                                <div className="mb-8">
                                    <div className="flex items-center gap-2 mb-4 border-b border-gray-100 pb-2">
                                        <span className="text-2xl">🔴</span>
                                        <h2 className="text-xl font-extrabold text-gray-800">Not Eligible</h2>
                                    </div>
                                    <div className="space-y-4">
                                        {assessment.ineligible_schemes.map((scheme, i) => (
                                            <SchemeCard key={`in-${i}`} scheme={scheme} type="ineligible" />
                                        ))}
                                    </div>
                                </div>
                            )}
                            
                            {/* Fallback empty states */}
                            {assessment && assessment.eligible_schemes.length === 0 && assessment.partial_schemes.length === 0 && (
                                <div className="text-center py-10 bg-gray-50 rounded-2xl border border-dashed border-gray-200">
                                    <p className="font-bold text-gray-600">No schemes found</p>
                                    <p className="text-sm text-gray-500 mt-1">Based on the provided details, this constituent does not qualify for the schemes in the database.</p>
                                </div>
                            )}

                            {/* Feedback Section */}
                            {assessment && currentQueryId && (
                                <div className="mt-10 pt-6 border-t border-gray-100 flex flex-col items-center justify-center">
                                    <p className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">AI Quality Feedback</p>
                                    <div className="flex items-center gap-4">
                                        <button 
                                            onClick={() => handleFeedback(1)}
                                            disabled={feedbackGiven !== null}
                                            className={`flex items-center justify-center w-12 h-12 rounded-full border-2 transition-all ${
                                                feedbackGiven === 1 
                                                    ? 'bg-emerald-100 border-emerald-500 text-emerald-600 scale-110' 
                                                    : 'bg-white border-gray-200 text-gray-400 hover:border-emerald-300 hover:text-emerald-500'
                                            } ${feedbackGiven !== null && feedbackGiven !== 1 ? 'opacity-30' : ''}`}
                                        >
                                            👍
                                        </button>
                                        <button 
                                            onClick={() => handleFeedback(0)}
                                            disabled={feedbackGiven !== null}
                                            className={`flex items-center justify-center w-12 h-12 rounded-full border-2 transition-all ${
                                                feedbackGiven === 0
                                                    ? 'bg-rose-100 border-rose-500 text-rose-600 scale-110' 
                                                    : 'bg-white border-gray-200 text-gray-400 hover:border-rose-300 hover:text-rose-500'
                                            } ${feedbackGiven !== null && feedbackGiven !== 0 ? 'opacity-30' : ''}`}
                                        >
                                            👎
                                        </button>
                                    </div>
                                    {feedbackGiven !== null && (
                                        <p className="text-xs text-indigo-500 font-medium mt-3">✅ Registered to Langfuse. Thanks!</p>
                                    )}
                                </div>
                            )}

                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
