"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface LoadingOverlayProps {
    visible: boolean;
    steps?: string[];
    currentStep?: number;
}

const DEFAULT_STEPS = [
    "🧠 Analyzing your description...",
    "🗺️ Detecting location & ward...",
    "🏛️ Routing to department...",
    "⚡ Calculating priority score...",
    "✅ Finalizing your ticket...",
];

export default function LoadingOverlay({
    visible,
    steps = DEFAULT_STEPS,
    currentStep = 0,
}: LoadingOverlayProps) {
    return (
        <AnimatePresence>
            {visible && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
                >
                    <motion.div
                        initial={{ scale: 0.9, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0.9, opacity: 0 }}
                        className="bg-white rounded-3xl p-8 max-w-sm w-full mx-4 shadow-2xl"
                    >
                        <div className="flex flex-col items-center gap-6">
                            <div className="relative w-16 h-16">
                                <div className="absolute inset-0 rounded-full border-4 border-blue-100" />
                                <div className="absolute inset-0 rounded-full border-4 border-blue-500 border-t-transparent animate-spin" />
                                <div className="absolute inset-2 rounded-full bg-blue-50 flex items-center justify-center text-2xl">
                                    AI
                                </div>
                            </div>

                            <div className="text-center">
                                <h3 className="text-lg font-bold text-gray-900 mb-1">
                                    AI Pipeline Running
                                </h3>
                                <p className="text-sm text-gray-500">
                                    Please wait while we process your complaint
                                </p>
                            </div>

                            <div className="w-full space-y-2">
                                {steps.map((step, i) => (
                                    <div
                                        key={i}
                                        className={`flex items-center gap-3 text-sm transition-all duration-300 ${i < currentStep
                                                ? "text-green-600 opacity-60"
                                                : i === currentStep
                                                    ? "text-blue-700 font-medium"
                                                    : "text-gray-300"
                                            }`}
                                    >
                                        <span className="w-5 h-5 flex-shrink-0">
                                            {i < currentStep ? "✅" : i === currentStep ? "⏳" : "○"}
                                        </span>
                                        {step}
                                    </div>
                                ))}
                            </div>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
