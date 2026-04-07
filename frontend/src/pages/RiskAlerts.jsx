import { useState, useEffect } from "react";
import { AlertTriangle, ShieldAlert, Info, XCircle, Activity, TrendingDown, Clock, CheckCircle, Search } from "lucide-react";
import { Button } from "../components/ui/button";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;

const severityConfig = {
  critical: { bg: "bg-red-500/10", border: "border-red-500/30", text: "text-red-400", icon: ShieldAlert, label: "CRITICAL" },
  warning: { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-400", icon: AlertTriangle, label: "WARNING" },
  info: { bg: "bg-blue-500/10", border: "border-blue-500/30", text: "text-blue-400", icon: Info, label: "INFO" },
};

const typeConfig = {
  high_refund_rate: { icon: TrendingDown, label: "High Refund Rate" },
  failed_payments_spike: { icon: XCircle, label: "Failed Payments Spike" },
  abandoned_bot: { icon: Clock, label: "Abandoned Bot" },
  unusual_volume: { icon: Activity, label: "Unusual Volume" },
  expiry_wave: { icon: Clock, label: "Expiry Wave" },
};

export default function RiskAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState({ total: 0, critical_count: 0, warning_count: 0, info_count: 0 });
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const token = localStorage.getItem("token");

  const fetchAlerts = async () => {
    try {
      const res = await fetch(`${API}/api/saas/risk-alerts`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to fetch alerts");
      const data = await res.json();
      setAlerts(data.alerts || []);
      setStats({ total: data.total, critical_count: data.critical_count, warning_count: data.warning_count, info_count: data.info_count });
    } catch (err) {
      toast.error("Failed to load risk alerts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAlerts(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const dismissAlert = async (alertId) => {
    try {
      const res = await fetch(`${API}/api/saas/risk-alerts/${alertId}/dismiss`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "Acknowledged by admin" }),
      });
      if (!res.ok) throw new Error("Failed");
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
      toast.success("Alert dismissed");
    } catch {
      toast.error("Failed to dismiss alert");
    }
  };

  const filtered = alerts.filter((a) => {
    if (filter !== "all" && a.severity !== filter) return false;
    if (search && !a.tenant_name.toLowerCase().includes(search.toLowerCase()) && !a.message.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-lime-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="risk-alerts-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Risk & Alerts</h1>
          <p className="text-sm text-zinc-500 mt-1">Platform-wide fraud detection and anomaly monitoring</p>
        </div>
        <Button onClick={fetchAlerts} variant="outline" size="sm" className="border-white/10 text-zinc-300 hover:text-white" data-testid="refresh-alerts-btn">
          <Activity className="w-4 h-4 mr-2" /> Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Total Alerts", value: stats.total, color: "text-white", bg: "bg-white/5" },
          { label: "Critical", value: stats.critical_count, color: "text-red-400", bg: "bg-red-500/10" },
          { label: "Warnings", value: stats.warning_count, color: "text-amber-400", bg: "bg-amber-500/10" },
          { label: "Info", value: stats.info_count, color: "text-blue-400", bg: "bg-blue-500/10" },
        ].map((s) => (
          <div key={s.label} className={`${s.bg} rounded-xl border border-white/6 p-4`} data-testid={`stat-${s.label.toLowerCase().replace(/\s/g, "-")}`}>
            <p className="text-xs text-zinc-500 uppercase tracking-wider">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color} mt-1`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            placeholder="Search alerts..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-lime-500/50"
            data-testid="alert-search"
          />
        </div>
        {["all", "critical", "warning", "info"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            data-testid={`filter-${f}`}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              filter === f ? "bg-lime-500/20 text-lime-400 border border-lime-500/30" : "bg-white/5 text-zinc-400 border border-white/6 hover:text-white"
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Alert List */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 bg-white/[0.02] rounded-2xl border border-white/6">
          <CheckCircle className="w-12 h-12 text-emerald-500/50 mx-auto mb-3" />
          <p className="text-zinc-400 text-sm">No alerts found. Platform is healthy!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((alert) => {
            const sev = severityConfig[alert.severity] || severityConfig.info;
            const typeConf = typeConfig[alert.type] || { icon: Info, label: alert.type };
            const TypeIcon = typeConf.icon;
            const SevIcon = sev.icon;
            return (
              <div
                key={alert.id}
                className={`${sev.bg} border ${sev.border} rounded-xl p-4 flex items-start gap-4 group`}
                data-testid={`alert-${alert.id}`}
              >
                <div className={`w-10 h-10 rounded-lg ${sev.bg} flex items-center justify-center flex-shrink-0`}>
                  <SevIcon className={`w-5 h-5 ${sev.text}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] font-bold uppercase tracking-wider ${sev.text}`}>{sev.label}</span>
                    <span className="text-zinc-600">|</span>
                    <span className="text-xs text-zinc-400 flex items-center gap-1">
                      <TypeIcon className="w-3 h-3" /> {typeConf.label}
                    </span>
                  </div>
                  <p className="text-sm text-white font-medium">{alert.message}</p>
                  <p className="text-xs text-zinc-500 mt-1">Tenant: <span className="text-zinc-300">{alert.tenant_name}</span></p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => dismissAlert(alert.id)}
                  className="text-zinc-500 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  data-testid={`dismiss-${alert.id}`}
                >
                  Dismiss
                </Button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
