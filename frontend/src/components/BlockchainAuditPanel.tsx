"use client";

import { useEffect, useState } from "react";
import { blockchainApi } from "@/lib/api";
import toast from "react-hot-toast";

interface AnchorInfo {
    id: string;
    batch_id: string;
    data_hash: string;
    anchor_count: number;
    tx_hash: string | null;
    explorer_url: string | null;
    block_number: number | null;
    status: string;
    anchored_at: string | null;
}

export default function BlockchainAuditPanel() {
    const [anchors, setAnchors] = useState<AnchorInfo[]>([]);
    const [loading, setLoading] = useState(true);
    const [anchoring, setAnchoring] = useState(false);
    const [verifyingId, setVerifyingId] = useState<string | null>(null);

    const loadAnchors = async () => {
        try {
            const res = await blockchainApi.listAnchors(10);
            setAnchors(res.data);
        } catch (e) {
            console.error(e);
            toast.error("Failed to load blockchain history");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadAnchors();
    }, []);

    const handleAnchor = async () => {
        if (anchoring) return;
        setAnchoring(true);
        const toastId = toast.loading("Anchoring pending logs to blockchain...");
        try {
            const res = await blockchainApi.anchorPending();
            if (res.data.status === "no_logs") {
                toast.success("All audit logs are already anchored!", { id: toastId });
            } else {
                toast.success(`Successfully anchored ${res.data.count} logs (Tx: ${res.data.tx_hash.substring(0, 10)}...)`, { id: toastId });
                loadAnchors();
            }
        } catch (e) {
            console.error(e);
            toast.error("Failed to anchor logs", { id: toastId });
        } finally {
            setAnchoring(false);
        }
    };

    const handleVerify = async (batchId: string) => {
        if (verifyingId === batchId) return;
        setVerifyingId(batchId);
        try {
            const res = await blockchainApi.verifyBatch(batchId);
            if (res.data.is_valid) {
                toast.success(`Cryptographic Verification Passed: ${res.data.message}`, { duration: 6000 });
            } else {
                toast.error(`TAMPER DETECTED: ${res.data.message}`, { duration: 8000 });
            }
        } catch (e) {
            console.error(e);
            toast.error("Verification failed");
        } finally {
            setVerifyingId(null);
        }
    };

    if (loading) {
        return <div className="p-4 text-center text-gray-500 text-sm">Loading blockchain ledger...</div>;
    }

    return (
        <div className="flex flex-col h-full">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <span className="text-xl">⛓️</span>
                    <div>
                        <h3 className="font-bold text-gray-800 text-base">Immutable Audit Ledger</h3>
                        <p className="text-xs text-slate-500">Cryptographic proof of civic actions on EVM Blockchain</p>
                    </div>
                </div>
                <button
                    onClick={handleAnchor}
                    disabled={anchoring}
                    className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full border bg-slate-800 text-white hover:bg-slate-700 disabled:opacity-50 transition-colors"
                >
                    {anchoring ? (
                        <><span className="w-3 h-3 border-2 border-slate-400 border-t-white rounded-full animate-spin" /> Anchoring...</>
                    ) : (
                        <>📦 Anchor Pending Logs</>
                    )}
                </button>
            </div>

            <div className="overflow-x-auto border border-gray-100 rounded-xl max-h-[300px] overflow-y-auto">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50 sticky top-0 border-b border-gray-100 z-10">
                        <tr>
                            <th className="text-left px-4 py-3 text-xs text-gray-500 font-semibold w-24">Date</th>
                            <th className="text-left px-4 py-3 text-xs text-gray-500 font-semibold">Data Hash (SHA-256)</th>
                            <th className="text-center px-4 py-3 text-xs text-gray-500 font-semibold w-20">Logs</th>
                            <th className="text-center px-4 py-3 text-xs text-gray-500 font-semibold w-24">Network Tx</th>
                            <th className="text-center px-4 py-3 text-xs text-gray-500 font-semibold w-24">Verify</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                        {anchors.length === 0 ? (
                            <tr>
                                <td colSpan={5} className="py-8 text-center bg-gray-50/50">
                                    <div className="flex flex-col items-center justify-center opacity-60">
                                        <span className="text-3xl mb-2">🧊</span>
                                        <p className="text-sm font-medium text-gray-600">No logs anchored yet</p>
                                        <p className="text-xs text-gray-500 mt-1">Click Anchor above to commit the first batch.</p>
                                    </div>
                                </td>
                            </tr>
                        ) : (
                            anchors.map(a => (
                                <tr key={a.id} className="hover:bg-slate-50/80 transition-colors">
                                    <td className="px-4 py-3 text-xs text-gray-600 whitespace-nowrap">
                                        {a.anchored_at ? new Date(a.anchored_at).toLocaleDateString("en-IN", { month: "short", day: "numeric", hour: '2-digit', minute: '2-digit' }) : "Pending"}
                                    </td>
                                    <td className="px-4 py-3">
                                        <div className="flex items-center gap-2">
                                            <span className="font-mono text-[10px] bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded truncate max-w-[150px] border border-slate-200">
                                                0x{a.data_hash}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-4 py-3 text-center">
                                        <span className="bg-blue-50 text-blue-700 text-xs font-bold px-2 py-0.5 rounded-full border border-blue-100">
                                            {a.anchor_count}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-center">
                                        {a.explorer_url && a.tx_hash ? (
                                            <a href={a.explorer_url} target="_blank" rel="noreferrer" className="text-indigo-600 hover:text-indigo-800 text-[10px] font-mono hover:underline flex flex-col items-center">
                                                <span>Tx: {a.tx_hash.substring(0, 6)}...</span>
                                                <span className="text-[8px] text-gray-400 mt-0.5">Block {a.block_number}</span>
                                            </a>
                                        ) : (
                                            <span className="text-[10px] text-gray-400 italic">Pending</span>
                                        )}
                                    </td>
                                    <td className="px-4 py-3 text-center">
                                        <button
                                            onClick={() => handleVerify(a.batch_id)}
                                            disabled={verifyingId === a.batch_id || a.status !== "confirmed"}
                                            className="text-[10px] font-bold px-2.5 py-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 disabled:opacity-50 transition-colors flex items-center justify-center min-w-[70px] mx-auto"
                                        >
                                            {verifyingId === a.batch_id ? "..." : "Verify"}
                                        </button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
