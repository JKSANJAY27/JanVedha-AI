"use client";

import { createContext, useContext, useEffect, useState } from "react";

interface User {
    id: string;
    name: string;
    role: string;
    ward_id?: number;
    zone_id?: number;
    dept_id?: string;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    login: (token: string, user: User) => void;
    logout: () => void;
    isOfficer: boolean;
    isWardPGO: boolean;
    isDeptOfficer: boolean;
    isTechnician: boolean;
    isCouncillor: boolean;
    isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    token: null,
    login: () => { },
    logout: () => { },
    isOfficer: false,
    isWardPGO: false,
    isDeptOfficer: false,
    isTechnician: false,
    isCouncillor: false,
    isAdmin: false,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);

    useEffect(() => {
        const savedToken = localStorage.getItem("access_token");
        const savedUser = localStorage.getItem("user");
        if (savedToken && savedUser) {
            setToken(savedToken);
            setUser(JSON.parse(savedUser));
        }
    }, []);

    const login = (tok: string, usr: User) => {
        localStorage.setItem("access_token", tok);
        localStorage.setItem("user", JSON.stringify(usr));
        setToken(tok);
        setUser(usr);
    };

    const logout = () => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("user");
        setToken(null);
        setUser(null);
    };

    const role = user?.role ?? "";
    const isOfficer = !!user && role !== "PUBLIC_USER";
    const isWardPGO = role === "WARD_OFFICER";
    const isDeptOfficer = role === "DEPT_HEAD";
    const isTechnician = role === "TECHNICIAN";
    const isCouncillor = role === "COUNCILLOR";
    const isAdmin = role === "COMMISSIONER" || role === "SUPER_ADMIN";

    return (
        <AuthContext.Provider value={{
            user, token, login, logout,
            isOfficer, isWardPGO, isDeptOfficer, isTechnician, isCouncillor, isAdmin,
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
