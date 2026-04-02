import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { motion } from "framer-motion";
import {
  ArrowLeft, Building2, Users, IndianRupee, CreditCard, Shield, Package,
  UserPlus, TrendingUp, Clock, CheckCircle, XCircle, Radio, Copy, Eye,
  ChevronRight, Mail, Globe, Activity, AlertTriangle, RefreshCw,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";
import { Badge } from "../components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "../components/ui/table";
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from "../components/ui/tabs";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });

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

function StatBlock({ label, value, icon: Icon, color, sub }) {
  return (
    <div className="p-3 rounded-xl bg-white/3 border border-white/5">
      <div className="flex items-center gap-2 mb-1">
        <div className={`w-6 h-6 rounded-md flex items-center justify-center ${color}`}>
          <Icon className="w-3 h-3 text-white" />
        </div>
        <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">{label}</span>
      </div>
      <p className="font-mono text-xl font-bold text-white">{value}</p>
      {sub && <p className="text-[10px] text-zinc-600 mt-0.5">{sub}</p>}
    </div>
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

const COLORS = ["#BFFF00", "#A3E635", "#BEF264", "#10B981", "#F59E0B", "#3B82F6"];

const formatDate = (d) => {
  if (!d) return "-";
  return new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
};

const formatDateTime = (d) => {
  if (!d) return "-";
  return new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
};

const copyToClipboard = (text) => {
  navigator.clipboard.writeText(text);
  toast.success("Copied to clipboard");
};

export default function TenantProfile() {
  const { tenantId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    fetchProfile();
  }, [tenantId]);

  const fetchProfile = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/tenant-profile/${tenantId}`, getAuth());
      setData(res.data);
    } catch (e) {
      console.error("Tenant profile error:", e);
      toast.error("Failed to load tenant profile");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-48 rounded-xl animate-pulse" style={{ background: "hsl(0, 0%, 6%)" }} />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[...Array(8)].map((_, i) => <div key={i} className="h-24 rounded-xl animate-pulse" style={{ background: "hsl(0, 0%, 6%)" }} />)}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <AlertTriangle className="w-12 h-12 text-lime-400 mb-4" />
        <p className="text-white text-lg font-semibold">Tenant not found</p>
        <button onClick={() => navigate("/dashboard/saas-management")} className="mt-4 text-sm text-lime-400 hover:text-lime-300 flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" /> Back to Tenants
        </button>
      </div>
    );
  }

  const { tenant, stats, dashboard_admins, telegram_admins, plans, subscribers, recent_payments, revenue_chart, plan_distribution } = data;

  return (
    <div className="space-y-6" data-testid="tenant-profile">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate("/dashboard/saas-management")} className="w-9 h-9 rounded-xl bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors" data-testid="back-btn">
            <ArrowLeft className="w-4 h-4 text-zinc-400" />
          </button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-heading text-2xl font-bold text-white" data-testid="tenant-name">{tenant.name || tenant.tenant_id}</h1>
              <Badge className={`text-[10px] ${tenant.status === "active" ? "bg-emerald-500/15 text-emerald-400" : "bg-lime-500/15 text-lime-400"}`}>
                {tenant.status}
              </Badge>
            </div>
            <div className="flex items-center gap-4 mt-1">
              {tenant.email && <span className="text-xs text-zinc-500 flex items-center gap-1"><Mail className="w-3 h-3" /> {tenant.email}</span>}
              <span
                className="text-xs text-zinc-600 font-mono cursor-pointer hover:text-zinc-400 flex items-center gap-1 transition-colors"
                onClick={() => copyToClipboard(tenant.tenant_id)}
                data-testid="tenant-id-copy"
              >
                {tenant.tenant_id} <Copy className="w-3 h-3" />
              </span>
            </div>
          </div>
        </div>
        <button onClick={fetchProfile} className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-zinc-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg border border-white/6 transition-all" data-testid="refresh-profile">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </motion.div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatBlock label="Total Revenue" value={`Rs.${(stats.total_revenue || 0).toLocaleString()}`} icon={IndianRupee} color="bg-lime-500/20" sub={`Rs.${(stats.monthly_revenue || 0).toLocaleString()} this month`} />
        <StatBlock label="Bot Users" value={stats.bot_users || 0} icon={Users} color="bg-blue-500/20" />
        <StatBlock label="Active Subs" value={stats.active_subscribers || 0} icon={UserPlus} color="bg-emerald-500/20" sub={`${stats.expired_subscribers || 0} expired`} />
        <StatBlock label="Payments" value={stats.total_payments || 0} icon={CreditCard} color="bg-cyan-500/20" sub={`${stats.pending_payments || 0} pending`} />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatBlock label="Plans" value={stats.total_plans || 0} icon={Package} color="bg-violet-500/20" />
        <StatBlock label="Broadcasts" value={stats.total_broadcasts || 0} icon={Radio} color="bg-amber-500/20" />
        <StatBlock label="Dashboard Admins" value={dashboard_admins?.length || 0} icon={Shield} color="bg-indigo-500/20" />
        <StatBlock label="TG Admins" value={telegram_admins?.length || 0} icon={Activity} color="bg-teal-500/20" />
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-white/5 border border-white/6 p-1 rounded-xl">
          <TabsTrigger value="overview" className="data-[state=active]:bg-lime-500/20 data-[state=active]:text-white text-zinc-500 rounded-lg text-xs" data-testid="tab-overview">Overview</TabsTrigger>
          <TabsTrigger value="subscribers" className="data-[state=active]:bg-lime-500/20 data-[state=active]:text-white text-zinc-500 rounded-lg text-xs" data-testid="tab-subscribers">Subscribers</TabsTrigger>
          <TabsTrigger value="payments" className="data-[state=active]:bg-lime-500/20 data-[state=active]:text-white text-zinc-500 rounded-lg text-xs" data-testid="tab-payments">Payments</TabsTrigger>
          <TabsTrigger value="plans" className="data-[state=active]:bg-lime-500/20 data-[state=active]:text-white text-zinc-500 rounded-lg text-xs" data-testid="tab-plans">Plans</TabsTrigger>
          <TabsTrigger value="admins" className="data-[state=active]:bg-lime-500/20 data-[state=active]:text-white text-zinc-500 rounded-lg text-xs" data-testid="tab-admins">Admins</TabsTrigger>
          <TabsTrigger value="config" className="data-[state=active]:bg-lime-500/20 data-[state=active]:text-white text-zinc-500 rounded-lg text-xs" data-testid="tab-config">Config</TabsTrigger>
        </TabsList>

        {/* OVERVIEW */}
        <TabsContent value="overview" className="space-y-6 mt-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Revenue Chart */}
            <GlassCard className="lg:col-span-2" delay={0.1} testId="tenant-revenue-chart">
              <h3 className="font-heading font-semibold text-white text-sm mb-1">Revenue (30 Days)</h3>
              <p className="text-[11px] text-zinc-600 mb-4">Daily revenue breakdown</p>
              {revenue_chart?.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={revenue_chart}>
                    <defs>
                      <linearGradient id="tRevGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#BFFF00" stopOpacity={0.3} />
                        <stop offset="100%" stopColor="#BFFF00" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="date" tick={{ fill: "#52525B", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => v?.slice(5)} />
                    <YAxis tick={{ fill: "#52525B", fontSize: 10 }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip />} />
                    <Area type="monotone" dataKey="revenue" stroke="#BFFF00" fill="url(#tRevGrad)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-48 text-zinc-600 text-sm">No revenue data for last 30 days</div>
              )}
            </GlassCard>

            {/* Plan Distribution */}
            <GlassCard delay={0.15} testId="tenant-plan-dist">
              <h3 className="font-heading font-semibold text-white text-sm mb-4">Plan Distribution</h3>
              {plan_distribution?.length > 0 && plan_distribution.some(p => p.count > 0) ? (
                <>
                  <ResponsiveContainer width="100%" height={150}>
                    <PieChart>
                      <Pie data={plan_distribution.filter(p => p.count > 0)} cx="50%" cy="50%" innerRadius={40} outerRadius={65} paddingAngle={3} dataKey="count" nameKey="name">
                        {plan_distribution.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="space-y-2 mt-2">
                    {plan_distribution.map((p, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                          <span className="text-zinc-400 truncate max-w-[100px]">{p.name}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-zinc-500">Rs.{p.price}</span>
                          <span className="text-white font-mono font-semibold">{p.count}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex items-center justify-center h-40 text-zinc-600 text-sm">No subscriber data</div>
              )}
            </GlassCard>
          </div>

          {/* Recent Payments */}
          <GlassCard delay={0.2} testId="tenant-recent-payments">
            <h3 className="font-heading font-semibold text-white text-sm mb-4">Recent Payments</h3>
            {recent_payments?.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-white/6 hover:bg-transparent">
                      <TableHead className="text-zinc-500 text-xs">User</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Plan</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Amount</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Status</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Date</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recent_payments.slice(0, 10).map((p, i) => (
                      <TableRow key={p.id || i} className="border-white/4 hover:bg-white/3">
                        <TableCell className="text-white text-xs font-mono">@{p.telegram_user_id || p.telegram_username || "?"}</TableCell>
                        <TableCell className="text-zinc-400 text-xs">{p.plan_name || p.plan_id || "-"}</TableCell>
                        <TableCell className="text-white text-xs font-semibold">Rs.{(p.amount || 0).toLocaleString()}</TableCell>
                        <TableCell>
                          <Badge className={`text-[10px] ${p.status === "verified" || p.status === "approved" ? "bg-emerald-500/15 text-emerald-400" : p.status === "pending" ? "bg-amber-500/15 text-amber-400" : "bg-lime-500/15 text-lime-400"}`}>
                            {p.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-zinc-500 text-xs">{formatDateTime(p.created_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-zinc-600 text-sm text-center py-6">No payments yet</p>
            )}
          </GlassCard>
        </TabsContent>

        {/* SUBSCRIBERS */}
        <TabsContent value="subscribers" className="mt-4">
          <GlassCard delay={0.1} testId="tenant-subscribers-list">
            <h3 className="font-heading font-semibold text-white text-sm mb-4">
              Subscribers ({subscribers?.length || 0})
            </h3>
            {subscribers?.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-white/6 hover:bg-transparent">
                      <TableHead className="text-zinc-500 text-xs">Telegram ID</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Username</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Plan</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Status</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Start</TableHead>
                      <TableHead className="text-zinc-500 text-xs">End</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {subscribers.map((s, i) => (
                      <TableRow key={s.id || i} className="border-white/4 hover:bg-white/3">
                        <TableCell className="text-white text-xs font-mono">{s.telegram_user_id}</TableCell>
                        <TableCell className="text-zinc-400 text-xs">@{s.telegram_username || "-"}</TableCell>
                        <TableCell className="text-zinc-400 text-xs">{s.plan_name || s.plan_id}</TableCell>
                        <TableCell>
                          <Badge className={`text-[10px] ${s.status === "active" ? "bg-emerald-500/15 text-emerald-400" : s.status === "grace" ? "bg-amber-500/15 text-amber-400" : "bg-lime-500/15 text-lime-400"}`}>
                            {s.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-zinc-500 text-xs">{formatDate(s.start_date)}</TableCell>
                        <TableCell className="text-zinc-500 text-xs">{formatDate(s.end_date)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-zinc-600 text-sm text-center py-10">No subscribers</p>
            )}
          </GlassCard>
        </TabsContent>

        {/* PAYMENTS */}
        <TabsContent value="payments" className="mt-4">
          <GlassCard delay={0.1} testId="tenant-payments-list">
            <h3 className="font-heading font-semibold text-white text-sm mb-4">
              Payments ({recent_payments?.length || 0})
            </h3>
            {recent_payments?.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-white/6 hover:bg-transparent">
                      <TableHead className="text-zinc-500 text-xs">User</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Plan</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Amount</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Method</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Status</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Date</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Screenshot</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recent_payments.map((p, i) => (
                      <TableRow key={p.id || i} className="border-white/4 hover:bg-white/3">
                        <TableCell className="text-white text-xs font-mono">@{p.telegram_user_id || "?"}</TableCell>
                        <TableCell className="text-zinc-400 text-xs">{p.plan_name || p.plan_id || "-"}</TableCell>
                        <TableCell className="text-white text-xs font-semibold">Rs.{(p.amount || 0).toLocaleString()}</TableCell>
                        <TableCell className="text-zinc-400 text-xs">{p.payment_method || "-"}</TableCell>
                        <TableCell>
                          <Badge className={`text-[10px] ${p.status === "verified" || p.status === "approved" ? "bg-emerald-500/15 text-emerald-400" : p.status === "pending" ? "bg-amber-500/15 text-amber-400" : "bg-lime-500/15 text-lime-400"}`}>
                            {p.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-zinc-500 text-xs">{formatDateTime(p.created_at)}</TableCell>
                        <TableCell>
                          {p.screenshot_url ? (
                            <a href={p.screenshot_url} target="_blank" rel="noopener noreferrer" className="text-lime-400 hover:text-lime-300">
                              <Eye className="w-4 h-4" />
                            </a>
                          ) : <span className="text-zinc-700">-</span>}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-zinc-600 text-sm text-center py-10">No payments</p>
            )}
          </GlassCard>
        </TabsContent>

        {/* PLANS */}
        <TabsContent value="plans" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {plans?.length > 0 ? plans.map((plan, i) => (
              <GlassCard key={plan.id || i} delay={0.05 * i} testId={`tenant-plan-${i}`}>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-white font-semibold text-sm">{plan.name}</h4>
                  <Badge className={`text-[10px] ${plan.is_active ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-500/15 text-zinc-400"}`}>
                    {plan.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
                <p className="font-mono text-2xl font-bold text-white">Rs.{plan.price}</p>
                <p className="text-xs text-zinc-500 mt-1">{plan.duration_days} days</p>
                {plan.channel_id && (
                  <div className="mt-3 p-2 rounded-lg bg-white/3 border border-white/5">
                    <p className="text-[10px] text-zinc-600">Channel ID</p>
                    <p className="text-xs text-white font-mono truncate">{plan.channel_id}</p>
                  </div>
                )}
                {plan.features?.length > 0 && (
                  <div className="mt-3 space-y-1">
                    {plan.features.map((f, fi) => (
                      <div key={fi} className="flex items-center gap-1.5 text-xs text-zinc-400">
                        <CheckCircle className="w-3 h-3 text-emerald-500" /> {f}
                      </div>
                    ))}
                  </div>
                )}
              </GlassCard>
            )) : (
              <p className="text-zinc-600 text-sm text-center py-10 col-span-3">No plans configured</p>
            )}
          </div>
        </TabsContent>

        {/* ADMINS */}
        <TabsContent value="admins" className="space-y-6 mt-4">
          {/* Dashboard Admins */}
          <GlassCard delay={0.1} testId="tenant-dashboard-admins">
            <h3 className="font-heading font-semibold text-white text-sm mb-4 flex items-center gap-2">
              <Shield className="w-4 h-4 text-violet-400" /> Dashboard Admins ({dashboard_admins?.length || 0})
            </h3>
            {dashboard_admins?.length > 0 ? (
              <div className="space-y-2">
                {dashboard_admins.map((a, i) => (
                  <div key={a.id || i} className="flex items-center gap-3 p-3 rounded-xl bg-white/3 border border-white/5">
                    <div className="w-9 h-9 rounded-lg bg-violet-500/15 flex items-center justify-center">
                      <span className="text-xs font-bold text-violet-400">{(a.name || a.email || "U").charAt(0).toUpperCase()}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white">{a.name || "Unnamed"}</p>
                      <p className="text-xs text-zinc-500">{a.email}</p>
                    </div>
                    <div className="text-right">
                      <Badge className="text-[10px] bg-violet-500/15 text-violet-400">{a.role}</Badge>
                      <p className="text-[10px] text-zinc-600 mt-0.5">{a.dashboard_subscription_status || "N/A"}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-zinc-600 text-sm text-center py-6">No dashboard admins</p>
            )}
          </GlassCard>

          {/* Telegram Admins */}
          <GlassCard delay={0.15} testId="tenant-tg-admins">
            <h3 className="font-heading font-semibold text-white text-sm mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4 text-teal-400" /> Telegram Bot Admins ({telegram_admins?.length || 0})
            </h3>
            {telegram_admins?.length > 0 ? (
              <div className="space-y-2">
                {telegram_admins.map((a, i) => (
                  <div key={a.id || i} className="flex items-center gap-3 p-3 rounded-xl bg-white/3 border border-white/5">
                    <div className="w-9 h-9 rounded-lg bg-teal-500/15 flex items-center justify-center">
                      <Activity className="w-4 h-4 text-teal-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white">{a.name || "Bot Admin"}</p>
                      <p className="text-xs text-zinc-500 font-mono">TG: {a.telegram_user_id}</p>
                    </div>
                    <div className="text-right">
                      <Badge className={`text-[10px] ${a.is_active ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-500/15 text-zinc-400"}`}>
                        {a.is_active ? "Active" : "Inactive"}
                      </Badge>
                      <p className="text-[10px] text-zinc-600 mt-0.5">{a.role}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-zinc-600 text-sm text-center py-6">No Telegram admins</p>
            )}
          </GlassCard>
        </TabsContent>

        {/* CONFIG */}
        <TabsContent value="config" className="mt-4">
          <GlassCard delay={0.1} testId="tenant-config">
            <h3 className="font-heading font-semibold text-white text-sm mb-4">Tenant Configuration</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[
                { label: "Tenant ID", value: tenant.tenant_id, mono: true },
                { label: "Name", value: tenant.name },
                { label: "Email", value: tenant.email },
                { label: "Status", value: tenant.status, badge: true },
                { label: "Owner Telegram ID", value: tenant.owner_telegram_id, mono: true },
                { label: "Bot Username", value: tenant.bot_username ? `@${tenant.bot_username}` : "-" },
                { label: "Bot Token", value: tenant.bot_token ? `${tenant.bot_token.slice(0, 10)}...` : "-", mono: true, sensitive: true },
                { label: "UPI ID", value: tenant.upi_id || "-" },
                { label: "Channel ID", value: tenant.channel_id || "-", mono: true },
                { label: "Created", value: formatDate(tenant.created_at) },
              ].map((item, i) => (
                <div key={i} className="p-3 rounded-xl bg-white/3 border border-white/5">
                  <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">{item.label}</p>
                  {item.badge ? (
                    <Badge className={`text-[10px] ${item.value === "active" ? "bg-emerald-500/15 text-emerald-400" : "bg-lime-500/15 text-lime-400"}`}>
                      {item.value}
                    </Badge>
                  ) : (
                    <p className={`text-sm text-white ${item.mono ? "font-mono" : ""} ${item.sensitive ? "blur-sm hover:blur-none transition-all cursor-pointer" : ""} truncate`}>
                      {item.value || "-"}
                    </p>
                  )}
                </div>
              ))}
            </div>
            {tenant.razorpay_key_id && (
              <div className="mt-4 p-3 rounded-xl bg-white/3 border border-white/5">
                <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Razorpay Key</p>
                <p className="text-sm text-white font-mono blur-sm hover:blur-none transition-all cursor-pointer truncate">{tenant.razorpay_key_id}</p>
              </div>
            )}
          </GlassCard>
        </TabsContent>
      </Tabs>
    </div>
  );
}
