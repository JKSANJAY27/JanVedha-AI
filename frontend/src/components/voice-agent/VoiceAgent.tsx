"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import { voiceAgentApi } from "@/lib/api";

interface ConversationItem {
    id: string;
    role: "user" | "agent";
    text: string;
    timestamp: Date;
}

type AgentState = "idle" | "recording" | "processing" | "speaking";

const LANGUAGES = [
    { code: "en-IN", name: "English",   native: "Eng",    short: "EN" },
    { code: "hi-IN", name: "Hindi",     native: "हिंदी",    short: "HI" },
    { code: "ta-IN", name: "Tamil",     native: "தமிழ்",    short: "TA" },
    { code: "te-IN", name: "Telugu",    native: "తెలుగు",   short: "TE" },
    { code: "kn-IN", name: "Kannada",   native: "ಕನ್ನಡ",    short: "KN" },
    { code: "ml-IN", name: "Malayalam", native: "മലയാളം",  short: "ML" },
    { code: "bn-IN", name: "Bengali",   native: "বাংলা",    short: "BN" },
    { code: "gu-IN", name: "Gujarati",  native: "ગુજરાતી",  short: "GU" },
    { code: "mr-IN", name: "Marathi",   native: "मराठी",    short: "MR" },
    { code: "pa-IN", name: "Punjabi",   native: "ਪੰਜਾਬੀ",   short: "PA" },
];

// Top 4 languages shown as quick-select pills
const QUICK_LANGS = LANGUAGES.slice(0, 4);

const STORAGE_KEY = "voice_agent_language";

export default function VoiceAgent() {
    const { user } = useAuth();
    const [isOpen, setIsOpen] = useState(false);
    const [agentState, setAgentState] = useState<AgentState>("idle");
    const [language, setLanguage] = useState("en-IN");
    const [showLanguageMenu, setShowLanguageMenu] = useState(false);
    const [conversation, setConversation] = useState<ConversationItem[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [audioLevel, setAudioLevel] = useState(0);

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);
    const audioContextRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const animationFrameRef = useRef<number>(0);
    const audioElementRef = useRef<HTMLAudioElement | null>(null);
    const conversationEndRef = useRef<HTMLDivElement>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const langMenuRef = useRef<HTMLDivElement>(null);
    const languageRef = useRef(language);

    // Keep ref in sync with state for stale closures
    useEffect(() => {
        languageRef.current = language;
    }, [language]);

    // Load saved language preference from localStorage
    useEffect(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved && LANGUAGES.some(l => l.code === saved)) {
            setLanguage(saved);
        }
    }, []);

    // Persist language selection
    const selectLanguage = useCallback((code: string) => {
        setLanguage(code);
        setShowLanguageMenu(false);
        localStorage.setItem(STORAGE_KEY, code);
    }, []);

    // Close language menu on outside click
    useEffect(() => {
        if (!showLanguageMenu) return;
        const handleClickOutside = (e: MouseEvent) => {
            if (langMenuRef.current && !langMenuRef.current.contains(e.target as Node)) {
                setShowLanguageMenu(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [showLanguageMenu]);

    // Auto-scroll conversation
    useEffect(() => {
        conversationEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [conversation, agentState]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
            if (audioContextRef.current) audioContextRef.current.close();
            if (audioElementRef.current) {
                audioElementRef.current.pause();
                audioElementRef.current = null;
            }
            if (streamRef.current) {
                streamRef.current.getTracks().forEach(t => t.stop());
            }
        };
    }, []);

    // ── Audio Level Monitor ──────────────────────────────────────────────
    const startAudioLevelMonitor = useCallback((stream: MediaStream) => {
        const audioCtx = new AudioContext();
        const analyser = audioCtx.createAnalyser();
        const source = audioCtx.createMediaStreamSource(stream);
        analyser.fftSize = 256;
        source.connect(analyser);
        audioContextRef.current = audioCtx;
        analyserRef.current = analyser;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const monitor = () => {
            analyser.getByteFrequencyData(dataArray);
            const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
            setAudioLevel(Math.min(avg / 128, 1));
            animationFrameRef.current = requestAnimationFrame(monitor);
        };
        monitor();
    }, []);

    const stopAudioLevelMonitor = useCallback(() => {
        if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }
        setAudioLevel(0);
    }, []);

    // ── Recording ────────────────────────────────────────────────────────
    const startRecording = useCallback(async () => {
        setError(null);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            streamRef.current = stream;
            
            const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
                ? "audio/webm;codecs=opus"
                : "audio/webm";
            
            const recorder = new MediaRecorder(stream, { mimeType });
            audioChunksRef.current = [];

            recorder.ondataavailable = (e) => {
                if (e.data.size > 0) audioChunksRef.current.push(e.data);
            };

            recorder.onstop = () => {
                stream.getTracks().forEach(t => t.stop());
                streamRef.current = null;
                stopAudioLevelMonitor();
                const blob = new Blob(audioChunksRef.current, { type: mimeType });
                handleVoiceQuery(blob);
            };

            mediaRecorderRef.current = recorder;
            recorder.start(250);
            startAudioLevelMonitor(stream);
            setAgentState("recording");
        } catch (err: any) {
            console.error("Mic access error:", err);
            setError("Microphone access denied. Please allow microphone permissions.");
        }
    }, [startAudioLevelMonitor, stopAudioLevelMonitor]);

    const stopRecording = useCallback(() => {
        if (mediaRecorderRef.current?.state === "recording") {
            mediaRecorderRef.current.stop();
        }
    }, []);

    // ── Voice Query Handler ──────────────────────────────────────────────
    const handleVoiceQuery = useCallback(async (audioBlob: Blob) => {
        setAgentState("processing");
        setError(null);

        try {
            const formData = new FormData();
            formData.append("audio", audioBlob, "recording.webm");
            if (languageRef.current) formData.append("language", languageRef.current);

            const resp = await voiceAgentApi.ask(formData);
            const data = resp.data;

            if (data.transcript) {
                setConversation(prev => [...prev, {
                    id: `u-${Date.now()}`,
                    role: "user",
                    text: data.transcript,
                    timestamp: new Date(),
                }]);
            }

            setConversation(prev => [...prev, {
                id: `a-${Date.now()}`,
                role: "agent",
                text: data.response_text,
                timestamp: new Date(),
            }]);

            if (data.audio_base64) {
                playAudio(data.audio_base64, data.audio_format || "mp3");
            } else {
                setAgentState("idle");
            }
        } catch (err: any) {
            console.error("Voice query error:", err);
            setError(err.response?.data?.detail || "Failed to process voice query. Please try again.");
            setAgentState("idle");
        }
    }, []);

    // ── Morning Briefing ─────────────────────────────────────────────────
    const handleBriefing = useCallback(async () => {
        setAgentState("processing");
        setError(null);

        try {
            const resp = await voiceAgentApi.briefing(languageRef.current, user?.ward_id);
            const data = resp.data;

            setConversation(prev => [...prev, {
                id: `a-${Date.now()}`,
                role: "agent",
                text: data.briefing_text,
                timestamp: new Date(),
            }]);

            if (data.audio_base64) {
                playAudio(data.audio_base64, data.audio_format || "mp3");
            } else {
                setAgentState("idle");
            }
        } catch (err: any) {
            console.error("Briefing error:", err);
            setError(err.response?.data?.detail || "Failed to generate briefing. Please try again.");
            setAgentState("idle");
        }
    }, [user?.ward_id]);

    // ── Audio Playback ───────────────────────────────────────────────────
    const playAudio = useCallback((base64Audio: string, format: string) => {
        setAgentState("speaking");
        
        if (audioElementRef.current) {
            audioElementRef.current.pause();
            audioElementRef.current = null;
        }

        const mimeType = format === "wav" ? "audio/wav" : "audio/mpeg";
        const audioSrc = `data:${mimeType};base64,${base64Audio}`;
        const audio = new Audio(audioSrc);
        audioElementRef.current = audio;

        audio.onended = () => {
            setAgentState("idle");
            audioElementRef.current = null;
        };

        audio.onerror = () => {
            setAgentState("idle");
            audioElementRef.current = null;
            setError("Failed to play audio response");
        };

        audio.play().catch(() => {
            setAgentState("idle");
            setError("Audio playback was blocked. Click to interact first.");
        });
    }, []);

    const stopPlayback = useCallback(() => {
        if (audioElementRef.current) {
            audioElementRef.current.pause();
            audioElementRef.current = null;
        }
        setAgentState("idle");
    }, []);

    const currentLang = LANGUAGES.find(l => l.code === language) || LANGUAGES[0];
    const isQuickLang = QUICK_LANGS.some(l => l.code === language);

    if (!user) return null;

    return (
        <>
            {/* ── Floating Voice Button ──────────────────────────────────── */}
            <button
                onClick={() => setIsOpen(v => !v)}
                className="fixed bottom-6 left-6 z-50 w-14 h-14 rounded-full shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200 flex items-center justify-center group"
                style={{
                    background: isOpen
                        ? "linear-gradient(135deg, #374151, #1f2937)"
                        : "linear-gradient(135deg, #059669, #047857)",
                }}
                aria-label="Voice Agent"
                id="voice-agent-toggle"
            >
                {isOpen ? (
                    <span className="text-white text-xl">✕</span>
                ) : (
                    <>
                        <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z" />
                        </svg>
                        <span className="absolute w-full h-full rounded-full border-2 border-emerald-400 animate-ping opacity-30" />
                    </>
                )}
            </button>

            {/* ── Voice Agent Panel ──────────────────────────────────────── */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: 20, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 20, scale: 0.95 }}
                        transition={{ type: "spring", stiffness: 300, damping: 25 }}
                        className="fixed bottom-24 left-6 z-50 w-[380px] max-h-[600px] flex flex-col bg-white rounded-3xl shadow-2xl border border-gray-100 overflow-hidden"
                        id="voice-agent-panel"
                    >
                        {/* Header */}
                        <div className="bg-gradient-to-r from-emerald-600 to-teal-700 p-4 pb-3">
                            <div className="flex items-center justify-between mb-2.5">
                                <div className="flex items-center gap-2">
                                    <div className="w-9 h-9 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center text-lg">
                                        🎙️
                                    </div>
                                    <div>
                                        <p className="text-white font-semibold text-sm">Ward Voice Agent</p>
                                        <p className="text-emerald-200 text-[10px]">Sarvam AI · Gemini Intelligence</p>
                                    </div>
                                </div>
                                <button
                                    onClick={() => setIsOpen(false)}
                                    className="text-white/70 hover:text-white text-lg leading-none"
                                >
                                    ✕
                                </button>
                            </div>

                            {/* ── Optimized Language Selector ─────────────────────── */}
                            <div className="relative" ref={langMenuRef}>
                                {/* Quick-select pills for top 4 languages */}
                                <div className="flex items-center gap-1">
                                    {QUICK_LANGS.map(lang => (
                                        <button
                                            key={lang.code}
                                            onClick={() => selectLanguage(lang.code)}
                                            className={`flex items-center gap-1 text-[11px] px-2.5 py-1.5 rounded-full transition-all duration-200 font-medium ${
                                                language === lang.code
                                                    ? "bg-white text-emerald-700 shadow-sm scale-[1.02]"
                                                    : "bg-white/15 text-white/90 hover:bg-white/25"
                                            }`}
                                        >
                                            <span className="font-bold text-[10px] opacity-70">{lang.short}</span>
                                            <span>{lang.native}</span>
                                        </button>
                                    ))}

                                    {/* "More" dropdown trigger */}
                                    <button
                                        onClick={() => setShowLanguageMenu(v => !v)}
                                        className={`flex items-center gap-1 text-[11px] px-2.5 py-1.5 rounded-full transition-all duration-200 font-medium ${
                                            !isQuickLang
                                                ? "bg-white text-emerald-700 shadow-sm"
                                                : "bg-white/15 text-white/90 hover:bg-white/25"
                                        }`}
                                        id="voice-language-selector"
                                    >
                                        {!isQuickLang ? (
                                            <>
                                                <span className="font-bold text-[10px] opacity-70">{currentLang.short}</span>
                                                <span>{currentLang.native}</span>
                                            </>
                                        ) : (
                                            <span>More ▾</span>
                                        )}
                                    </button>
                                </div>

                                {/* Dropdown for remaining languages */}
                                <AnimatePresence>
                                    {showLanguageMenu && (
                                        <motion.div
                                            initial={{ opacity: 0, y: -8, scale: 0.95 }}
                                            animate={{ opacity: 1, y: 0, scale: 1 }}
                                            exit={{ opacity: 0, y: -8, scale: 0.95 }}
                                            transition={{ type: "spring", stiffness: 400, damping: 25 }}
                                            className="absolute top-full left-0 right-0 mt-1.5 bg-white rounded-2xl shadow-2xl border border-gray-100 py-1.5 z-10 overflow-hidden"
                                        >
                                            <p className="px-3 py-1 text-[9px] font-bold uppercase tracking-widest text-gray-400">
                                                All Languages
                                            </p>
                                            <div className="grid grid-cols-2 gap-0.5 px-1.5">
                                                {LANGUAGES.map(lang => (
                                                    <button
                                                        key={lang.code}
                                                        onClick={() => selectLanguage(lang.code)}
                                                        className={`flex items-center gap-2 px-2.5 py-2 text-xs rounded-xl transition-all duration-150 ${
                                                            language === lang.code
                                                                ? "bg-emerald-50 text-emerald-700 font-semibold ring-1 ring-emerald-200"
                                                                : "text-gray-700 hover:bg-gray-50"
                                                        }`}
                                                    >
                                                        <span className="text-[13px] font-semibold min-w-[2.5rem]">{lang.native}</span>
                                                        <span className="text-[10px] text-gray-400">{lang.name}</span>
                                                        {language === lang.code && (
                                                            <span className="ml-auto text-emerald-500 text-sm">✓</span>
                                                        )}
                                                    </button>
                                                ))}
                                            </div>
                                            <div className="mt-1.5 px-3 pb-0.5">
                                                <p className="text-[9px] text-gray-300 text-center">
                                                    STT auto-detects · TTS responds in selected language
                                                </p>
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>
                        </div>

                        {/* Conversation */}
                        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50 min-h-[140px] max-h-[280px]">
                            {conversation.length === 0 && agentState === "idle" && (
                                <div className="text-center py-6 text-gray-400">
                                    <span className="text-4xl block mb-3">🎙️</span>
                                    <p className="text-sm font-medium text-gray-500">Talk to your ward</p>
                                    <p className="text-xs mt-1">Tap the mic to ask about tickets, overdue cases, or department performance</p>
                                </div>
                            )}

                            {conversation.map(item => (
                                <div key={item.id} className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}>
                                    {item.role === "agent" && (
                                        <div className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center text-xs mr-2 flex-shrink-0 mt-0.5">
                                            🎙️
                                        </div>
                                    )}
                                    <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm ${
                                        item.role === "user"
                                            ? "bg-emerald-600 text-white rounded-tr-sm"
                                            : "bg-white text-gray-800 shadow-sm border border-gray-100 rounded-tl-sm"
                                    }`}>
                                        {item.text}
                                    </div>
                                </div>
                            ))}

                            {agentState === "processing" && (
                                <div className="flex items-center gap-2">
                                    <div className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center text-xs">🧠</div>
                                    <div className="bg-white shadow-sm border border-gray-100 rounded-2xl rounded-tl-sm px-4 py-3">
                                        <div className="flex items-center gap-2">
                                            <div className="w-4 h-4 border-2 border-emerald-200 border-t-emerald-600 rounded-full animate-spin" />
                                            <span className="text-xs text-gray-500 font-medium">Thinking…</span>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {agentState === "speaking" && (
                                <div className="flex items-center gap-2">
                                    <div className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center text-xs">🔊</div>
                                    <div className="bg-white shadow-sm border border-emerald-200 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-3">
                                        <div className="flex items-center gap-0.5 h-5">
                                            {[0, 1, 2, 3, 4].map(i => (
                                                <div
                                                    key={i}
                                                    className="w-1 bg-emerald-500 rounded-full animate-pulse"
                                                    style={{
                                                        height: `${8 + Math.random() * 12}px`,
                                                        animationDelay: `${i * 0.1}s`,
                                                        animationDuration: `${0.5 + Math.random() * 0.5}s`,
                                                    }}
                                                />
                                            ))}
                                        </div>
                                        <span className="text-xs text-emerald-700 font-medium">Speaking…</span>
                                        <button
                                            onClick={stopPlayback}
                                            className="ml-1 text-[10px] text-red-500 hover:text-red-700 font-semibold"
                                        >
                                            Stop
                                        </button>
                                    </div>
                                </div>
                            )}

                            <div ref={conversationEndRef} />
                        </div>

                        {/* Error */}
                        {error && (
                            <div className="mx-4 mb-2 px-3 py-2 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">
                                {error}
                            </div>
                        )}

                        {/* Quick Actions */}
                        <div className="px-4 py-2 bg-white border-t border-gray-100 flex gap-1.5 overflow-x-auto scrollbar-none">
                            <button
                                onClick={handleBriefing}
                                disabled={agentState !== "idle"}
                                className="text-[11px] font-medium text-emerald-700 border border-emerald-200 rounded-full px-3 py-1.5 bg-emerald-50 hover:bg-emerald-100 transition-colors whitespace-nowrap flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
                                id="voice-morning-briefing"
                            >
                                🌅 Morning Briefing
                            </button>
                            <button
                                onClick={() => {
                                    setConversation([]);
                                    setError(null);
                                }}
                                className="text-[11px] font-medium text-gray-500 border border-gray-200 rounded-full px-3 py-1.5 bg-gray-50 hover:bg-gray-100 transition-colors whitespace-nowrap flex-shrink-0"
                            >
                                Clear
                            </button>
                        </div>

                        {/* Mic Button Area */}
                        <div className="px-4 py-4 bg-white border-t border-gray-100 flex flex-col items-center gap-2">
                            {agentState === "recording" ? (
                                <>
                                    <p className="text-xs text-red-600 font-medium flex items-center gap-1.5">
                                        <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                                        Listening… tap to send
                                    </p>
                                    <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden mb-1">
                                        <div
                                            className="h-full bg-gradient-to-r from-emerald-400 to-emerald-600 rounded-full transition-all duration-75"
                                            style={{ width: `${Math.max(5, audioLevel * 100)}%` }}
                                        />
                                    </div>
                                    <button
                                        onClick={stopRecording}
                                        className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 text-white shadow-lg hover:shadow-xl transition-all flex items-center justify-center group"
                                        id="voice-stop-recording"
                                    >
                                        <svg className="w-7 h-7" fill="currentColor" viewBox="0 0 24 24">
                                            <rect x="6" y="6" width="12" height="12" rx="2" />
                                        </svg>
                                        <span className="absolute w-20 h-20 rounded-full border-2 border-red-400 animate-ping opacity-20" />
                                    </button>
                                </>
                            ) : (
                                <>
                                    <p className="text-[11px] text-gray-400">
                                        {agentState === "idle" ? "Tap to speak" :
                                         agentState === "processing" ? "Processing your query…" :
                                         "Playing response…"}
                                    </p>
                                    <button
                                        onClick={startRecording}
                                        disabled={agentState !== "idle"}
                                        className="w-16 h-16 rounded-full shadow-lg hover:shadow-xl transition-all flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed relative"
                                        style={{
                                            background: agentState === "idle"
                                                ? "linear-gradient(135deg, #059669, #047857)"
                                                : "#9ca3af",
                                        }}
                                        id="voice-start-recording"
                                    >
                                        <svg className="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 24 24">
                                            <path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z" />
                                        </svg>
                                    </button>
                                </>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
}
