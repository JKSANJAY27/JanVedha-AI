"use client";

import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { trustApi } from "@/lib/api";

interface ResolveWithProofModalProps {
  ticketId: string;
  ticketCode: string;
  issueType: string;
  technicianId: string;
  onSuccess: (result: VerificationResult) => void;
  onClose: () => void;
}

interface VerificationResult {
  verified: boolean | null;
  confidence: "high" | "medium" | "low";
  verification_statement: string;
  concerns: string | null;
}

export default function ResolveWithProofModal({
  ticketId,
  ticketCode,
  issueType,
  technicianId,
  onSuccess,
  onClose,
}: ResolveWithProofModalProps) {
  const [photo, setPhoto] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [verificationResult, setVerificationResult] = useState<VerificationResult | null>(null);
  const [step, setStep] = useState<"upload" | "verifying" | "result">("upload");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Please upload an image file.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error("File too large. Maximum 10 MB.");
      return;
    }
    setPhoto(file);
    const reader = new FileReader();
    reader.onloadend = () => setPreview(reader.result as string);
    reader.readAsDataURL(file);
  };

  const handleSubmit = async () => {
    if (!photo) {
      toast.error("Please select a proof photo first.");
      return;
    }
    setUploading(true);
    setStep("verifying");

    try {
      const formData = new FormData();
      formData.append("photo", photo);
      formData.append("technician_id", technicianId);

      const res = await trustApi.resolveWithProof(ticketId, formData);
      const result: VerificationResult = res.data.gemini_verification;
      setVerificationResult(result);
      setStep("result");
      onSuccess(result);
      toast.success("Work proof submitted & verified by AI!");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to submit proof.";
      toast.error(message);
      setStep("upload");
    } finally {
      setUploading(false);
    }
  };

  const confidenceConfig = {
    high: { color: "text-emerald-600", bg: "bg-emerald-50 border-emerald-200", icon: "✅", label: "High Confidence" },
    medium: { color: "text-amber-600", bg: "bg-amber-50 border-amber-200", icon: "⚠️", label: "Medium Confidence" },
    low: { color: "text-red-600", bg: "bg-red-50 border-red-200", icon: "🔍", label: "Low Confidence — Review Required" },
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          className="bg-white rounded-3xl shadow-2xl w-full max-w-lg overflow-hidden"
        >
          {/* Header */}
          {/* Header */}
          <div className={`px-6 py-5 text-white ${step === "result" && verificationResult?.verified === false ? "bg-gradient-to-r from-red-600 to-rose-600" : "bg-gradient-to-r from-emerald-600 to-teal-600"}`}>
            <div className="flex items-center justify-between">
              <div>
                <p className={`${step === "result" && verificationResult?.verified === false ? "text-red-200" : "text-emerald-200"} text-xs font-semibold uppercase tracking-widest mb-1`}>
                  {step === "result" && verificationResult?.verified === false ? "AI Verification Failed" : "AI-Verified Resolution"}
                </p>
                <h2 className="text-xl font-extrabold">{step === "result" && verificationResult?.verified === false ? "Proof Rejected" : "Mark as Resolved"}</h2>
                <p className={`${step === "result" && verificationResult?.verified === false ? "text-red-200" : "text-emerald-200"} text-sm mt-0.5`}>
                  {ticketCode} · {issueType}
                </p>
              </div>
              <div className="w-12 h-12 bg-white/20 rounded-2xl flex items-center justify-center text-2xl">
                {step === "result" && verificationResult?.verified === false ? "❌" : "📸"}
              </div>
            </div>
          </div>

          <div className="p-6 space-y-5">
            {/* Step: Upload */}
            {step === "upload" && (
              <>
                <div className="text-sm text-gray-600 bg-blue-50 border border-blue-200 rounded-2xl p-4">
                  <p className="font-semibold text-blue-800 mb-1">📋 How it works</p>
                  <p>Upload a clear photo of the completed work. Gemini AI will analyze it and generate an official verification statement.</p>
                </div>

                {/* Drop zone */}
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-2xl cursor-pointer transition-all duration-200 flex flex-col items-center justify-center py-10 px-6 text-center
                    ${preview ? "border-emerald-400 bg-emerald-50" : "border-gray-300 bg-gray-50 hover:border-emerald-400 hover:bg-emerald-50"}`}
                >
                  {preview ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img src={preview} alt="Proof preview" className="max-h-48 rounded-xl object-cover shadow-md" />
                  ) : (
                    <>
                      <span className="text-5xl mb-3">📷</span>
                      <p className="font-semibold text-gray-700">Click to upload proof photo</p>
                      <p className="text-xs text-gray-400 mt-1">JPG, PNG — max 10 MB</p>
                    </>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileSelect}
                  className="hidden"
                />

                {photo && (
                  <p className="text-sm text-emerald-700 font-medium flex items-center gap-2">
                    <span>✅</span> {photo.name} selected ({(photo.size / 1024).toFixed(0)} KB)
                  </p>
                )}

                <div className="flex gap-3 pt-2">
                  <button
                    onClick={onClose}
                    className="flex-1 py-3 rounded-2xl border border-gray-200 text-gray-600 font-semibold hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                     onClick={handleSubmit}
                     disabled={!photo || uploading}
                     className="flex-1 py-3 rounded-2xl bg-emerald-600 text-white font-bold hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                     id="resolve-submit-btn"
                  >
                    {uploading ? "Submitting..." : "Submit & Verify with AI →"}
                  </button>
                </div>
              </>
            )}

            {/* Step: Verifying */}
            {step === "verifying" && (
              <div className="flex flex-col items-center py-10 gap-5">
                <div className="relative w-20 h-20">
                  <div className="absolute inset-0 rounded-full border-4 border-emerald-200" />
                  <div className="absolute inset-0 rounded-full border-4 border-emerald-500 border-t-transparent animate-spin" />
                  <div className="absolute inset-0 flex items-center justify-center text-2xl">🤖</div>
                </div>
                <div className="text-center">
                  <p className="font-extrabold text-gray-800 text-lg">Gemini is verifying...</p>
                  <p className="text-gray-500 text-sm mt-1">Analyzing your photo against the reported issue</p>
                </div>
              </div>
            )}

            {/* Step: Result */}
            {step === "result" && verificationResult && (
              <>
                <div className={`rounded-2xl border-2 p-5 ${confidenceConfig[verificationResult.confidence]?.bg}`}>
                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-3xl">{verificationResult.verified === false ? "❌" : confidenceConfig[verificationResult.confidence]?.icon}</span>
                    <div>
                      <p className={`font-extrabold text-lg ${verificationResult.verified === false ? "text-red-700" : confidenceConfig[verificationResult.confidence]?.color}`}>
                        {verificationResult.verified === true ? "Work Verified!" : verificationResult.verified === false ? "Verification Failed" : "Verification Inconclusive"}
                      </p>
                      <p className={`text-sm font-semibold ${verificationResult.verified === false ? "text-red-600" : confidenceConfig[verificationResult.confidence]?.color}`}>
                        {confidenceConfig[verificationResult.confidence]?.label}
                      </p>
                    </div>
                  </div>
                  <p className="text-gray-700 text-sm leading-relaxed">
                    {verificationResult.verification_statement}
                  </p>
                  {verificationResult.concerns && (
                    <div className="mt-3 p-3 bg-white/60 rounded-xl">
                      <p className="text-xs font-bold text-gray-600 mb-1">⚠️ Concerns noted:</p>
                      <p className="text-xs text-gray-600">{verificationResult.concerns}</p>
                    </div>
                  )}
                </div>

                {verificationResult.verified === false ? (
                  <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-sm text-red-800">
                    ❌ Ticket status has been updated to <strong>Rejected</strong> and sent back to the technician.
                  </div>
                ) : (
                  <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4 text-sm text-emerald-800">
                    ✅ Ticket status has been updated to <strong>Closed</strong> and the proof is now visible to the citizen and councillor.
                  </div>
                )}

                <button
                  onClick={onClose}
                  className={`w-full py-3 rounded-2xl text-white font-bold transition-colors ${
                    verificationResult.verified === false ? "bg-red-600 hover:bg-red-700" : "bg-emerald-600 hover:bg-emerald-700"
                  }`}
                >
                  Done
                </button>
              </>
            )}
          </div>

        </motion.div>
      </div>
    </AnimatePresence>
  );
}
