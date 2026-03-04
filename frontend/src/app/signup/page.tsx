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

const schema = z
    .object({
        name: z.string().min(2, "Name must be at least 2 characters"),
        email: z.string().email("Enter a valid email"),
        phone: z.string().regex(/^[6-9]\d{9}$/, "Enter valid 10-digit Indian mobile number"),
        password: z.string().min(6, "Password must be at least 6 characters"),
        confirmPassword: z.string(),
    })
    .refine((d) => d.password === d.confirmPassword, {
        message: "Passwords do not match",
        path: ["confirmPassword"],
    });

type FormData = z.infer<typeof schema>;

export default function SignupPage() {
    const router = useRouter();
    const { login } = useAuth();
    const [loading, setLoading] = useState(false);

    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm<FormData>({ resolver: zodResolver(schema) });

    const onSubmit = async (data: FormData) => {
        setLoading(true);
        try {
            // Register
            await authApi.registerPublic({
                name: data.name,
                email: data.email,
                phone: data.phone,
                password: data.password,
            });

            // Auto-login after registration
            const res = await authApi.login(data.email, data.password);
            const { access_token, user } = res.data;
            login(access_token, user);
            toast.success(`Welcome, ${user.name}! Your account has been created.`);
            router.push("/");
        } catch (err: any) {
            toast.error(getErrorMessage(err, "Registration failed. Please try again."));
        } finally {
            setLoading(false);
        }
    };

    const inputClass =
        "w-full bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-white placeholder:text-white/40 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-transparent transition-all";

    return (
        <div className="min-h-screen bg-gradient-to-br from-emerald-900 via-teal-900 to-slate-900 flex items-center justify-center px-4">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="w-full max-w-md"
            >
                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-white font-extrabold text-2xl mx-auto mb-4 shadow-xl">
                        JV
                    </div>
                    <h1 className="text-2xl font-bold text-white">Join JanVedha AI</h1>
                    <p className="text-emerald-300 mt-1">Create your citizen account</p>
                </div>

                <div className="bg-white/10 backdrop-blur-md border border-white/20 rounded-3xl p-8 shadow-2xl">
                    <h2 className="text-xl font-bold text-white mb-6">Sign Up</h2>

                    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-emerald-100 mb-1.5">
                                Full Name
                            </label>
                            <input
                                {...register("name")}
                                type="text"
                                placeholder="Your full name"
                                className={inputClass}
                            />
                            {errors.name && (
                                <p className="text-red-400 text-xs mt-1">{errors.name.message}</p>
                            )}
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-emerald-100 mb-1.5">
                                Email Address
                            </label>
                            <input
                                {...register("email")}
                                type="email"
                                placeholder="you@example.com"
                                className={inputClass}
                            />
                            {errors.email && (
                                <p className="text-red-400 text-xs mt-1">{errors.email.message}</p>
                            )}
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-emerald-100 mb-1.5">
                                Mobile Number
                            </label>
                            <input
                                {...register("phone")}
                                type="tel"
                                placeholder="10-digit mobile number"
                                className={inputClass}
                            />
                            {errors.phone && (
                                <p className="text-red-400 text-xs mt-1">{errors.phone.message}</p>
                            )}
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="block text-sm font-medium text-emerald-100 mb-1.5">
                                    Password
                                </label>
                                <input
                                    {...register("password")}
                                    type="password"
                                    placeholder="••••••••"
                                    className={inputClass}
                                />
                                {errors.password && (
                                    <p className="text-red-400 text-xs mt-1">
                                        {errors.password.message}
                                    </p>
                                )}
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-emerald-100 mb-1.5">
                                    Confirm
                                </label>
                                <input
                                    {...register("confirmPassword")}
                                    type="password"
                                    placeholder="••••••••"
                                    className={inputClass}
                                />
                                {errors.confirmPassword && (
                                    <p className="text-red-400 text-xs mt-1">
                                        {errors.confirmPassword.message}
                                    </p>
                                )}
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-gradient-to-r from-emerald-500 to-teal-600 text-white rounded-xl py-3.5 font-bold hover:shadow-lg hover:shadow-emerald-500/30 transition-all duration-200 disabled:opacity-60 flex items-center justify-center gap-2 mt-2"
                        >
                            {loading ? (
                                <>
                                    <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    Creating account…
                                </>
                            ) : (
                                "Create Account →"
                            )}
                        </button>
                    </form>

                    <div className="mt-6 text-center space-y-2">
                        <p className="text-teal-300 text-sm">
                            Already have an account?{" "}
                            <Link
                                href="/user-login"
                                className="text-white font-semibold hover:text-emerald-200 transition-colors"
                            >
                                Sign In
                            </Link>
                        </p>
                        <p className="text-teal-400/60 text-xs">
                            Officer?{" "}
                            <Link
                                href="/login"
                                className="text-teal-300/80 hover:text-white transition-colors"
                            >
                                Officer login →
                            </Link>
                        </p>
                    </div>
                </div>
            </motion.div>
        </div>
    );
}
