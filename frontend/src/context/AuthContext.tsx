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
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    token: null,
    login: () => { },
    logout: () => { },
    isOfficer: false,
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

    const isOfficer =
        !!user &&
        user.role !== "PUBLIC_USER" &&
        user.role !== undefined;

    return (
        <AuthContext.Provider value={{ user, token, login, logout, isOfficer }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
