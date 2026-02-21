import Link from 'next/link';
import { Home, ListTodo, MapPin, Users, Settings, LogOut } from 'lucide-react';

export function Sidebar() {
    return (
        <div className="w-64 h-screen glass-panel border-r border-white/10 flex flex-col fixed left-0 top-0">
            <div className="p-6">
                <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                    Janvedha AI
                </h1>
                <p className="text-xs text-muted-foreground mt-1">Command Center</p>
            </div>

            <nav className="flex-1 px-4 space-y-2 mt-4">
                <Link href="/" className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/5 text-foreground font-medium transition-colors">
                    <Home className="w-5 h-5 text-primary" />
                    Dashboard
                </Link>
                <Link href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-muted-foreground hover:text-foreground font-medium transition-colors">
                    <ListTodo className="w-5 h-5" />
                    Tickets
                </Link>
                <Link href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-muted-foreground hover:text-foreground font-medium transition-colors">
                    <MapPin className="w-5 h-5" />
                    Live Map
                </Link>
                <Link href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-muted-foreground hover:text-foreground font-medium transition-colors">
                    <Users className="w-5 h-5" />
                    Public Sentiment
                </Link>
            </nav>

            <div className="p-4 border-t border-white/5 mt-auto">
                <Link href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-muted-foreground hover:text-foreground font-medium transition-colors">
                    <Settings className="w-5 h-5" />
                    Settings
                </Link>
                <button className="w-full flex items-center gap-3 px-3 py-2 mt-1 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive font-medium transition-colors">
                    <LogOut className="w-5 h-5" />
                    Logout
                </button>
            </div>
        </div>
    );
}
