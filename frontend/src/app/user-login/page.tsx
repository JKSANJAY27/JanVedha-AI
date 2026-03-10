"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/getErrorMessage";
import { authApi, publicApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";
import dynamic from "next/dynamic";
import { PRIORITY_COLORS } from "@/lib/constants";
import PriorityBadge from "@/components/PriorityBadge";
import { formatRelative } from "@/lib/formatters";

// Map needs to be dynamic to avoid SSR issues
const MapComponent = dynamic(() => import("@/features/map/IssueMap"), { ssr: false });

const loginSchema = z.object({
    email: z.string().email("Enter a valid email"),
    password: z.string().min(6, "Password must be at least 6 characters"),
});

const signupSchema = z.object({
    name: z.string().min(2, "Full name is required"),
    email: z.string().email("Enter a valid email"),
    phone: z.string().regex(/^[6-9]\d{9}$/, "Enter valid 10-digit mobile number"),
    password: z.string().min(6, "Password must be at least 6 characters"),
    confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
});

type LoginFormData = z.infer<typeof loginSchema>;
type SignupFormData = z.infer<typeof signupSchema>;

interface MapIssue {
    id: string;
    ticket_code: string;
    description: string;
    dept_id: string;
    priority_label: string;
    priority_score: number;
    status: string;
    lat?: number;
    lng?: number;
    location?: { lat?: number; lng?: number; address?: string };
    created_at: string;
}

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function LoginContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { login } = useAuth();

    // Sync tab with URL
    const modeParam = searchParams.get("mode") as any;
    const initialTab = (['login', 'signup', 'officer'].includes(modeParam)) ? modeParam : 'login';

    const [activeTab, setActiveTab] = useState<'login' | 'signup' | 'officer'>(initialTab);
    const [loading, setLoading] = useState(false);
    const [isMapLoading, setIsMapLoading] = useState(true);

    const [issues, setIssues] = useState<MapIssue[]>([]);
    const [topIssues, setTopIssues] = useState<MapIssue[]>([]);
    const [currentSlideIndex, setCurrentSlideIndex] = useState(0);

    const loginForm = useForm<LoginFormData>({ resolver: zodResolver(loginSchema) });
    const signupForm = useForm<SignupFormData>({ resolver: zodResolver(signupSchema) });

    useEffect(() => {
        if (modeParam && ['login', 'signup', 'officer'].includes(modeParam) && activeTab !== modeParam) {
            setActiveTab(modeParam);
        }
    }, [modeParam]);

    useEffect(() => {
        setIsMapLoading(true);
        publicApi.getHeatmap().then((res) => {
            const items: any[] = res.data?.data || res.data || [];
            const normalized = items.map((item: any) => ({
                ...item,
                lat: item.location?.lat ?? item.lat ?? undefined,
                lng: item.location?.lng ?? item.lng ?? undefined,
            }));
            setIssues(normalized);

            const top5 = [...normalized]
                .sort((a, b) => b.priority_score - a.priority_score)
                .slice(0, 5);
            setTopIssues(top5);
        }).catch((err) => {
            console.error("Failed to fetch heatmap data:", err);
        }).finally(() => {
            setIsMapLoading(false);
        });
    }, []);

    useEffect(() => {
        if (topIssues.length <= 1) return;
        const interval = setInterval(() => {
            setCurrentSlideIndex((prev) => (prev + 1) % topIssues.length);
        }, 5000);
        return () => clearInterval(interval);
    }, [topIssues.length]);

    const onLoginSubmit = async (data: LoginFormData) => {
        setLoading(true);
        try {
            const res = await authApi.login(data.email, data.password);
            const { access_token, user } = res.data;
            login(access_token, user);
            toast.success(`Welcome back, ${user.name}!`);
            router.push("/");
        } catch (err: any) {
            toast.error(getErrorMessage(err, "Login failed. Check your credentials."));
        } finally {
            setLoading(false);
        }
    };

    const onSignupSubmit = async (data: SignupFormData) => {
        setLoading(true);
        try {
            await authApi.registerPublic({
                name: data.name,
                email: data.email,
                phone: data.phone,
                password: data.password,
            });
            toast.success("Account created successfully! Please sign in.");
            router.push("/user-login?mode=login");
            signupForm.reset();
        } catch (err: any) {
            toast.error(getErrorMessage(err, "Signup failed"));
        } finally {
            setLoading(false);
        }
    };

    const inputClass = "w-full bg-slate-900/40 border border-slate-700/50 rounded-xl px-4 py-3 text-white placeholder:text-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all backdrop-blur-sm";
    const labelClass = "block text-sm font-medium text-slate-300 mb-1.5 ml-1";

    return (
        <div className="relative w-full h-[calc(100vh-64px)] overflow-hidden bg-slate-900">
            {/* BACKGROUND MAP */}
            <div className="absolute inset-0 z-0 opacity-80 mix-blend-luminosity hover:mix-blend-normal transition-all duration-1000">
                {!isMapLoading ? (
                    <MapComponent issues={issues} onIssueClick={() => { }} />
                ) : (
                    <div className="h-full w-full flex items-center justify-center text-slate-400">
                        <div className="flex flex-col items-center gap-3">
                            <span className="w-8 h-8 border-4 border-slate-700 border-t-emerald-500 rounded-full animate-spin" />
                            <p className="text-sm font-medium">Loading Live Intel Map...</p>
                        </div>
                    </div>
                )}
            </div>

            {/* FLOATING AUTH PANEL (Left) */}
            <div className="absolute left-0 md:left-8 lg:left-24 top-0 md:top-1/2 md:-translate-y-1/2 w-full md:w-[450px] h-full md:h-auto overflow-y-auto md:overflow-visible z-10 p-4 md:p-0">
                <div className="bg-slate-900/60 backdrop-blur-xl border border-white/10 p-6 sm:p-8 rounded-3xl shadow-[0_8px_40px_rgba(0,0,0,0.5)]">
                    <div className="flex items-center gap-4 mb-8">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-blue-600 flex items-center justify-center text-white font-extrabold text-lg shadow-lg border border-white/20">
                            JV
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold text-white tracking-tight leading-none mb-1">JanVedha AI</h1>
                            <p className="text-emerald-400 text-xs font-medium tracking-wide">Civic Operations API</p>
                        </div>
                    </div>

                    {/* Aesthetic Tab Selector */}
                    <div className="flex p-1 bg-slate-950/50 rounded-2xl mb-8 border border-white/5 relative">
                        {['login', 'signup', 'officer'].map((tab) => (
                            <button
                                key={tab}
                                onClick={() => router.push(`/user-login?mode=${tab}`)}
                                className={`flex-1 py-2 text-sm font-semibold rounded-xl transition-all relative z-10 ${activeTab === tab ? "text-white" : "text-slate-400 hover:text-slate-200"}`}
                            >
                                {activeTab === tab && (
                                    <motion.div
                                        layoutId="activeTabIndicator"
                                        className="absolute inset-0 bg-white/10 rounded-xl shadow-sm border border-white/10"
                                        transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                                    />
                                )}
                                <span className="relative z-20">
                                    {tab === 'login' && "Sign In"}
                                    {tab === 'signup' && "Sign Up"}
                                    {tab === 'officer' && "Staff"}
                                </span>
                            </button>
                        ))}
                    </div>

                    <div className="min-h-[280px]">
                        <AnimatePresence mode="wait">
                            <motion.div
                                key={activeTab}
                                initial={{ opacity: 0, scale: 0.98 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.98 }}
                                transition={{ duration: 0.2 }}
                            >
                                {activeTab === 'login' && (
                                    <form onSubmit={loginForm.handleSubmit(onLoginSubmit)} className="space-y-4">
                                        <div>
                                            <label className={labelClass}>Email Address</label>
                                            <input {...loginForm.register("email")} type="email" placeholder="citizen@example.com" className={inputClass} />
                                            {loginForm.formState.errors.email && <p className="text-red-400 text-xs mt-1.5 ml-1">{loginForm.formState.errors.email.message}</p>}
                                        </div>
                                        <div>
                                            <div className="flex items-center justify-between mb-1.5">
                                                <label className={labelClass.replace("mb-1.5", "mb-0")}>Password</label>
                                                <a href="#" className="text-xs text-blue-400 hover:text-blue-300">Forgot?</a>
                                            </div>
                                            <input {...loginForm.register("password")} type="password" placeholder="••••••••" className={inputClass} />
                                            {loginForm.formState.errors.password && <p className="text-red-400 text-xs mt-1.5 ml-1">{loginForm.formState.errors.password.message}</p>}
                                        </div>
                                        <button type="submit" disabled={loading} className="w-full bg-blue-600/90 hover:bg-blue-500 text-white rounded-xl py-3.5 font-bold transition-all disabled:opacity-60 flex items-center justify-center gap-2 mt-6 border border-blue-400/30">
                                            {loading ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : "Secure Access"}
                                        </button>
                                    </form>
                                )}

                                {activeTab === 'signup' && (
                                    <form onSubmit={signupForm.handleSubmit(onSignupSubmit)} className="space-y-3">
                                        <div>
                                            <input {...signupForm.register("name")} type="text" placeholder="Full Name" className={inputClass} />
                                            {signupForm.formState.errors.name && <p className="text-red-400 text-xs mt-1.5 ml-1">{signupForm.formState.errors.name.message}</p>}
                                        </div>
                                        <div className="grid grid-cols-2 gap-3">
                                            <div>
                                                <input {...signupForm.register("email")} type="email" placeholder="Email" className={inputClass} />
                                                {signupForm.formState.errors.email && <p className="text-red-400 text-xs mt-1.5 ml-1">{signupForm.formState.errors.email.message}</p>}
                                            </div>
                                            <div>
                                                <input {...signupForm.register("phone")} type="tel" placeholder="Mobile" className={inputClass} />
                                                {signupForm.formState.errors.phone && <p className="text-red-400 text-xs mt-1.5 ml-1">{signupForm.formState.errors.phone.message}</p>}
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-2 gap-3">
                                            <div>
                                                <input {...signupForm.register("password")} type="password" placeholder="Password" className={inputClass} />
                                                {signupForm.formState.errors.password && <p className="text-red-400 text-xs mt-1.5 ml-1">{signupForm.formState.errors.password.message}</p>}
                                            </div>
                                            <div>
                                                <input {...signupForm.register("confirmPassword")} type="password" placeholder="Confirm" className={inputClass} />
                                                {signupForm.formState.errors.confirmPassword && <p className="text-red-400 text-xs mt-1.5 ml-1">{signupForm.formState.errors.confirmPassword.message}</p>}
                                            </div>
                                        </div>
                                        <button type="submit" disabled={loading} className="w-full bg-emerald-600/90 hover:bg-emerald-500 text-white rounded-xl py-3 block font-bold transition-all disabled:opacity-60 mt-4 border border-emerald-400/30">
                                            {loading ? "Creating..." : "Create Account"}
                                        </button>
                                    </form>
                                )}

                                {activeTab === 'officer' && (
                                    <div className="text-center py-6 bg-slate-900/50 rounded-2xl border border-white/5 p-6">
                                        <div className="w-14 h-14 bg-indigo-500/20 rounded-2xl flex items-center justify-center border border-indigo-500/30 mx-auto mb-4">
                                            <svg className="w-7 h-7 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                            </svg>
                                        </div>
                                        <h3 className="text-lg font-bold text-white mb-2">Government Staff</h3>
                                        <p className="text-slate-400 text-xs mb-6">Secure access to the Internal JanVedha AI Dashboard.</p>
                                        <Link href="/login" className="w-full inline-block bg-indigo-600/90 hover:bg-indigo-500 text-white rounded-xl py-3 font-bold transition-all border border-indigo-400/30">
                                            Go to Officer Portal →
                                        </Link>
                                    </div>
                                )}
                            </motion.div>
                        </AnimatePresence>
                    </div>
                </div>
            </div>

            {/* FLOATING LIVE FEED PANEL (Right) */}
            <div className="hidden lg:block absolute right-12 top-1/2 -translate-y-1/2 w-[400px] z-10 pointer-events-none">
                <div className="bg-white/10 backdrop-blur-md border border-white/20 p-6 rounded-3xl shadow-2xl relative overflow-hidden">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="w-2.5 h-2.5 bg-red-400 rounded-full animate-pulse shadow-[0_0_10px_rgba(248,113,113,0.8)]" />
                        <h2 className="text-lg font-bold text-white tracking-tight">Critical Issues</h2>
                        <span className="ml-auto text-xs text-white/50 font-bold tracking-widest uppercase">Live</span>
                    </div>

                    <div className="relative h-44">
                        {topIssues.length > 0 && (
                            <AnimatePresence mode="wait">
                                <motion.div
                                    key={currentSlideIndex}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: -20 }}
                                    transition={{ duration: 0.4 }}
                                    className="absolute inset-0"
                                >
                                    <div className="flex items-center gap-2 mb-3">
                                        <PriorityBadge label={topIssues[currentSlideIndex].priority_label} />
                                        <span className="text-xs text-white/60 font-mono">
                                            {topIssues[currentSlideIndex].ticket_code}
                                        </span>
                                    </div>
                                    <h3 className="text-base font-medium text-white line-clamp-3 leading-snug mb-3">
                                        {topIssues[currentSlideIndex].description}
                                    </h3>
                                    <div className="mt-auto flex items-center justify-between opacity-70">
                                        <span className="text-xs text-white truncate max-w-[180px]">
                                            📍 {topIssues[currentSlideIndex].location?.address || "Unknown"}
                                        </span>
                                        <span className="text-xs text-white/50">
                                            {formatRelative(topIssues[currentSlideIndex].created_at)}
                                        </span>
                                    </div>
                                </motion.div>
                            </AnimatePresence>
                        )}
                    </div>
                </div>
            </div>

            {/* Overlay Gradient to ensure contrast handles map styles */}
            <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-slate-900 to-transparent z-0 pointer-events-none" />
        </div>
    );
}

export default function UserLoginPage() {
    return (
        <Suspense fallback={<div className="min-h-screen bg-slate-900 flex items-center justify-center text-white">Loading...</div>}>
            <LoginContent />
        </Suspense>
    );
}
