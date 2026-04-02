import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { motion } from "framer-motion";
import {
  IndianRupee, Users, Building2, TrendingUp, TrendingDown, AlertTriangle,
  CreditCard, ArrowUpRight, ArrowRight, Activity, UserPlus, Clock,
  ChevronRight, Zap, Shield, Crown, Eye, Package, Sparkles, Server,
  BarChart3, Globe, RefreshCw,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, PieChart, Pie, Cell,
} from "recharts";
import { Badge } from "../components/ui/badge";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });

// ── Shared Components ──

function MetricCard({ label, value, sub, icon: Icon, color, delay, onClick, badge }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
      onClick={onClick}
      className={`relative rounded-2xl p-4 border border-white/6 transition-all duration-200 ${onClick ? "cursor-pointer hover:border-white/12 hover:scale-[1.01]" : ""}`}
      style={{ background: "hsl(0, 0%, 4%)" }}
      data-testid={`metric-${label.toLowerCase().replace(/\s+/g, "-")}`}
    >
      {badge && (
        <span className="absolute top-3 right-3 px-2 py-0.5 text-[10px] font-bold rounded-full bg-amber-500/20 text-amber-400">{badge}</span>
      )}
      <div className={`w-9 h-9 rounded-xl flex items-center justify-center mb-3 ${color}`}>
        <Icon className="w-4 h-4 text-white" />
      </div>
      <p className="font-mono text-2xl font-bold text-white tracking-tight">{value}</p>
      <p className="text-xs text-zinc-500 font-medium mt-0.5">{label}</p>
      {sub && <p className="text-[10px] text-zinc-600 mt-0.5">{sub}</p>}
    </motion.div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="px-3 py-2 rounded-lg text-sm" style={{ background: "hsl(0, 0%, 5%)", border: "1px solid hsl(0, 0%, 12%)" }}>
      <p className="text-zinc-400 text-xs">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-white font-semibold">Rs. {p.value?.toLocaleString()}</p>
      ))}
    </div>
  );
}

function SectionHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <h3 className="font-heading font-semibold text-white text-sm">{title}</h3>
        {subtitle && <p className="text-[11px] text-zinc-600">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

function GlassCard({ children, className = "", delay = 0, testId }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className={`rounded-2xl border border-white/6 p-5 ${className}`}
      style={{ background: "hsl(0, 0%, 4%)" }}
      data-testid={testId}
    >
      {children}
    </motion.div>
  );
}

// ── Super Admin Control Center ──

function SuperAdminDashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API}/admin/stats`, getAuth());
      setStats(res.data);
    } catch (e) {
      console.error("Stats fetch error:", e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-28 rounded-2xl animate-pulse" style={{ background: "hsl(0, 0%, 6%)" }} />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="h-72 lg:col-span-2 rounded-2xl animate-pulse" style={{ background: "hsl(0, 0%, 6%)" }} />
          <div className="h-72 rounded-2xl animate-pulse" style={{ background: "hsl(0, 0%, 6%)" }} />
        </div>
      </div>
    );
  }

  const p = stats?.platform || {};
  const b = stats?.bot_ecosystem || {};
  const r = stats?.revenue || {};
  const t = stats?.trials || {};

  const COLORS = ["#BFFF00", "#A3E635", "#BEF264", "#10B981", "#F59E0B"];

  const formatDate = (d) => {
    if (!d) return "";
    return new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold text-white" data-testid="dashboard-title">Control Center</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
          </p>
        </div>
        <button onClick={fetchStats} className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-zinc-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg border border-white/6 transition-all" data-testid="refresh-btn">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </motion.div>

      {/* ── Platform Metrics ── */}
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-lime-400/60 mb-3 px-1">Platform Overview</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard label="Total Tenants" value={p.total_tenants || 0} sub={`${p.active_tenants || 0} active`} icon={Building2} color="bg-lime-500/20" delay={0.05} onClick={() => navigate("/dashboard/saas-management")} />
          <MetricCard label="Tenant Admins" value={p.total_tenant_admins || 0} icon={Shield} color="bg-violet-500/20" delay={0.1} />
          <MetricCard label="Platform Revenue" value={`Rs.${(p.platform_revenue || 0).toLocaleString()}`} icon={IndianRupee} color="bg-emerald-500/20" delay={0.15} />
          <MetricCard label="Pending Requests" value={p.pending_requests || 0} icon={Clock} color="bg-amber-500/20" delay={0.2} badge={p.pending_requests > 0 ? "Action" : null} onClick={() => navigate("/dashboard/admin-subs")} />
        </div>
      </div>

      {/* ── Bot Ecosystem Metrics ── */}
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-lime-400/60 mb-3 px-1">Bot Ecosystem</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard label="Total Bot Users" value={(b.total_bot_users || 0).toLocaleString()} icon={Users} color="bg-blue-500/20" delay={0.25} />
          <MetricCard label="Active Subscribers" value={(b.active_subscribers || 0).toLocaleString()} sub={`${b.expired_subscribers || 0} expired`} icon={UserPlus} color="bg-emerald-500/20" delay={0.3} />
          <MetricCard label="Tenant Revenue" value={`Rs.${(r.total_tenant_revenue || 0).toLocaleString()}`} sub={`Rs.${(r.monthly_revenue || 0).toLocaleString()} this month`} icon={TrendingUp} color="bg-lime-600/20" delay={0.35} />
          <MetricCard label="Payments" value={(b.total_payments || 0).toLocaleString()} sub={`${b.pending_payments || 0} pending`} icon={CreditCard} color="bg-cyan-500/20" delay={0.4} badge={b.pending_payments > 0 ? b.pending_payments : null} />
        </div>
      </div>

      {/* ── Charts + Top Tenants ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Revenue Chart */}
        <GlassCard className="lg:col-span-2" delay={0.3} testId="revenue-chart-platform">
          <SectionHeader title="Revenue Trend" subtitle="Last 14 days across all tenants" />
          {(r.daily_chart || []).length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={r.daily_chart}>
                <defs>
                  <linearGradient id="revGradP" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#BFFF00" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#BFFF00" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="date" tick={{ fill: "#52525B", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => v?.slice(5)} />
                <YAxis tick={{ fill: "#52525B", fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="revenue" stroke="#BFFF00" fill="url(#revGradP)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48 text-zinc-600 text-sm">No revenue data yet</div>
          )}
        </GlassCard>

        {/* Top Tenants */}
        <GlassCard delay={0.35} testId="top-tenants">
          <SectionHeader title="Top Tenants" subtitle="By revenue" />
          {(stats?.top_tenants || []).length > 0 ? (
            <div className="space-y-3">
              {stats.top_tenants.map((t, i) => (
                <div
                  key={t.tenant_id}
                  onClick={() => navigate(`/dashboard/tenant/${t.tenant_id}`)}
                  className="flex items-center gap-3 p-3 rounded-xl bg-white/3 hover:bg-white/6 cursor-pointer transition-all border border-transparent hover:border-white/8 group"
                  data-testid={`top-tenant-${i}`}
                >
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-white" style={{ background: COLORS[i % COLORS.length] + "30", color: COLORS[i % COLORS.length] }}>
                    #{i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">{t.name}</p>
                    <p className="text-[10px] text-zinc-600">{t.payment_count} payments</p>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-sm font-semibold text-white">Rs.{t.revenue.toLocaleString()}</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 transition-colors" />
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center h-40 text-zinc-600 text-sm">No tenant revenue data</div>
          )}
        </GlassCard>
      </div>

      {/* ── Recent Activity + Trial Info ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Tenants */}
        <GlassCard delay={0.4} testId="recent-tenants">
          <SectionHeader
            title="Recent Tenants"
            subtitle="Latest registered tenants"
            action={
              <button onClick={() => navigate("/dashboard/saas-management")} className="text-xs text-lime-400 hover:text-lime-300 flex items-center gap-1 transition-colors">
                View All <ArrowRight className="w-3 h-3" />
              </button>
            }
          />
          <div className="space-y-2">
            {(stats?.recent_tenants || []).map((t, i) => (
              <div
                key={t.tenant_id}
                onClick={() => navigate(`/dashboard/tenant/${t.tenant_id}`)}
                className="flex items-center gap-3 py-2.5 px-3 rounded-xl hover:bg-white/4 cursor-pointer transition-all border-b border-white/4 last:border-0 group"
                data-testid={`recent-tenant-${i}`}
              >
                <div className="w-8 h-8 rounded-lg bg-lime-500/10 flex items-center justify-center">
                  <Building2 className="w-4 h-4 text-lime-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{t.name || t.tenant_id}</p>
                  <p className="text-[10px] text-zinc-600">{t.email || ""}</p>
                </div>
                <div className="text-right">
                  <Badge className={`text-[10px] ${t.status === "active" ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-500/15 text-zinc-400"}`}>
                    {t.status}
                  </Badge>
                  <p className="text-[10px] text-zinc-600 mt-0.5">{formatDate(t.created_at)}</p>
                </div>
              </div>
            ))}
            {(stats?.recent_tenants || []).length === 0 && (
              <p className="text-zinc-600 text-sm py-4 text-center">No tenants yet</p>
            )}
          </div>
        </GlassCard>

        {/* Recent Subscriptions */}
        <GlassCard delay={0.45} testId="recent-subs">
          <SectionHeader
            title="Recent Subscription Activity"
            subtitle="Dashboard plan requests"
            action={
              <button onClick={() => navigate("/dashboard/admin-subs")} className="text-xs text-lime-400 hover:text-lime-300 flex items-center gap-1 transition-colors">
                Manage <ArrowRight className="w-3 h-3" />
              </button>
            }
          />
          <div className="space-y-2">
            {(stats?.recent_subscriptions || []).map((s, i) => (
              <div key={s.id || i} className="flex items-center gap-3 py-2.5 px-3 rounded-xl hover:bg-white/4 transition-all border-b border-white/4 last:border-0">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${s.status === "approved" ? "bg-emerald-500/10" : s.status === "pending" ? "bg-amber-500/10" : "bg-lime-500/10"}`}>
                  <CreditCard className={`w-4 h-4 ${s.status === "approved" ? "text-emerald-400" : s.status === "pending" ? "text-amber-400" : "text-lime-400"}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{s.user_name || s.user_email || "User"}</p>
                  <p className="text-[10px] text-zinc-600">{s.plan_id} - {s.status}</p>
                </div>
                <div className="text-right">
                  {s.amount > 0 && <p className="font-mono text-xs font-semibold text-white">Rs.{s.amount?.toLocaleString()}</p>}
                  <p className="text-[10px] text-zinc-600">{formatDate(s.created_at)}</p>
                </div>
              </div>
            ))}
            {(stats?.recent_subscriptions || []).length === 0 && (
              <p className="text-zinc-600 text-sm py-4 text-center">No subscriptions yet</p>
            )}
          </div>
        </GlassCard>
      </div>

      {/* ── Trial + Quick Links ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <GlassCard delay={0.5} testId="trial-status">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-violet-500/20 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-violet-400" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Trials</p>
              <p className="text-[10px] text-zinc-600">{t.enabled ? `${t.duration_days} day trials active` : "Trials disabled"}</p>
            </div>
          </div>
          <p className="font-mono text-3xl font-bold text-white">{t.total_trial_users || 0}</p>
          <p className="text-xs text-zinc-500 mt-1">Total trial users</p>
        </GlassCard>

        <GlassCard delay={0.55} testId="quick-link-analytics" className="cursor-pointer hover:border-white/12 transition-all" onClick={() => navigate("/dashboard/analytics")}>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-blue-500/20 flex items-center justify-center">
              <BarChart3 className="w-4 h-4 text-blue-400" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Analytics</p>
              <p className="text-[10px] text-zinc-600">Deep dive into data</p>
            </div>
          </div>
          <div className="flex items-center gap-1 text-xs text-zinc-500 mt-2">
            <span>Open Analytics</span>
            <ArrowRight className="w-3 h-3" />
          </div>
        </GlassCard>

        <GlassCard delay={0.6} testId="quick-link-revenue" className="cursor-pointer hover:border-white/12 transition-all" onClick={() => navigate("/dashboard/revenue")}>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/20 flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Revenue</p>
              <p className="text-[10px] text-zinc-600">Detailed revenue view</p>
            </div>
          </div>
          <div className="flex items-center gap-1 text-xs text-zinc-500 mt-2">
            <span>Open Revenue</span>
            <ArrowRight className="w-3 h-3" />
          </div>
        </GlassCard>
      </div>
    </div>
  );
}

// ── Tenant Admin Dashboard (Existing) ──

function TenantDashboard() {
  const [analytics, setAnalytics] = useState(null);
  const [revenue, setRevenue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [chartRange, setChartRange] = useState("30d");

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
          {[...Array(6)].map((_, i) => <div key={i} className="h-28 rounded-2xl animate-pulse" style={{ background: "hsl(0, 0%, 6%)" }} />)}
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
  const chartData = (r.daily_chart || []).map(d => ({ date: d.date?.slice(5) || "", revenue: d.revenue || 0 }));
  const planStats = a.plan_stats || r.plan_performance || [];
  const COLORS = ["#BFFF00", "#A3E635", "#BEF264", "#10B981", "#F59E0B", "#3B82F6"];
  const recentPayments = (a.recent_payments || []).slice(0, 5);
  const recentSubs = (a.recent_subscribers || []).slice(0, 5);

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="font-heading text-2xl font-bold text-white" data-testid="dashboard-title">Dashboard</h1>
        <p className="text-sm text-zinc-500 mt-1">
          {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        </p>
      </motion.div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <MetricCard label="Total Revenue" value={`Rs.${totalRevenue.toLocaleString()}`} icon={IndianRupee} color="bg-lime-500/20" delay={0.05} />
        <MetricCard label="Monthly Revenue" value={`Rs.${monthlyRevenue.toLocaleString()}`} icon={TrendingUp} color="bg-lime-600/20" delay={0.1} />
        <MetricCard label="Active Subs" value={activeSubs.toLocaleString()} icon={Users} color="bg-emerald-500/20" delay={0.15} />
        <MetricCard label="Total Users" value={totalSubs.toLocaleString()} icon={UserPlus} color="bg-amber-500/20" delay={0.2} />
        <MetricCard label="Churn Rate" value={`${churnRate}%`} icon={Activity} color="bg-blue-500/20" delay={0.25} />
        <MetricCard label="Expired" value={failedPayments.toLocaleString()} icon={AlertTriangle} color="bg-zinc-500/20" delay={0.3} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <GlassCard className="lg:col-span-2" delay={0.2} testId="revenue-chart">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-heading font-semibold text-white text-sm">Revenue</h3>
              <p className="text-[11px] text-zinc-600">Last 30 days</p>
            </div>
            <div className="flex gap-1 bg-white/5 rounded-lg p-0.5">
              {["7d", "30d", "90d"].map(range => (
                <button key={range} onClick={() => setChartRange(range)} className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${chartRange === range ? "bg-lime-600 text-white" : "text-zinc-500 hover:text-zinc-300"}`} data-testid={`chart-range-${range}`}>
                  {range}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={chartRange === "7d" ? chartData.slice(-7) : chartData}>
              <defs>
                <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#BFFF00" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#BFFF00" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="date" tick={{ fill: "#52525B", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#52525B", fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="revenue" stroke="#BFFF00" fill="url(#revGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </GlassCard>

        <GlassCard delay={0.3} testId="plan-distribution">
          <h3 className="font-heading font-semibold text-white text-sm mb-4">Plan Distribution</h3>
          {planStats.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie data={planStats} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="count" nameKey="name">
                    {planStats.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2 mt-2">
                {planStats.slice(0, 4).map((p, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                      <span className="text-zinc-400 truncate max-w-[100px]">{p.name}</span>
                    </div>
                    <span className="text-white font-mono font-semibold">{p.count || p.sales || 0}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-40 text-zinc-600 text-sm">No plan data</div>
          )}
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GlassCard delay={0.35} testId="recent-activity">
          <SectionHeader title="Recent Activity" />
          <div className="space-y-2">
            {recentPayments.length > 0 ? recentPayments.map((p, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-white/4 last:border-0">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${p.status === "verified" ? "bg-emerald-500/10" : p.status === "pending" ? "bg-amber-500/10" : "bg-lime-500/10"}`}>
                    <CreditCard className={`w-4 h-4 ${p.status === "verified" ? "text-emerald-400" : p.status === "pending" ? "text-amber-400" : "text-lime-400"}`} />
                  </div>
                  <div>
                    <p className="text-sm text-white font-medium">{p.telegram_username || p.telegram_user_id || "User"}</p>
                    <p className="text-xs text-zinc-600">{p.plan_name || "Payment"} - {p.status}</p>
                  </div>
                </div>
                <span className="text-sm font-mono font-semibold text-white">Rs.{(p.amount || 0).toLocaleString()}</span>
              </div>
            )) : (
              <p className="text-zinc-600 text-sm py-4 text-center">No recent activity</p>
            )}
          </div>
        </GlassCard>

        <GlassCard delay={0.4} testId="new-subscribers">
          <SectionHeader title="New Subscribers" />
          <div className="space-y-2">
            {recentSubs.length > 0 ? recentSubs.map((s, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-white/4 last:border-0">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-lime-500/10 flex items-center justify-center">
                    <UserPlus className="w-4 h-4 text-lime-400" />
                  </div>
                  <div>
                    <p className="text-sm text-white font-medium">{s.telegram_username || s.telegram_user_id || "User"}</p>
                    <p className="text-xs text-zinc-600">{s.plan_name || "Plan"}</p>
                  </div>
                </div>
                <Badge className={`text-[10px] ${s.status === "active" ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-500/15 text-zinc-400"}`}>
                  {s.status}
                </Badge>
              </div>
            )) : (
              <p className="text-zinc-600 text-sm py-2 text-center">No recent subscribers</p>
            )}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}

// ── Main Export ──

export default function Dashboard() {
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const isSuperAdmin = user.role === "super_admin";

  return isSuperAdmin ? <SuperAdminDashboard /> : <TenantDashboard />;
}
