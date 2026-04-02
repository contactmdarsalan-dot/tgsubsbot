import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Activity,
  RefreshCcw,
  Terminal,
  CreditCard,
  MessageSquare,
  MousePointer,
  Image,
  Users,
  Search,
  Download,
} from "lucide-react";
import { PulseDot } from "../components/ui/sera-ui";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

const EVENT_CONFIG = {
  command: { label: "Command", icon: Terminal, color: "text-blue-400", bg: "bg-blue-500/10" },
  callback: { label: "Button Click", icon: MousePointer, color: "text-violet-400", bg: "bg-violet-500/10" },
  message: { label: "Message", icon: MessageSquare, color: "text-gray-400", bg: "bg-gray-500/10" },
  payment_screenshot: { label: "Payment Screenshot", icon: CreditCard, color: "text-amber-400", bg: "bg-amber-500/10" },
  payment_verified: { label: "Payment Verified", icon: CreditCard, color: "text-emerald-400", bg: "bg-emerald-500/10" },
  new_subscriber: { label: "New Subscriber", icon: Users, color: "text-lime-400", bg: "bg-lime-500/10" },
  photo: { label: "Photo", icon: Image, color: "text-cyan-400", bg: "bg-cyan-500/10" },
};

function timeAgo(dateStr) {
  const now = new Date();
  const past = new Date(dateStr);
  const diff = Math.floor((now - past) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function BotActivityLogs() {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (filter) params.set("event_type", filter);
      
      const [logsRes, statsRes] = await Promise.all([
        axios.get(`${API}/bot-activity?${params}`, getAuthHeaders()),
        axios.get(`${API}/bot-activity/stats`, getAuthHeaders()),
      ]);
      setLogs(logsRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error("Failed to fetch bot activity:", error);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchData]);

  const filteredLogs = search
    ? logs.filter(l =>
        l.details?.toLowerCase().includes(search.toLowerCase()) ||
        l.telegram_username?.toLowerCase().includes(search.toLowerCase()) ||
        l.telegram_user_id?.includes(search)
      )
    : logs;

  const handleExport = () => {
    const csv = "Time,Event,User ID,Username,Details\n" +
      filteredLogs.map(l =>
        `${l.created_at},${l.event_type},${l.telegram_user_id},${l.telegram_username},${(l.details || "").replace(/,/g, ";")}`
      ).join("\n");
    
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bot-activity-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="bot-activity-page">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-col md:flex-row md:items-center justify-between gap-4"
      >
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-serif text-4xl font-semibold tracking-tight">Bot Activity</h1>
            {autoRefresh && <PulseDot color="emerald" />}
          </div>
          <p className="text-muted-foreground mt-1">Real-time bot interactions & webhook logs</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleExport} data-testid="export-activity-btn">
            <Download className="w-4 h-4 mr-1.5" />
            Export CSV
          </Button>
          <Button
            variant={autoRefresh ? "default" : "outline"}
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
            data-testid="auto-refresh-toggle"
          >
            <RefreshCcw className={`w-4 h-4 mr-1.5 ${autoRefresh ? "animate-spin" : ""}`} />
            {autoRefresh ? "Live" : "Auto-Refresh"}
          </Button>
        </div>
      </motion.div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
            className="rounded-xl bg-card border border-border/50 p-4">
            <p className="text-xs text-muted-foreground">Last 24h Events</p>
            <p className="font-serif text-2xl font-bold mt-1">{stats.total_24h}</p>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
            className="rounded-xl bg-card border border-border/50 p-4">
            <p className="text-xs text-muted-foreground">Active Users 24h</p>
            <p className="font-serif text-2xl font-bold text-emerald-500 mt-1">{stats.active_users_24h}</p>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
            className="rounded-xl bg-card border border-border/50 p-4">
            <p className="text-xs text-muted-foreground">Commands 24h</p>
            <p className="font-serif text-2xl font-bold text-blue-400 mt-1">{stats.by_type?.command || 0}</p>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
            className="rounded-xl bg-card border border-border/50 p-4">
            <p className="text-xs text-muted-foreground">Payments 24h</p>
            <p className="font-serif text-2xl font-bold text-amber-400 mt-1">{stats.by_type?.payment_screenshot || 0}</p>
          </motion.div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search by username, ID, or details..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 bg-muted/50 border-transparent"
            data-testid="search-activity"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {[
            { key: "", label: "All" },
            { key: "command", label: "Commands" },
            { key: "callback", label: "Buttons" },
            { key: "payment_screenshot", label: "Payments" },
            { key: "message", label: "Messages" },
          ].map((f) => (
            <Button
              key={f.key}
              variant={filter === f.key ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter(f.key)}
              className="text-xs"
              data-testid={`filter-${f.key || "all"}`}
            >
              {f.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Activity Feed */}
      <div className="space-y-1.5">
        {filteredLogs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/50 p-12 text-center">
            <Activity className="w-12 h-12 text-muted-foreground/50 mx-auto mb-4" />
            <p className="text-lg font-medium text-muted-foreground">No bot activity yet</p>
            <p className="text-sm text-muted-foreground/70 mt-2 max-w-md mx-auto">
              Activity logs appear when users interact with the bot. Deploy latest code to production first — "Save to Github" then redeploy on Coolify.
            </p>
            <Button variant="outline" size="sm" className="mt-4" onClick={fetchData} data-testid="refresh-activity">
              <RefreshCcw className="w-4 h-4 mr-1.5" /> Refresh
            </Button>
          </div>
        ) : (
          filteredLogs.map((log, i) => {
            const config = EVENT_CONFIG[log.event_type] || EVENT_CONFIG.message;
            const Icon = config.icon;
            return (
              <motion.div
                key={log.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: Math.min(i * 0.02, 0.5) }}
                className="flex items-center gap-3 rounded-lg bg-card/50 hover:bg-card border border-transparent hover:border-border/30 px-4 py-2.5 transition-all"
                data-testid={`activity-log-${log.id}`}
              >
                <div className={`w-8 h-8 rounded-lg ${config.bg} flex items-center justify-center flex-shrink-0`}>
                  <Icon className={`w-4 h-4 ${config.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">
                      {log.telegram_username ? `@${log.telegram_username}` : log.telegram_user_id || "Unknown"}
                    </span>
                    <Badge variant="outline" className={`text-[10px] ${config.color} border-current/20`}>
                      {config.label}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground truncate mt-0.5">
                    {log.details || "-"}
                  </p>
                </div>
                <span className="text-xs text-muted-foreground/70 flex-shrink-0">
                  {timeAgo(log.created_at)}
                </span>
              </motion.div>
            );
          })
        )}
      </div>
    </div>
  );
}
