"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/getErrorMessage";
import { authApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";

const schema = z.object({
    email: z.string().email("Enter a valid email"),
    password: z.string().min(6, "Password must be at least 6 characters"),
});

type FormData = z.infer<typeof schema>;

const ROLE_REDIRECTS: Record<string, string> = {
    COUNCILLOR: "/councillor/dashboard",
    SUPERVISOR: "/officer/dashboard",
    JUNIOR_ENGINEER: "/officer/dashboard",
    FIELD_STAFF: "/officer/dashboard",
    SUPER_ADMIN: "/",
    PUBLIC_USER: "/",
};

export default function LoginPage() {
    const router = useRouter();
    const { login } = useAuth();
    const [loading, setLoading] = useState(false);

    const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
        resolver: zodResolver(schema),
    });

    const onSubmit = async (data: FormData) => {
        setLoading(true);
        try {
            const res = await authApi.login(data.email, data.password);
            const { access_token, user } = res.data;
            login(access_token, user);
            toast.success(`Welcome back, ${user.name}!`);
            const redirect = ROLE_REDIRECTS[user.role] ?? "/officer/dashboard";
            router.push(redirect);
        } catch (err: any) {
            toast.error(getErrorMessage(err, "Login failed. Check credentials."));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-900 via-indigo-900 to-slate-900 flex items-center justify-center px-4">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="w-full max-w-md"
            >
                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white font-extrabold text-2xl mx-auto mb-4 shadow-xl">
                        JV
                    </div>
                    <h1 className="text-2xl font-bold text-white">JanVedha AI</h1>
                    <p className="text-blue-300 mt-1">Officer Portal Login</p>
                </div>

                <div className="bg-white/10 backdrop-blur-md border border-white/20 rounded-3xl p-8 shadow-2xl">
                    <h2 className="text-xl font-bold text-white mb-6">Sign In</h2>

                    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-blue-100 mb-1.5">Email Address</label>
                            <input
                                {...register("email")}
                                type="email"
                                placeholder="officer@nmc.gov.in"
                                className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-white placeholder:text-white/40 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                            />
                            {errors.email && <p className="text-red-400 text-xs mt-1">{errors.email.message}</p>}
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-blue-100 mb-1.5">Password</label>
                            <input
                                {...register("password")}
                                type="password"
                                placeholder="••••••••"
                                className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-white placeholder:text-white/40 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                            />
                            {errors.password && <p className="text-red-400 text-xs mt-1">{errors.password.message}</p>}
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-xl py-3.5 font-bold hover:shadow-lg hover:shadow-blue-500/30 transition-all duration-200 disabled:opacity-60 flex items-center justify-center gap-2 mt-2"
                        >
                            {loading ? (
                                <>
                                    <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    Signing in…
                                </>
                            ) : (
                                "Sign In →"
                            )}
                        </button>
                    </form>

                    <div className="mt-6 text-center">
                        <p className="text-blue-300 text-sm">
                            Citizen?{" "}
                            <Link href="/" className="text-white font-semibold hover:text-blue-200 transition-colors">
                                Submit a complaint
                            </Link>
                        </p>
                    </div>

                    {/* Info box */}
                    <div className="mt-5 bg-blue-500/10 border border-blue-400/20 rounded-xl p-4">
                        <p className="text-xs text-blue-200 font-medium mb-2">Supported Roles</p>
                        <div className="flex flex-wrap gap-1.5">
                            {["Supervisor", "Junior Engineer", "Councillor"].map((r) => (
                                <span key={r} className="text-xs bg-white/10 text-blue-100 rounded-full px-2.5 py-0.5">
                                    {r}
                                </span>
                            ))}
                        </div>
                    </div>
                </div>
            </motion.div>
        </div>
    );
}
