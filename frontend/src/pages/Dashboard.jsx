import { useState, useEffect } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import {
  Users,
  IndianRupee,
  TrendingUp,
  UserPlus,
  CreditCard,
  Activity,
  Sparkles,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Area,
  AreaChart,
} from "recharts";
import {
  StatsCard,
  BentoGrid,
  BentoItem,
  GlowCard,
  AnimatedListItem,
  ChartContainer,
  PulseDot,
  AnimatedProgress,
} from "../components/ui/sera-ui";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

const COLORS = ["#E11D48", "#10B981", "#F59E0B", "#8B5CF6"];

export default function Dashboard() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [settings, setSettings] = useState(null);
  const [plans, setPlans] = useState([]);

  useEffect(() => {
    fetchAnalytics();
    fetchSetupData();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const response = await axios.get(`${API}/analytics`, getAuthHeaders());
      setAnalytics(response.data);
    } catch (error) {
      console.error("Failed to fetch analytics:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSetupData = async () => {
    try {
      const [settingsRes, plansRes] = await Promise.all([
        axios.get(`${API}/settings`, getAuthHeaders()),
        axios.get(`${API}/plans`, getAuthHeaders()),
      ]);
      setSettings(settingsRes.data);
      setPlans(plansRes.data);
    } catch (error) {
      console.error("Setup data fetch error:", error);
    }
  };

  const setupChecklist = settings ? [
    { label: "Bot Token configured", done: !!settings.telegram_bot_token, link: "/dashboard/settings" },
    { label: "Channel ID set", done: !!settings.telegram_channel_id, link: "/dashboard/settings" },
    { label: "QR Code uploaded", done: !!settings.qr_code_url, link: "/dashboard/settings" },
    { label: "Plans created", done: plans.length > 0, link: "/dashboard/plans" },
    { label: "Welcome message set", done: settings.welcome_message && settings.welcome_message !== "Welcome to our subscription bot! Use /plans to see available plans.", link: "/dashboard/settings" },
  ] : [];

  const setupComplete = setupChecklist.filter(s => s.done).length;
  const setupTotal = setupChecklist.length;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full"
        />
      </div>
    );
  }

  const statusData = [
    { name: "Active", value: analytics?.active_subscribers || 0, color: "#10B981" },
    { name: "Grace", value: analytics?.grace_subscribers || 0, color: "#F59E0B" },
    { name: "Expired", value: analytics?.expired_subscribers || 0, color: "#E11D48" },
  ].filter((d) => d.value > 0);

  const planData = analytics?.plan_stats || [];

  // Calculate conversion rate
  const totalUsers = analytics?.total_subscribers || 0;
  const activeUsers = analytics?.active_subscribers || 0;
  const conversionRate = totalUsers > 0 ? ((activeUsers / totalUsers) * 100).toFixed(1) : 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="space-y-1"
      >
        <div className="flex items-center gap-3">
          <h1 className="font-serif text-4xl font-semibold tracking-tight">Dashboard</h1>
          <PulseDot color="emerald" />
        </div>
        <p className="text-muted-foreground">
          Real-time overview of your premium subscription business
        </p>
      </motion.div>

      {/* Stats Grid - Bento Style */}
      <BentoGrid className="grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
        <BentoItem delay={0}>
          <StatsCard
            title="Total Subscribers"
            value={analytics?.total_subscribers || 0}
            icon={Users}
            trend={12}
            trendLabel="vs last month"
            color="primary"
          />
        </BentoItem>

        <BentoItem delay={0.1}>
          <StatsCard
            title="Active"
            value={analytics?.active_subscribers || 0}
            icon={TrendingUp}
            trend={8}
            trendLabel="growing"
            color="emerald"
          />
        </BentoItem>

        <BentoItem delay={0.2}>
          <StatsCard
            title="Total Revenue"
            value={analytics?.total_revenue || 0}
            prefix="₹"
            icon={IndianRupee}
            trend={23}
            trendLabel="lifetime"
            color="amber"
          />
        </BentoItem>

        <BentoItem delay={0.3}>
          <StatsCard
            title="This Month"
            value={analytics?.monthly_revenue || 0}
            prefix="₹"
            icon={Sparkles}
            trend={15}
            trendLabel="vs last month"
            color="rose"
          />
        </BentoItem>
      </BentoGrid>

      {/* Setup Checklist - Only show if not all complete */}
      {setupTotal > 0 && setupComplete < setupTotal && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="rounded-2xl bg-card border border-border/50 p-5"
          data-testid="setup-checklist"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-serif text-lg font-semibold">Setup Checklist</h3>
              <p className="text-xs text-muted-foreground mt-0.5">{setupComplete}/{setupTotal} steps done</p>
            </div>
            <div className="w-24 h-2 bg-muted/50 rounded-full overflow-hidden">
              <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${(setupComplete/setupTotal)*100}%` }} />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">
            {setupChecklist.map((item, i) => (
              <a
                key={item.label}
                href={item.link}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${
                  item.done
                    ? "bg-emerald-500/10 text-emerald-500"
                    : "bg-muted/30 text-muted-foreground hover:bg-muted/50"
                }`}
              >
                <span className="text-base">{item.done ? "✓" : "○"}</span>
                <span className="truncate">{item.label}</span>
              </a>
            ))}
          </div>
        </motion.div>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Subscriber Status - Donut Chart */}
        <ChartContainer title="Subscriber Status" delay={0.4}>
          {statusData.length > 0 ? (
            <div className="flex items-center justify-between">
              <div className="h-64 w-1/2">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={statusData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {statusData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(340 40% 7%)",
                        border: "1px solid hsl(340 40% 20%)",
                        borderRadius: "0.75rem",
                        color: "white",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-4">
                {statusData.map((item, index) => (
                  <motion.div
                    key={item.name}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.5 + index * 0.1 }}
                    className="flex items-center gap-3"
                  >
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="text-sm text-muted-foreground">{item.name}</span>
                    <span className="font-serif font-semibold">{item.value}</span>
                  </motion.div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              No subscriber data yet
            </div>
          )}
        </ChartContainer>

        {/* Plan Distribution - Bar Chart */}
        <ChartContainer title="Subscribers by Plan" delay={0.5}>
          {planData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={planData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(340 30% 15%)" />
                  <XAxis dataKey="name" stroke="hsl(340 20% 50%)" fontSize={12} />
                  <YAxis stroke="hsl(340 20% 50%)" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(340 40% 7%)",
                      border: "1px solid hsl(340 40% 20%)",
                      borderRadius: "0.75rem",
                      color: "white",
                    }}
                  />
                  <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                    {planData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              No plans created yet
            </div>
          )}
        </ChartContainer>
      </div>

      {/* Recent Activity Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Conversion Rate Card */}
        <GlowCard glowColor="emerald" className="lg:col-span-1">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-muted-foreground">
                Conversion Rate
              </span>
              <Activity className="w-5 h-5 text-emerald-500" />
            </div>
            <div className="space-y-2">
              <span className="font-serif text-4xl font-semibold text-emerald-500">
                {conversionRate}%
              </span>
              <AnimatedProgress value={Number(conversionRate)} color="emerald" />
            </div>
            <p className="text-xs text-muted-foreground">
              {activeUsers} active out of {totalUsers} total subscribers
            </p>
          </div>
        </GlowCard>

        {/* Recent Subscribers */}
        <GlowCard className="lg:col-span-1">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-muted-foreground">
                Recent Subscribers
              </span>
              <UserPlus className="w-5 h-5 text-primary" />
            </div>
            <div className="space-y-3">
              {analytics?.recent_subscribers?.length > 0 ? (
                analytics.recent_subscribers.slice(0, 4).map((sub, index) => (
                  <AnimatedListItem key={sub.id || index} index={index}>
                    <div className="flex items-center justify-between p-2 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-rose-500 to-red-600 flex items-center justify-center text-xs font-semibold text-white">
                          {sub.telegram_username?.charAt(0)?.toUpperCase() || "U"}
                        </div>
                        <span className="text-sm font-medium truncate max-w-[100px]">
                          @{sub.telegram_username || "user"}
                        </span>
                      </div>
                      <span
                        className={`text-xs px-2 py-1 rounded-full ${
                          sub.status === "active"
                            ? "bg-emerald-500/10 text-emerald-500"
                            : "bg-amber-500/10 text-amber-500"
                        }`}
                      >
                        {sub.status}
                      </span>
                    </div>
                  </AnimatedListItem>
                ))
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No recent subscribers
                </p>
              )}
            </div>
          </div>
        </GlowCard>

        {/* Recent Payments */}
        <GlowCard className="lg:col-span-1">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-muted-foreground">
                Recent Payments
              </span>
              <CreditCard className="w-5 h-5 text-primary" />
            </div>
            <div className="space-y-3">
              {analytics?.recent_payments?.length > 0 ? (
                analytics.recent_payments.slice(0, 4).map((payment, index) => (
                  <AnimatedListItem key={payment.id || index} index={index}>
                    <div className="flex items-center justify-between p-2 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
                      <div className="flex items-center gap-2">
                        <ArrowUpRight className="w-4 h-4 text-emerald-500" />
                        <span className="font-serif font-semibold">
                          ₹{payment.amount?.toLocaleString("en-IN")}
                        </span>
                      </div>
                      <span
                        className={`text-xs px-2 py-1 rounded-full ${
                          payment.status === "verified"
                            ? "bg-emerald-500/10 text-emerald-500"
                            : payment.status === "pending"
                            ? "bg-amber-500/10 text-amber-500"
                            : "bg-red-500/10 text-red-500"
                        }`}
                      >
                        {payment.status}
                      </span>
                    </div>
                  </AnimatedListItem>
                ))
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No recent payments
                </p>
              )}
            </div>
          </div>
        </GlowCard>
      </div>

      {/* Quick Stats Footer */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.8 }}
        className="flex flex-wrap gap-4 justify-center pt-4"
      >
        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-muted/50 border border-border/50">
          <PulseDot color="emerald" />
          <span className="text-sm text-muted-foreground">System Online</span>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-muted/50 border border-border/50">
          <span className="text-sm text-muted-foreground">Last updated:</span>
          <span className="text-sm font-medium">
            {new Date().toLocaleTimeString("en-IN", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
      </motion.div>
    </div>
  );
}
