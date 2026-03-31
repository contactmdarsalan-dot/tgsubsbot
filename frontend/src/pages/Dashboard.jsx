import { useState, useEffect } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import {
  IndianRupee, Users, Building2, TrendingUp, TrendingDown, AlertTriangle,
  CreditCard, ArrowUpRight, ArrowRight, Activity, UserPlus, Clock,
  ChevronRight, Zap, Shield,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, PieChart, Pie, Cell,
} from "recharts";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });

function Skeleton({ className }) {
  return <div className={`skeleton ${className}`} />;
}

function MetricCard({ label, value, change, changeType, icon: Icon, color, delay, onClick }) {
  const isPositive = changeType === "positive";
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      className="metric-card cursor-pointer group"
      onClick={onClick}
      data-testid={`metric-${label.toLowerCase().replace(/\s+/g, "-")}`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
        {change !== undefined && (
          <div className={`flex items-center gap-1 text-xs font-semibold ${isPositive ? "text-emerald-400" : "text-rose-400"}`}>
            {isPositive ? <ArrowUpRight className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            {change}%
          </div>
        )}
      </div>
      <p className="font-mono text-2xl font-bold text-white tracking-tight">{value}</p>
      <p className="text-xs text-zinc-500 font-medium mt-1">{label}</p>
    </motion.div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-card px-3 py-2 rounded-lg text-sm" style={{ background: "hsl(340,40%,7%)", border: "1px solid hsl(340,40%,15%)" }}>
      <p className="text-zinc-400 text-xs">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-white font-semibold">Rs. {p.value?.toLocaleString()}</p>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [analytics, setAnalytics] = useState(null);
  const [revenue, setRevenue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [chartRange, setChartRange] = useState("30d");
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const isSuperAdmin = user.role === "super_admin";

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [analyticsRes, revenueRes] = await Promise.all([
          axios.get(`${API}/analytics`, getAuth()),
          axios.get(`${API}/analytics/revenue`, getAuth()).catch(() => ({ data: null })),
        ]);
        setAnalytics(analyticsRes.data);
        setRevenue(revenueRes.data);
      } catch (e) {
        console.error("Dashboard fetch error:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-28" />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Skeleton className="h-80 lg:col-span-2" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  }

  const a = analytics || {};
  const r = revenue || {};

  const totalRevenue = r.total_revenue || a.total_revenue || 0;
  const monthlyRevenue = r.monthly_revenue || a.monthly_revenue || 0;
  const activeSubs = r.active_subscribers || a.active_subscribers || 0;
  const totalSubs = a.total_subscribers || 0;
  const churnRate = r.churn_rate || 0;
  const failedPayments = a.expired_subscribers || 0;
  const revenueGrowth = r.revenue_growth || 0;

  const chartData = (r.daily_chart || []).map(d => ({
    date: d.date?.slice(5) || "",
    revenue: d.revenue || 0,
  }));

  const planStats = a.plan_stats || r.plan_performance || [];
  const COLORS = ["#E11D48", "#F43F5E", "#FB7185", "#10B981", "#F59E0B", "#3B82F6"];

  const recentPayments = (a.recent_payments || []).slice(0, 5);
  const recentSubs = (a.recent_subscribers || []).slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <h1 className="font-heading text-2xl font-bold text-white" data-testid="dashboard-title">
          {isSuperAdmin ? "Control Center" : "Dashboard"}
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        </p>
      </motion.div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <MetricCard label="Total Revenue" value={`Rs.${totalRevenue.toLocaleString()}`} change={Math.abs(revenueGrowth)} changeType={revenueGrowth >= 0 ? "positive" : "negative"} icon={IndianRupee} color="bg-rose-500/20" delay={0.05} />
        <MetricCard label="Monthly Revenue" value={`Rs.${monthlyRevenue.toLocaleString()}`} icon={TrendingUp} color="bg-rose-600/20" delay={0.1} />
        <MetricCard label="Active Subs" value={activeSubs.toLocaleString()} icon={Users} color="bg-emerald-500/20" delay={0.15} />
        <MetricCard label="Total Users" value={totalSubs.toLocaleString()} icon={UserPlus} color="bg-amber-500/20" delay={0.2} />
        <MetricCard label="Churn Rate" value={`${churnRate}%`} changeType={churnRate > 10 ? "negative" : "positive"} icon={Activity} color="bg-blue-500/20" delay={0.25} />
        <MetricCard label="Expired" value={failedPayments.toLocaleString()} icon={AlertTriangle} color="bg-zinc-500/20" delay={0.3} />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Revenue Chart */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="lg:col-span-2 glass-card rounded-2xl p-5" data-testid="revenue-chart">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-heading font-semibold text-white">Revenue</h3>
              <p className="text-xs text-zinc-500">Last 30 days</p>
            </div>
            <div className="flex gap-1 bg-white/5 rounded-lg p-0.5">
              {["7d", "30d", "90d"].map(r => (
                <button key={r} onClick={() => setChartRange(r)} className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${chartRange === r ? "bg-rose-600 text-white" : "text-zinc-500 hover:text-zinc-300"}`} data-testid={`chart-range-${r}`}>
                  {r}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={chartRange === "7d" ? chartData.slice(-7) : chartRange === "90d" ? chartData : chartData}>
              <defs>
                <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#E11D48" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#E11D48" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="date" tick={{ fill: "#71717A", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#71717A", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="revenue" stroke="#E11D48" fill="url(#revGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Plan Distribution */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="glass-card rounded-2xl p-5" data-testid="plan-distribution">
          <h3 className="font-heading font-semibold text-white mb-4">Plan Distribution</h3>
          {planStats.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={planStats} cx="50%" cy="50%" innerRadius={50} outerRadius={75} paddingAngle={3} dataKey="count" nameKey="name">
                    {planStats.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip content={({ active, payload }) => active && payload?.[0] ? (
                    <div className="px-3 py-2 rounded-lg text-sm" style={{ background: "hsl(340,40%,7%)", border: "1px solid hsl(340,40%,15%)" }}>
                      <p className="text-white font-semibold">{payload[0].name}: {payload[0].value}</p>
                    </div>
                  ) : null} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2 mt-2">
                {planStats.slice(0, 4).map((p, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                      <span className="text-zinc-400 truncate max-w-[120px]">{p.name}</span>
                    </div>
                    <span className="text-white font-mono font-semibold">{p.count || p.sales || 0}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-40 text-zinc-600 text-sm">No plan data</div>
          )}
        </motion.div>
      </div>

      {/* Bottom Row: Recent Activity + Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }} className="glass-card rounded-2xl p-5" data-testid="recent-activity">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-heading font-semibold text-white">Recent Activity</h3>
            <Activity className="w-4 h-4 text-zinc-500" />
          </div>
          <div className="space-y-3">
            {recentPayments.length > 0 ? recentPayments.map((p, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${p.status === "verified" ? "bg-emerald-500/15" : p.status === "pending" ? "bg-amber-500/15" : "bg-rose-500/15"}`}>
                    <CreditCard className={`w-4 h-4 ${p.status === "verified" ? "text-emerald-400" : p.status === "pending" ? "text-amber-400" : "text-rose-400"}`} />
                  </div>
                  <div>
                    <p className="text-sm text-white font-medium">{p.telegram_username || p.telegram_user_id || "User"}</p>
                    <p className="text-xs text-zinc-500">{p.plan_name || "Payment"} - {p.status}</p>
                  </div>
                </div>
                <span className="text-sm font-mono font-semibold text-white">Rs.{(p.amount || 0).toLocaleString()}</span>
              </div>
            )) : (
              <p className="text-zinc-600 text-sm py-4 text-center">No recent activity</p>
            )}
          </div>
        </motion.div>

        {/* Quick Stats / Alerts */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="glass-card rounded-2xl p-5" data-testid="alerts-panel">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-heading font-semibold text-white">Quick Stats</h3>
            <Shield className="w-4 h-4 text-zinc-500" />
          </div>
          <div className="space-y-3">
            {/* Recent Subscribers */}
            <div className="mb-4">
              <p className="text-xs font-bold uppercase tracking-[0.15em] text-zinc-600 mb-2">New Subscribers</p>
              {recentSubs.length > 0 ? recentSubs.map((s, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-rose-500/15 flex items-center justify-center">
                      <UserPlus className="w-4 h-4 text-rose-400" />
                    </div>
                    <div>
                      <p className="text-sm text-white font-medium">{s.telegram_username || s.telegram_user_id || "User"}</p>
                      <p className="text-xs text-zinc-500">{s.plan_name || "Plan"}</p>
                    </div>
                  </div>
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${s.status === "active" ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-500/15 text-zinc-400"}`}>
                    {s.status}
                  </span>
                </div>
              )) : (
                <p className="text-zinc-600 text-sm py-2">No recent subscribers</p>
              )}
            </div>

            {/* Key metrics summary */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white/5 rounded-xl p-3">
                <p className="text-xs text-zinc-500">ARPU</p>
                <p className="font-mono text-lg font-bold text-white">Rs.{(r.arpu || 0).toLocaleString()}</p>
              </div>
              <div className="bg-white/5 rounded-xl p-3">
                <p className="text-xs text-zinc-500">LTV</p>
                <p className="font-mono text-lg font-bold text-white">Rs.{(r.ltv || 0).toLocaleString()}</p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
