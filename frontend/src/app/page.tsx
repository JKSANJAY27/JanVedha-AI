"use client";

import { useState, useRef, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { publicApi } from "@/lib/api";
import { formatDate } from "@/lib/formatters";
import PriorityBadge from "@/components/PriorityBadge";
import LoadingOverlay from "@/components/LoadingOverlay";
import Link from "next/link";
import { DEPT_NAMES } from "@/lib/constants";

const schema = z.object({
  description: z.string().min(20, "Describe the issue in at least 20 characters"),
  location_text: z.string().min(5, "Please enter location"),
  reporter_phone: z.string().regex(/^[6-9]\d{9}$/, "Enter valid 10-digit Indian mobile number"),
  reporter_name: z.string().optional(),
  consent_given: z.boolean().refine((v) => v === true, "You must consent to share info"),
});

type FormData = z.infer<typeof schema>;

interface TicketResult {
  ticket_code: string;
  status: string;
  dept_id: string;
  priority_label: string;
  priority_score: number;
  sla_deadline: string;
  ai_routing_reason?: string;
  suggestions?: string[];
  seasonal_alert?: string;
}

// AI processing steps with timing
const AI_STEPS = [
  "🧠 Analyzing your description…",
  "🗺️ Detecting location & ward…",
  "🏛️ Routing to department…",
  "⚡ Calculating priority score…",
  "✅ Finalizing your ticket…",
];

export default function SubmitComplaintPage() {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [aiStep, setAiStep] = useState(0);
  const [result, setResult] = useState<TicketResult | null>(null);
  const [locationLoading, setLocationLoading] = useState(false);
  const locationRef = useRef<HTMLInputElement | null>(null);

  const { ref: locationFormRef, ...locationRegister } = register("location_text");

  const combineRef = (el: HTMLInputElement | null) => {
    locationRef.current = el;
    locationFormRef(el);
  };

  const detectLocation = () => {
    if (!navigator.geolocation) {
      toast.error("Geolocation not supported");
      return;
    }
    setLocationLoading(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`
          );
          const data = await res.json();
          const addr = data.display_name || `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
          if (locationRef.current) locationRef.current.value = addr;
        } catch {
          if (locationRef.current)
            locationRef.current.value = `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
        }
        setLocationLoading(false);
      },
      () => {
        toast.error("Location access denied. Please enter manually.");
        setLocationLoading(false);
      }
    );
  };

  const onPhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhoto(file);
    const reader = new FileReader();
    reader.onload = (ev) => setPhotoPreview(ev.target?.result as string);
    reader.readAsDataURL(file);
  };

  // Simulate progressive AI steps
  useEffect(() => {
    if (!isSubmitting) return;
    setAiStep(0);
    const intervals = AI_STEPS.map((_, i) =>
      setTimeout(() => setAiStep(i), i * 800)
    );
    return () => intervals.forEach(clearTimeout);
  }, [isSubmitting]);

  const onSubmit = async (data: FormData) => {
    setIsSubmitting(true);
    setResult(null);

    const formData = new FormData();
    formData.append("description", data.description);
    formData.append("location_text", data.location_text);
    formData.append("reporter_phone", data.reporter_phone);
    formData.append("consent_given", "true");
    if (data.reporter_name) formData.append("reporter_name", data.reporter_name);
    if (photo) formData.append("photo", photo);

    // Also need to send as JSON since backend uses JSON body
    const jsonData = {
      description: data.description,
      location_text: data.location_text,
      reporter_phone: data.reporter_phone,
      consent_given: true,
      reporter_name: data.reporter_name || null,
      photo_url: null,
    };

    try {
      await new Promise((r) => setTimeout(r, AI_STEPS.length * 800 + 500));
      const res = await publicApi.submitComplaint(JSON.stringify(jsonData) as any);
      setResult(res.data);
      toast.success("Complaint submitted successfully!");
      reset();
      setPhoto(null);
      setPhotoPreview(null);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Submission failed. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleJsonSubmit = async (data: FormData) => {
    setIsSubmitting(true);
    setResult(null);

    const jsonData = {
      description: data.description,
      location_text: data.location_text,
      reporter_phone: data.reporter_phone,
      consent_given: true,
      reporter_name: data.reporter_name || null,
      photo_url: null,
    };

    try {
      // Wait for animation
      await new Promise((r) => setTimeout(r, AI_STEPS.length * 850 + 500));
      const res = await publicApi.submitComplaint(jsonData as any);
      setResult(res.data);
      toast.success("Complaint submitted successfully!");
      reset();
      setPhoto(null);
      setPhotoPreview(null);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Submission failed. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 via-white to-slate-50">
      {/* Hero */}
      <section className="bg-gradient-to-br from-blue-700 via-blue-800 to-indigo-900 text-white py-16 px-4">
        <div className="max-w-3xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="inline-flex items-center gap-2 bg-white/10 rounded-full px-4 py-1.5 mb-5 text-sm font-medium backdrop-blur-sm border border-white/20">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              AI-Powered Civic Management
            </div>
            <h1 className="text-4xl md:text-5xl font-extrabold mb-4 leading-tight">
              Report a Civic Issue
            </h1>
            <p className="text-blue-200 text-lg max-w-xl mx-auto">
              Submit your complaint and our AI pipeline will instantly classify, prioritize, and route it to the right department.
            </p>
          </motion.div>
        </div>
      </section>

      <div className="max-w-2xl mx-auto px-4 py-10">
        <AnimatePresence mode="wait">
          {result ? (
            <motion.div
              key="success"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="bg-white rounded-3xl shadow-xl p-8 border border-green-100"
            >
              <div className="text-center mb-6">
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center text-3xl mx-auto mb-4">
                  ✅
                </div>
                <h2 className="text-2xl font-bold text-gray-900">Ticket Created!</h2>
                <p className="text-gray-500 mt-1">Your complaint has been processed by our AI pipeline</p>
              </div>

              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl p-5 mb-5 text-center">
                <p className="text-xs text-gray-500 mb-1">Your Ticket Code</p>
                <p className="text-3xl font-mono font-extrabold text-blue-700 tracking-wider">
                  {result.ticket_code}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-5">
                <div className="bg-gray-50 rounded-xl p-3">
                  <p className="text-xs text-gray-500 mb-1">Department</p>
                  <p className="font-semibold text-gray-800 text-sm">
                    {DEPT_NAMES[result.dept_id] ?? result.dept_id}
                  </p>
                </div>
                <div className="bg-gray-50 rounded-xl p-3">
                  <p className="text-xs text-gray-500 mb-1">Priority</p>
                  <PriorityBadge label={result.priority_label} score={result.priority_score} />
                </div>
                <div className="bg-gray-50 rounded-xl p-3">
                  <p className="text-xs text-gray-500 mb-1">SLA Deadline</p>
                  <p className="font-medium text-gray-800 text-sm">{formatDate(result.sla_deadline)}</p>
                </div>
                <div className="bg-gray-50 rounded-xl p-3">
                  <p className="text-xs text-gray-500 mb-1">Status</p>
                  <p className="font-medium text-blue-700 text-sm">{result.status}</p>
                </div>
              </div>

              {result.ai_routing_reason && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4">
                  <p className="text-xs font-medium text-amber-700 mb-1">🤖 AI Routing Reason</p>
                  <p className="text-sm text-amber-800">{result.ai_routing_reason}</p>
                </div>
              )}

              {result.suggestions && result.suggestions.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs font-medium text-gray-500 mb-2">💡 AI Suggestions</p>
                  <ul className="space-y-1.5">
                    {result.suggestions.map((s, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                        <span className="text-blue-500 mt-0.5">•</span> {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {result.seasonal_alert && (
                <div className="bg-orange-50 border border-orange-200 rounded-xl p-3 mb-4 text-sm text-orange-800">
                  🌤️ <strong>Seasonal Alert:</strong> {result.seasonal_alert}
                </div>
              )}

              <div className="flex gap-3 mt-5">
                <Link
                  href={`/track/${result.ticket_code}`}
                  className="flex-1 text-center bg-blue-600 text-white rounded-xl py-3 font-semibold hover:bg-blue-700 transition-colors"
                >
                  Track My Ticket →
                </Link>
                <button
                  onClick={() => setResult(null)}
                  className="flex-1 text-center border border-gray-200 text-gray-600 rounded-xl py-3 font-semibold hover:bg-gray-50 transition-colors"
                >
                  Submit Another
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="form"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="bg-white rounded-3xl shadow-xl p-8 border border-gray-100"
            >
              <h2 className="text-xl font-bold text-gray-900 mb-6">Submit a Complaint</h2>

              <form onSubmit={handleSubmit(handleJsonSubmit)} className="space-y-5">
                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Issue Description <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    {...register("description")}
                    rows={4}
                    placeholder="Describe the civic issue in detail (e.g., broken streetlight near St. Mary's School gate)…"
                    className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none placeholder:text-gray-400"
                  />
                  {errors.description && (
                    <p className="text-red-500 text-xs mt-1">{errors.description.message}</p>
                  )}
                </div>

                {/* Photo upload */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Photo Evidence (optional)
                  </label>
                  <div className="flex items-center gap-4">
                    <label className="flex-1 cursor-pointer border-2 border-dashed border-gray-200 rounded-xl p-4 text-center hover:border-blue-400 hover:bg-blue-50 transition-all">
                      <span className="text-2xl block mb-1">📷</span>
                      <span className="text-sm text-gray-500">
                        {photo ? photo.name : "Click to upload photo"}
                      </span>
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={onPhotoChange}
                      />
                    </label>
                    {photoPreview && (
                      <div className="relative">
                        <img
                          src={photoPreview}
                          alt="Preview"
                          className="w-20 h-20 object-cover rounded-xl border border-gray-200"
                        />
                        <button
                          type="button"
                          onClick={() => { setPhoto(null); setPhotoPreview(null); }}
                          className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full text-xs flex items-center justify-center"
                        >
                          ✕
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Location */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Location <span className="text-red-500">*</span>
                  </label>
                  <div className="flex gap-2">
                    <input
                      {...locationRegister}
                      ref={combineRef}
                      type="text"
                      placeholder="Enter address or use GPS…"
                      className="flex-1 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <button
                      type="button"
                      onClick={detectLocation}
                      disabled={locationLoading}
                      className="px-4 py-3 bg-blue-50 border border-blue-200 text-blue-600 rounded-xl text-sm font-medium hover:bg-blue-100 transition-colors disabled:opacity-50 flex items-center gap-1.5"
                    >
                      {locationLoading ? (
                        <span className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                      ) : (
                        "📍 GPS"
                      )}
                    </button>
                  </div>
                  {errors.location_text && (
                    <p className="text-red-500 text-xs mt-1">{errors.location_text.message}</p>
                  )}
                </div>

                {/* Name + Phone row */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Your Name (optional)
                    </label>
                    <input
                      {...register("reporter_name")}
                      type="text"
                      placeholder="Full name"
                      className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Mobile Number <span className="text-red-500">*</span>
                    </label>
                    <input
                      {...register("reporter_phone")}
                      type="tel"
                      placeholder="10-digit number"
                      className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    {errors.reporter_phone && (
                      <p className="text-red-500 text-xs mt-1">{errors.reporter_phone.message}</p>
                    )}
                  </div>
                </div>

                {/* Consent */}
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    {...register("consent_given")}
                    type="checkbox"
                    className="w-4 h-4 mt-0.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-600">
                    I consent to share my contact information with the municipal authority for complaint resolution
                  </span>
                </label>
                {errors.consent_given && (
                  <p className="text-red-500 text-xs -mt-3">{errors.consent_given.message}</p>
                )}

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full bg-gradient-to-r from-blue-600 to-indigo-700 text-white rounded-xl py-4 font-bold text-base hover:shadow-lg hover:scale-[1.01] transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100 flex items-center justify-center gap-2"
                >
                  {isSubmitting ? (
                    <>
                      <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Processing…
                    </>
                  ) : (
                    <>🚀 Submit Complaint</>
                  )}
                </button>

                <p className="text-xs text-gray-400 text-center">
                  Powered by AI — your complaint will be routed in seconds
                </p>
              </form>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Info cards */}
        <div className="grid grid-cols-3 gap-4 mt-8">
          {[
            { icon: "🤖", title: "AI-Powered", desc: "Instant classification & routing" },
            { icon: "📍", title: "GPS Tracking", desc: "Pinpoint issue location" },
            { icon: "⚡", title: "Real-time", desc: "Track status live" },
          ].map((c) => (
            <div key={c.title} className="bg-white rounded-2xl p-4 text-center shadow-sm border border-gray-100">
              <div className="text-2xl mb-2">{c.icon}</div>
              <p className="text-sm font-semibold text-gray-800">{c.title}</p>
              <p className="text-xs text-gray-500 mt-0.5">{c.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <LoadingOverlay visible={isSubmitting} steps={AI_STEPS} currentStep={aiStep} />
    </div>
  );
}
