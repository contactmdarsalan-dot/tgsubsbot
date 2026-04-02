import { useState, useEffect } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import {
  IndianRupee,
  TrendingUp,
  TrendingDown,
  Users,
  BarChart3,
  Target,
  Zap,
  Calendar,
  ArrowUpRight,
  ArrowDownRight,
  Crown,
  Flame,
  ShieldCheck,
} from "lucide-react";
import {
  AreaChart,
  Area,
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
  RadialBarChart,
  RadialBar,
} from "recharts";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Button } from "../components/ui/button";
import {
  BentoGrid,
  BentoItem,
  GlowCard,
  ChartContainer,
  PulseDot,
  AnimatedProgress,
} from "../components/ui/sera-ui";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

const COLORS = ["#BFFF00", "#10B981", "#F59E0B", "#8B5CF6", "#3B82F6", "#EC4899"];

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[hsl(0, 0%, 5%)] border border-[hsl(0,0%,15%)] rounded-xl px-4 py-3 shadow-xl">
        <p className="text-xs text-gray-400 mb-1">{label}</p>
        {payload.map((item, i) => (
          <p key={i} className="text-sm font-semibold" style={{ color: item.color }}>
            {item.name}: {typeof item.value === 'number' ? `₹${item.value.toLocaleString("en-IN")}` : item.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

function MetricCard({ title, value, prefix = "", suffix = "", icon: Icon, trend, trendLabel, color = "primary", delay = 0 }) {
  const isPositive = trend >= 0;
  const colorMap = {
    primary: "from-lime-500 to-emerald-600",
    emerald: "from-emerald-500 to-green-600",
    amber: "from-amber-500 to-yellow-600",
    violet: "from-violet-500 to-purple-600",
    blue: "from-blue-500 to-cyan-600",
    rose: "from-lime-500 to-pink-600",
  };
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className="relative overflow-hidden rounded-2xl bg-card border border-border/50 p-5 hover:border-primary/30 transition-all duration-300"
      data-testid={`metric-${title.toLowerCase().replace(/\s/g, '-')}`}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{title}</p>
          <p className="font-serif text-3xl font-bold tracking-tight text-white">
            {prefix}{typeof value === 'number' ? value.toLocaleString("en-IN") : value}{suffix}
          </p>
          {trend !== undefined && (
            <div className="flex items-center gap-1.5">
              {isPositive ? (
                <ArrowUpRight className="w-3.5 h-3.5 text-emerald-500" />
              ) : (
                <ArrowDownRight className="w-3.5 h-3.5 text-red-500" />
              )}
              <span className={`text-xs font-medium ${isPositive ? 'text-emerald-500' : 'text-red-500'}`}>
                {Math.abs(trend)}%
              </span>
              {trendLabel && <span className="text-xs text-muted-foreground">{trendLabel}</span>}
            </div>
          )}
        </div>
        <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${colorMap[color]} flex items-center justify-center shadow-lg`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
    </motion.div>
  );
}

export default function RevenueDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [chartPeriod, setChartPeriod] = useState("daily");

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const response = await axios.get(`${API}/analytics/revenue`, getAuthHeaders());
      setData(response.data);
    } catch (error) {
      console.error("Failed to fetch revenue analytics:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleExportCSV = async () => {
    try {
      const response = await axios.get(`${API}/export/revenue-report`, getAuthHeaders());
      const csvData = response.data.csv_data;
      const blob = new Blob([csvData], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `revenue-report-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
    } catch (error) {
      console.error("Export failed:", error);
    }
  };

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

  if (!data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">
        Failed to load analytics data
      </div>
    );
  }

  const getChartData = () => {
    switch (chartPeriod) {
      case "weekly": return data.weekly_chart || [];
      case "monthly": return data.monthly_chart || [];
      default: return data.daily_chart || [];
    }
  };

  const getXKey = () => {
    switch (chartPeriod) {
      case "weekly": return "week";
      case "monthly": return "month";
      default: return "date";
    }
  };

  const funnelMax = Math.max(...(data.funnel || []).map(f => f.count), 1);

  return (
    <div className="space-y-8" data-testid="revenue-dashboard">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="font-serif text-4xl font-semibold tracking-tight text-white">Revenue Analytics</h1>
            <PulseDot color="emerald" />
          </div>
          <p className="text-muted-foreground">
            Track your business performance and optimize for growth
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleExportCSV} data-testid="export-revenue-csv">
            <ArrowUpRight className="w-4 h-4 mr-1.5" />
            Export CSV
          </Button>
          <Button
            size="sm"
            onClick={() => {
              const link = document.createElement("a");
              link.href = `${API}/analytics/export-pdf`;
              link.target = "_blank";
              const token = localStorage.getItem("token");
              fetch(`${API}/analytics/export-pdf`, {
                headers: { Authorization: `Bearer ${token}` },
              })
                .then((res) => res.blob())
                .then((blob) => {
                  const url = window.URL.createObjectURL(blob);
                  link.href = url;
                  link.download = `TGSubsBot_Revenue_${new Date().toISOString().slice(0, 10)}.pdf`;
                  link.click();
                  window.URL.revokeObjectURL(url);
                })
                .catch(() => {});
            }}
            data-testid="export-revenue-pdf"
          >
            <ArrowUpRight className="w-4 h-4 mr-1.5" />
            Export PDF
          </Button>
        </div>
      </motion.div>

      {/* Top Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-4">
        <MetricCard
          title="Total Revenue"
          value={data.total_revenue}
          prefix="₹"
          icon={IndianRupee}
          trend={data.revenue_growth}
          trendLabel="vs last month"
          color="amber"
          delay={0}
        />
        <MetricCard
          title="This Month"
          value={data.monthly_revenue}
          prefix="₹"
          icon={Flame}
          color="rose"
          delay={0.05}
        />
        <MetricCard
          title="Today"
          value={data.today_revenue}
          prefix="₹"
          icon={Zap}
          color="emerald"
          delay={0.1}
        />
        <MetricCard
          title="ARPU"
          value={data.arpu}
          prefix="₹"
          icon={Target}
          color="violet"
          delay={0.15}
        />
        <MetricCard
          title="LTV"
          value={data.ltv}
          prefix="₹"
          icon={Crown}
          color="blue"
          delay={0.2}
        />
        <MetricCard
          title="Churn Rate"
          value={data.churn_rate}
          suffix="%"
          icon={data.churn_rate > 20 ? TrendingDown : ShieldCheck}
          color={data.churn_rate > 20 ? "rose" : "emerald"}
          delay={0.25}
        />
      </div>

      {/* Revenue Chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="rounded-2xl bg-card border border-border/50 p-6"
        data-testid="revenue-chart-container"
      >
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-serif text-xl font-semibold">Revenue Trend</h2>
            <p className="text-sm text-muted-foreground mt-1">Track income over time</p>
          </div>
          <Tabs value={chartPeriod} onValueChange={setChartPeriod}>
            <TabsList className="bg-muted/50">
              <TabsTrigger value="daily" data-testid="chart-tab-daily" className="text-xs">Daily</TabsTrigger>
              <TabsTrigger value="weekly" data-testid="chart-tab-weekly" className="text-xs">Weekly</TabsTrigger>
              <TabsTrigger value="monthly" data-testid="chart-tab-monthly" className="text-xs">Monthly</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={getChartData()}>
              <defs>
                <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#BFFF00" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#BFFF00" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(0 0% 12%)" />
              <XAxis
                dataKey={getXKey()}
                stroke="hsl(0 0% 30%)"
                fontSize={11}
                tickFormatter={(v) => chartPeriod === "daily" ? v.slice(5) : v}
              />
              <YAxis
                stroke="hsl(0 0% 30%)"
                fontSize={11}
                tickFormatter={(v) => `₹${v >= 1000 ? `${(v/1000).toFixed(0)}k` : v}`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="revenue"
                name="Revenue"
                stroke="#BFFF00"
                strokeWidth={2.5}
                fill="url(#revenueGradient)"
                dot={false}
                activeDot={{ r: 5, strokeWidth: 2, fill: "#BFFF00" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      {/* Plan Performance + Conversion Funnel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Plan Performance */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="rounded-2xl bg-card border border-border/50 p-6"
          data-testid="plan-performance"
        >
          <h2 className="font-serif text-xl font-semibold mb-1">Plan Performance</h2>
          <p className="text-sm text-muted-foreground mb-6">Revenue by subscription plan</p>
          
          {data.plan_performance && data.plan_performance.length > 0 ? (
            <div className="space-y-4">
              {data.plan_performance.slice(0, 6).map((plan, i) => {
                const maxRev = data.plan_performance[0]?.revenue || 1;
                const pct = Math.round((plan.revenue / maxRev) * 100);
                return (
                  <motion.div
                    key={plan.name}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.5 + i * 0.08 }}
                    className="space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                        <span className="text-sm font-medium truncate max-w-[180px]">{plan.name}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-muted-foreground">{plan.sales} sales</span>
                        <span className="font-serif font-semibold text-sm">₹{plan.revenue.toLocaleString("en-IN")}</span>
                      </div>
                    </div>
                    <div className="h-2 bg-muted/50 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ delay: 0.6 + i * 0.08, duration: 0.6 }}
                        className="h-full rounded-full"
                        style={{ backgroundColor: COLORS[i % COLORS.length] }}
                      />
                    </div>
                  </motion.div>
                );
              })}
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-muted-foreground">
              No plan data yet
            </div>
          )}
        </motion.div>

        {/* Conversion Funnel */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="rounded-2xl bg-card border border-border/50 p-6"
          data-testid="conversion-funnel"
        >
          <h2 className="font-serif text-xl font-semibold mb-1">Conversion Funnel</h2>
          <p className="text-sm text-muted-foreground mb-6">User journey from bot to active subscriber</p>
          
          {data.funnel && data.funnel.length > 0 ? (
            <div className="space-y-5">
              {data.funnel.map((step, i) => {
                const pct = Math.round((step.count / funnelMax) * 100);
                const convRate = i > 0 && data.funnel[i-1].count > 0
                  ? Math.round((step.count / data.funnel[i-1].count) * 100)
                  : 100;
                const funnelColors = ["#3B82F6", "#8B5CF6", "#F59E0B", "#10B981"];
                return (
                  <motion.div
                    key={step.stage}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.6 + i * 0.1 }}
                    className="space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{step.stage}</span>
                      <div className="flex items-center gap-2">
                        <span className="font-serif font-bold">{step.count.toLocaleString()}</span>
                        {i > 0 && (
                          <span className={`text-xs px-1.5 py-0.5 rounded ${convRate >= 50 ? 'bg-emerald-500/10 text-emerald-500' : 'bg-amber-500/10 text-amber-500'}`}>
                            {convRate}%
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="h-3 bg-muted/50 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ delay: 0.7 + i * 0.1, duration: 0.6 }}
                        className="h-full rounded-full"
                        style={{ backgroundColor: funnelColors[i] }}
                      />
                    </div>
                  </motion.div>
                );
              })}
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-muted-foreground">
              No funnel data yet
            </div>
          )}
        </motion.div>
      </div>

      {/* Quick Stats Footer */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.7 }}
        className="grid grid-cols-2 md:grid-cols-4 gap-4"
      >
        <div className="rounded-xl bg-muted/30 border border-border/30 p-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">Total Payments</p>
          <p className="font-serif text-2xl font-bold">{data.total_payments}</p>
        </div>
        <div className="rounded-xl bg-muted/30 border border-border/30 p-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">Active Subscribers</p>
          <p className="font-serif text-2xl font-bold text-emerald-500">{data.active_subscribers}</p>
        </div>
        <div className="rounded-xl bg-muted/30 border border-border/30 p-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">In Grace Period</p>
          <p className="font-serif text-2xl font-bold text-amber-500">{data.grace_subscribers}</p>
        </div>
        <div className="rounded-xl bg-muted/30 border border-border/30 p-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">Expired</p>
          <p className="font-serif text-2xl font-bold text-red-500">{data.expired_subscribers}</p>
        </div>
      </motion.div>
    </div>
  );
}
