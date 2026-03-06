import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import NavBar from "@/components/NavBar";
import { Toaster } from "react-hot-toast";
import ChatWidget from "@/features/chatbot/ChatWidget";
import PublicAuthGuard from "@/components/PublicAuthGuard";

export const metadata: Metadata = {
  title: "JanVedha AI — Smart Civic Issue Management",
  description:
    "AI-powered civic complaint management. Submit issues, track resolutions, and hold local governance accountable.",
  keywords: "civic issues, complaints, ward, municipality, AI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-gray-900 antialiased">
        <AuthProvider>
          <PublicAuthGuard>
            <NavBar />
            <main>{children}</main>
            <ChatWidget />
            <Toaster
              position="top-right"
              toastOptions={{
                className: "!text-sm !font-medium !rounded-xl !shadow-lg",
                success: { iconTheme: { primary: "#16a34a", secondary: "#fff" } },
                error: { iconTheme: { primary: "#dc2626", secondary: "#fff" } },
              }}
            />
          </PublicAuthGuard>
        </AuthProvider>
      </body>
    </html>
  );
}
