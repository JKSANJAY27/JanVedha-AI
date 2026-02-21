import { Sidebar } from "@/components/Sidebar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CheckCircle, AlertTriangle, Clock, TrendingUp } from "lucide-react";

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-background text-foreground flex">
      <Sidebar />

      <main className="flex-1 ml-64 p-8 overflow-y-auto">
        <header className="flex justify-between items-center mb-8">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Executive Dashboard</h2>
            <p className="text-muted-foreground mt-1">Real-time civic status and SLA tracking</p>
          </div>
          <div className="flex items-center gap-4">
            <Button variant="secondary" className="glass-panel">
              Generate Standing Report
            </Button>
            <div className="flex items-center gap-2 px-3 py-1.5 glass-panel rounded-full">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
              <span className="text-sm font-medium">Live Data</span>
            </div>
          </div>
        </header>

        {/* Top KPI Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card className="hover:-translate-y-1">
            <CardContent className="p-6 flex items-center gap-4">
              <div className="p-3 bg-red-500/10 text-red-500 rounded-lg">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Critical SLAs Breached</p>
                <h3 className="text-2xl font-bold mt-1">14</h3>
              </div>
            </CardContent>
          </Card>
          <Card className="hover:-translate-y-1">
            <CardContent className="p-6 flex items-center gap-4">
              <div className="p-3 bg-yellow-500/10 text-yellow-500 rounded-lg">
                <Clock className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Open Tickets</p>
                <h3 className="text-2xl font-bold mt-1">842</h3>
              </div>
            </CardContent>
          </Card>
          <Card className="hover:-translate-y-1">
            <CardContent className="p-6 flex items-center gap-4">
              <div className="p-3 bg-green-500/10 text-green-500 rounded-lg">
                <CheckCircle className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Resolved (Today)</p>
                <h3 className="text-2xl font-bold mt-1">156</h3>
              </div>
            </CardContent>
          </Card>
          <Card className="hover:-translate-y-1">
            <CardContent className="p-6 flex items-center gap-4">
              <div className="p-3 bg-blue-500/10 text-blue-500 rounded-lg">
                <TrendingUp className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Avg Public Sentiment</p>
                <h3 className="text-2xl font-bold mt-1">72%</h3>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Dashboard Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

          {/* Active High Priority List */}
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>High Priority Action Queue</CardTitle>
              <Button variant="ghost" className="text-sm">View All</Button>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-white/5">
                {/* Mock Item 1 */}
                <div className="p-4 flex items-center justify-between hover:bg-white/5 transition-colors">
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-foreground">#CIV-2026-04901</span>
                      <Badge variant="critical">92 pts (Critical)</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">Huge pothole on Main Road causing traffic blockage.</p>
                    <div className="flex gap-4 mt-2 text-xs text-muted-foreground font-medium">
                      <span>Ward 42</span>
                      <span>•</span>
                      <span>Dept: Roads</span>
                      <span>•</span>
                      <span className="text-red-400">SLA: Breached (2h ago)</span>
                    </div>
                  </div>
                  <Button variant="primary">Verify Work</Button>
                </div>
                {/* Mock Item 2 */}
                <div className="p-4 flex items-center justify-between hover:bg-white/5 transition-colors">
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-foreground">#CIV-2026-04889</span>
                      <Badge variant="high">76 pts (High)</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">Streetlights out on 4th Avenue near the school.</p>
                    <div className="flex gap-4 mt-2 text-xs text-muted-foreground font-medium">
                      <span>Ward 14</span>
                      <span>•</span>
                      <span>Dept: Electrical</span>
                      <span>•</span>
                      <span className="text-yellow-400">SLA: 4h remain</span>
                    </div>
                  </div>
                  <Button variant="secondary">Assign</Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Ward Performance Leaderboard */}
          <Card>
            <CardHeader>
              <CardTitle>Ward Performance Tracker</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-white/5">
                <div className="p-4 flex items-center justify-between">
                  <div>
                    <p className="font-medium text-foreground">Ward 42 (Zone Center)</p>
                    <p className="text-xs text-muted-foreground">Officer: Ramesh K.</p>
                  </div>
                  <div className="text-right">
                    <p className="text-emerald-500 font-bold">94%</p>
                    <p className="text-xs text-muted-foreground">SLA Met</p>
                  </div>
                </div>
                <div className="p-4 flex items-center justify-between bg-red-500/5">
                  <div>
                    <p className="font-medium text-foreground text-red-400">Ward 14 (Zone North)</p>
                    <p className="text-xs text-red-400/70">Officer: Sunita M.</p>
                  </div>
                  <div className="text-right">
                    <p className="text-red-500 font-bold">61%</p>
                    <p className="text-xs text-red-500/70">SLA Met</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

        </div>
      </main>
    </div>
  );
}
