import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import {
  Users,
  IndianRupee,
  TrendingUp,
  Clock,
  UserPlus,
  CreditCard,
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
} from "recharts";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

const COLORS = ["#E11D48", "#F43F5E", "#FB7185", "#FDA4AF"];

export default function Dashboard() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  const statusData = [
    { name: "Active", value: analytics?.active_subscribers || 0, color: "#10B981" },
    { name: "Grace", value: analytics?.grace_subscribers || 0, color: "#F59E0B" },
    { name: "Expired", value: analytics?.expired_subscribers || 0, color: "#E11D48" },
  ].filter((d) => d.value > 0);

  const planData = analytics?.plan_stats || [];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="space-y-1">
        <h1 className="font-serif text-4xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your premium subscription business
        </p>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
        {/* Total Subscribers */}
        <Card className="romance-card border-none animate-fade-in-up stagger-1" data-testid="kpi-total-subscribers">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Subscribers
            </CardTitle>
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Users className="h-5 w-5 text-primary" strokeWidth={1.5} />
            </div>
          </CardHeader>
          <CardContent>
            <div className="font-serif text-4xl font-semibold tracking-tight stat-number">
              {analytics?.total_subscribers || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              <span className="text-emerald-500 font-medium">+{analytics?.active_subscribers || 0}</span> currently active
            </p>
          </CardContent>
        </Card>

        {/* Active Subscribers */}
        <Card className="romance-card border-none animate-fade-in-up stagger-2" data-testid="kpi-active-subscribers">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active
            </CardTitle>
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-emerald-500" strokeWidth={1.5} />
            </div>
          </CardHeader>
          <CardContent>
            <div className="font-serif text-4xl font-semibold tracking-tight text-emerald-500 stat-number">
              {analytics?.active_subscribers || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Currently subscribed
            </p>
          </CardContent>
        </Card>

        {/* Total Revenue */}
        <Card className="romance-card border-none animate-fade-in-up stagger-3" data-testid="kpi-total-revenue">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Revenue
            </CardTitle>
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
              <IndianRupee className="h-5 w-5 text-amber-500" strokeWidth={1.5} />
            </div>
          </CardHeader>
          <CardContent>
            <div className="font-serif text-4xl font-semibold tracking-tight stat-number">
              ₹{(analytics?.total_revenue || 0).toLocaleString("en-IN")}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Lifetime earnings
            </p>
          </CardContent>
        </Card>

        {/* Monthly Revenue */}
        <Card className="romance-card border-none animate-fade-in-up stagger-4 glow-rose" data-testid="kpi-monthly-revenue">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              This Month
            </CardTitle>
            <div className="w-10 h-10 rounded-xl bg-primary/15 flex items-center justify-center">
              <IndianRupee className="h-5 w-5 text-primary" strokeWidth={1.5} />
            </div>
          </CardHeader>
          <CardContent>
            <div className="font-serif text-4xl font-semibold tracking-tight text-primary stat-number">
              ₹{(analytics?.monthly_revenue || 0).toLocaleString("en-IN")}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Current month revenue
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Subscriber Status Chart */}
        <Card className="romance-card border-none" data-testid="chart-subscriber-status">
          <CardHeader>
            <CardTitle className="font-serif text-xl font-semibold">
              Subscriber Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            {statusData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={statusData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {statusData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex justify-center gap-6 mt-4">
                  {statusData.map((item) => (
                    <div key={item.name} className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: item.color }}
                      />
                      <span className="text-sm text-muted-foreground">
                        {item.name}: {item.value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="h-64 flex items-center justify-center text-muted-foreground">
                No subscribers yet
              </div>
            )}
          </CardContent>
        </Card>

        {/* Plan Distribution */}
        <Card className="romance-card border-none" data-testid="chart-plan-distribution">
          <CardHeader>
            <CardTitle className="font-serif text-xl font-semibold">
              Subscribers by Plan
            </CardTitle>
          </CardHeader>
          <CardContent>
            {planData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={planData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(340 30% 15%)" />
                    <XAxis dataKey="name" stroke="hsl(340 20% 50%)" fontSize={12} />
                    <YAxis stroke="hsl(340 20% 50%)" fontSize={12} />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: 'hsl(340 40% 7%)', 
                        border: '1px solid hsl(340 40% 20%)',
                        borderRadius: '0.75rem'
                      }} 
                    />
                    <Bar dataKey="count" fill="hsl(346 80% 50%)" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-64 flex items-center justify-center text-muted-foreground">
                No plans created yet
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Subscribers */}
        <Card className="romance-card border-none" data-testid="recent-subscribers">
          <CardHeader>
            <CardTitle className="font-serif text-xl font-semibold flex items-center gap-2">
              <UserPlus className="w-5 h-5 text-primary" strokeWidth={1.5} />
              Recent Subscribers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {analytics?.recent_subscribers?.length > 0 ? (
                analytics.recent_subscribers.map((sub) => (
                  <div
                    key={sub.id}
                    className="flex items-center justify-between py-2 border-b border-border last:border-0"
                  >
                    <div>
                      <p className="font-medium font-mono text-sm">
                        @{sub.telegram_username || sub.telegram_user_id}
                      </p>
                      <p className="text-xs text-muted-foreground">{sub.plan_name}</p>
                    </div>
                    <Badge
                      className={`${
                        sub.status === "active"
                          ? "bg-green-100 text-green-700"
                          : sub.status === "grace"
                          ? "bg-yellow-100 text-yellow-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {sub.status}
                    </Badge>
                  </div>
                ))
              ) : (
                <p className="text-muted-foreground text-center py-4">
                  No recent subscribers
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Recent Payments */}
        <Card className="romance-card border-none" data-testid="recent-payments">
          <CardHeader>
            <CardTitle className="font-serif text-xl font-semibold flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-primary" strokeWidth={1.5} />
              Recent Payments
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analytics?.recent_payments?.length > 0 ? (
                analytics.recent_payments.map((payment) => (
                  <div
                    key={payment.id}
                    className="flex items-center justify-between p-3 rounded-xl bg-muted/30 hover:bg-muted/50 transition-colors"
                  >
                    <div>
                      <p className="font-serif font-semibold text-lg">
                        ₹{payment.amount.toLocaleString("en-IN")}
                      </p>
                      <p className="text-xs text-muted-foreground capitalize">
                        {payment.payment_method}
                      </p>
                    </div>
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-medium ${
                        payment.status === "verified"
                          ? "status-active"
                          : payment.status === "pending"
                          ? "status-pending"
                          : "status-expired"
                      }`}
                    >
                      {payment.status}
                    </span>
                  </div>
                ))
              ) : (
                <p className="text-muted-foreground text-center py-8">
                  No recent payments
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
