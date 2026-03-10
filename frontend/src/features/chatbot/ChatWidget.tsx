"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "@/context/AuthContext";

interface Message {
    id: string;
    role: "user" | "bot";
    text: string;
    timestamp: Date;
    actions?: { label: string; href: string }[];
}

const QUICK_REPLIES = [
    "How do I file a complaint?",
    "Track my ticket",
    "SLA information",
    "Ward performance",
];

const BOT_WELCOME = "Hi! I'm your Civic AI Assistant 🏛️\n\nI can help you track complaints, explain SLA policies, and guide you through our civic management system. How can I help you today?";

export default function ChatWidget() {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState<Message[]>([
        {
            id: "welcome",
            role: "bot",
            text: BOT_WELCOME,
            timestamp: new Date(),
        },
    ]);
    const [input, setInput] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const [unread, setUnread] = useState(0);
    const wsRef = useRef<WebSocket | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const { user } = useAuth();

    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [messages, isTyping]);

    // Connect WebSocket
    useEffect(() => {
        const sessionId = Math.random().toString(36).substring(7);
        const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
        const wsBaseUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
        const wsUrl = `${wsBaseUrl}/api/chat/ws${token ? `?token=${token}` : ""}`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            setIsTyping(false);
            if (data.type === "BOT_MESSAGE") {
                const msg: Message = {
                    id: Date.now().toString(),
                    role: "bot",
                    text: data.message,
                    timestamp: new Date(),
                    actions: data.actions,
                };
                setMessages((prev) => [...prev, msg]);
                if (!isOpen) setUnread((n) => n + 1);
            }
        };

        ws.onerror = () => {
            setIsTyping(false);
        };

        return () => {
            ws.close();
        };
    }, []);

    const sendMessage = (text: string) => {
        if (!text.trim()) return;
        const userMsg: Message = {
            id: Date.now().toString(),
            role: "user",
            text,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setIsTyping(true);

        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(
                JSON.stringify({
                    type: "USER_MESSAGE",
                    message: text,
                    user_id: user?.id ?? "anonymous",
                    session_id: Math.random().toString(36),
                })
            );
        } else {
            // Fallback: offline response  
            setTimeout(() => {
                setIsTyping(false);
                setMessages((prev) => [
                    ...prev,
                    {
                        id: Date.now().toString(),
                        role: "bot",
                        text: "I'm currently offline. Please visit /track to check your ticket status, or call our helpline.",
                        timestamp: new Date(),
                    },
                ]);
            }, 1200);
        }
    };

    return (
        <>
            {/* Floating button */}
            <button
                onClick={() => {
                    setIsOpen((v) => !v);
                    setUnread(0);
                }}
                className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-gradient-to-br from-blue-600 to-indigo-700 text-white shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200 flex items-center justify-center"
                aria-label="Open chat assistant"
            >
                <span className="text-2xl">{isOpen ? "✕" : "💬"}</span>
                {unread > 0 && !isOpen && (
                    <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-xs font-bold flex items-center justify-center">
                        {unread}
                    </span>
                )}
            </button>

            {/* Chat window */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: 20, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 20, scale: 0.95 }}
                        transition={{ type: "spring", stiffness: 300, damping: 25 }}
                        className="fixed bottom-24 right-6 z-50 w-[360px] max-h-[520px] flex flex-col bg-white rounded-3xl shadow-2xl border border-gray-100 overflow-hidden"
                    >
                        {/* Header */}
                        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 p-4 flex items-center gap-3">
                            <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-lg">
                                🏛️
                            </div>
                            <div className="flex-1">
                                <p className="text-white font-semibold text-sm">Civic AI Assistant</p>
                                <p className="text-blue-200 text-xs">Online · Powered by Gemini</p>
                            </div>
                            <button
                                onClick={() => setIsOpen(false)}
                                className="text-white/70 hover:text-white text-lg leading-none"
                            >
                                ✕
                            </button>
                        </div>

                        {/* Messages */}
                        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
                            {messages.map((msg) => (
                                <div
                                    key={msg.id}
                                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                                >
                                    {msg.role === "bot" && (
                                        <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center text-sm mr-2 flex-shrink-0 mt-0.5">
                                            🤖
                                        </div>
                                    )}
                                    <div className={`max-w-[80%] ${msg.role === "user" ? "" : ""}`}>
                                        <div
                                            className={`rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${msg.role === "user"
                                                ? "bg-blue-600 text-white rounded-tr-sm"
                                                : "bg-white text-gray-800 shadow-sm border border-gray-100 rounded-tl-sm"
                                                }`}
                                        >
                                            {msg.text}
                                        </div>
                                        {msg.actions?.map((a) => (
                                            <a
                                                key={a.label}
                                                href={a.href}
                                                className="mt-1 inline-block text-xs text-blue-600 border border-blue-200 rounded-lg px-3 py-1 bg-blue-50 hover:bg-blue-100 transition-colors mr-1"
                                            >
                                                {a.label} →
                                            </a>
                                        ))}
                                    </div>
                                </div>
                            ))}

                            {isTyping && (
                                <div className="flex items-center gap-2">
                                    <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center text-sm">
                                        🤖
                                    </div>
                                    <div className="bg-white shadow-sm border border-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1">
                                        {[0, 1, 2].map((i) => (
                                            <span
                                                key={i}
                                                className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce"
                                                style={{ animationDelay: `${i * 0.15}s` }}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Quick replies */}
                        <div className="flex gap-1.5 px-4 py-2 bg-white border-t border-gray-100 overflow-x-auto flex-nowrap scrollbar-none">
                            {QUICK_REPLIES.map((qr) => (
                                <button
                                    key={qr}
                                    onClick={() => sendMessage(qr)}
                                    className="text-xs text-blue-600 border border-blue-200 rounded-full px-3 py-1 bg-blue-50 hover:bg-blue-100 transition-colors whitespace-nowrap flex-shrink-0"
                                >
                                    {qr}
                                </button>
                            ))}
                        </div>

                        {/* Input */}
                        <div className="p-3 bg-white border-t border-gray-100 flex gap-2">
                            <input
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage(input)}
                                placeholder="Ask me anything..."
                                className="flex-1 text-sm border border-gray-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            />
                            <button
                                onClick={() => sendMessage(input)}
                                disabled={!input.trim()}
                                className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                            >
                                ➤
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
}
