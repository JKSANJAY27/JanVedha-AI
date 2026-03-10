"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { authApi } from "@/lib/api";
import { USER_ROLES } from "@/lib/constants";

export default function NavBar() {
    const { user, isOfficer, logout } = useAuth();
    const router = useRouter();
    const pathname = usePathname();

    const isPublicUser = !!user && user.role === "PUBLIC_USER";

    const handleLogout = async () => {
        try { await authApi.logout(); } catch { }
        logout();
        router.push("/");
    };

    const navLink = (href: string, label: string) => (
        <Link
            href={href}
            className={`text-sm font-medium transition-colors hover:text-blue-600 ${pathname === href ? "text-blue-600 border-b-2 border-blue-600 pb-0.5" : "text-gray-600"
                }`}
        >
            {label}
        </Link>
    );

    return (
        <nav className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-gray-100 shadow-sm">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
                {/* Logo */}
                <Link href="/" className="flex items-center gap-2 group">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center text-white font-bold text-sm shadow-sm group-hover:shadow-md transition-shadow">
                        JV
                    </div>
                    <span className="font-bold text-gray-900 text-lg hidden sm:block">JanVedha AI</span>
                </Link>

                {user ? (
                    <>
                        {/* Public nav */}
                        <div className="flex items-center gap-6">
                            {!isOfficer && (
                                <>
                                    {isPublicUser && navLink("/dashboard", "Dashboard")}
                                    {navLink("/", "Submit")}
                                </>
                            )}
                            {navLink("/map", "Issue Heatmap")}
                            {!isPublicUser && navLink("/ward-performance", "Leaderboard")}

                            {/* Public user: My Tickets */}
                            {isPublicUser && navLink("/my-tickets", "My Tickets")}

                            {/* Officer links */}
                            {isOfficer && user.role !== "SUPER_ADMIN" && (
                                <>
                                    {navLink("/officer/dashboard", "Dashboard")}
                                    {navLink("/officer/reports", "Reports")}
                                </>
                            )}
                            {user.role === "SUPER_ADMIN" && (
                                <>
                                    {navLink("/officer/reports", "Reports")}
                                    {navLink("/map", "Full System Map")}
                                </>
                            )}
                        </div>

                        {/* User Profile & Logout */}
                        <div className="flex items-center gap-3">
                            <div className="hidden sm:flex flex-col items-end">
                                <span className="text-sm font-medium text-gray-900">{user.name}</span>
                                <span className="text-xs text-gray-400">{USER_ROLES[user.role] ?? user.role.replace(/_/g, " ")}</span>
                            </div>
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm">
                                {user.name[0]?.toUpperCase()}
                            </div>
                            <button
                                onClick={handleLogout}
                                className="text-sm text-gray-500 hover:text-red-500 transition-colors"
                            >
                                Logout
                            </button>
                        </div>
                    </>
                ) : (
                    <div className="flex items-center gap-3">
                        <Link
                            href="/user-login?mode=login"
                            className="text-sm font-semibold text-gray-600 hover:text-blue-600 transition-colors px-3 py-2"
                        >
                            Sign In
                        </Link>
                        <Link
                            href="/user-login?mode=signup"
                            className="text-sm font-bold bg-blue-600/10 text-blue-700 px-4 py-2 rounded-xl hover:bg-blue-600/20 transition-all shadow-sm"
                        >
                            Sign Up
                        </Link>
                        <div className="w-px h-5 bg-gray-200 mx-1 hidden sm:block" />
                        <Link
                            href="/user-login?mode=officer"
                            className="text-xs font-semibold text-gray-500 hover:text-gray-800 transition-colors px-3 py-2 bg-gray-100 rounded-lg"
                        >
                            Staff
                        </Link>
                    </div>
                )}
            </div>
        </nav >
    );
}

