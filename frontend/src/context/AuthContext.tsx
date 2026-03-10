"use client";

import { createContext, useContext, useEffect, useState } from "react";

interface User {
    id: string;
    name: string;
    role: string;
    phone?: string;
    email?: string;
    ward_id?: number;
    zone_id?: number;
    dept_id?: string;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    loading: boolean;
    login: (token: string, user: User) => void;
    logout: () => void;
    isOfficer: boolean;
    isSupervisor: boolean;
    isJuniorEngineer: boolean;
    isFieldStaff: boolean;
    isCouncillor: boolean;
    isCommissioner: boolean;
    isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    token: null,
    loading: true,
    login: () => { },
    logout: () => { },
    isOfficer: false,
    isSupervisor: false,
    isJuniorEngineer: false,
    isFieldStaff: false,
    isCouncillor: false,
    isCommissioner: false,
    isAdmin: false,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const savedToken = localStorage.getItem("access_token");
        const savedUser = localStorage.getItem("user");
        if (savedToken && savedUser) {
            setToken(savedToken);
            setUser(JSON.parse(savedUser));
        }
        setLoading(false);
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
    const isSupervisor = role === "SUPERVISOR";
    const isJuniorEngineer = role === "JUNIOR_ENGINEER";
    const isFieldStaff = role === "FIELD_STAFF";
    const isCouncillor = role === "COUNCILLOR";
    const isCommissioner = role === "COMMISSIONER" || role === "SUPER_ADMIN";
    const isAdmin = role === "SUPER_ADMIN";

    return (
        <AuthContext.Provider value={{
            user, token, loading, login, logout,
            isOfficer, isSupervisor, isJuniorEngineer, isFieldStaff, isCouncillor, isCommissioner, isAdmin,
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
