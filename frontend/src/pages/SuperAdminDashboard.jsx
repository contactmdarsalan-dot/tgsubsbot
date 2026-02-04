import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Switch } from "../components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import { toast } from "sonner";
import { 
  Users, 
  CheckCircle, 
  Clock, 
  Crown, 
  IndianRupee,
  Search,
  Shield,
  XCircle,
  RefreshCw,
  Calendar,
  Mail,
  User,
  Edit,
  MessageSquare,
  Send,
  AlertTriangle,
  Package,
  CreditCard,
  Trash2,
  Plus,
  Eye,
  ChevronDown,
  ChevronUp,
  Image,
  Sparkles,
  Star,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

// Only this email can access
const SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com";

export default function SuperAdminDashboard() {
  const [activeTab, setActiveTab] = useState("dashboard-plans");
  const [plans, setPlans] = useState([]);
  const [dashboardPlans, setDashboardPlans] = useState([]);
  const [subscribers, setSubscribers] = useState([]);
  const [payments, setPayments] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [subscriberFilter, setSubscriberFilter] = useState("all");
  const [paymentFilter, setPaymentFilter] = useState("all");
  const [ticketFilter, setTicketFilter] = useState("all");
  
  // Plan edit dialog
  const [planDialog, setPlanDialog] = useState({ open: false, plan: null, isNew: false });
  const [planForm, setPlanForm] = useState({ name: "", price: "", duration_days: "", features: "", channel_id: "" });
  
  // Dashboard Plan edit dialog
  const [dashPlanDialog, setDashPlanDialog] = useState({ open: false, plan: null });
  const [dashPlanForm, setDashPlanForm] = useState({ name: "", price: "", duration_days: "", popular: false, save: "", contact: false });
  
  // Screenshot modal
  const [screenshotModal, setScreenshotModal] = useState({ open: false, url: "", payment: null });
  
  // Support ticket
  const [expandedTicket, setExpandedTicket] = useState(null);
  const [adminReply, setAdminReply] = useState({ ticketId: null, message: "", status: "in_progress" });
  
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const isSuperAdmin = user.email === SUPER_ADMIN_EMAIL;

  useEffect(() => {
    if (isSuperAdmin) {
      fetchData();
    }
  }, [isSuperAdmin]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [plansRes, dashPlansRes, subsRes, paymentsRes, ticketsRes] = await Promise.all([
        axios.get(`${API}/plans`, getAuthHeaders()),
        axios.get(`${API}/admin/dashboard-plans`, getAuthHeaders()),
        axios.get(`${API}/subscribers`, getAuthHeaders()),
        axios.get(`${API}/payments`, getAuthHeaders()),
        axios.get(`${API}/admin/support/tickets`, getAuthHeaders()),
      ]);
      setPlans(plansRes.data);
      setDashboardPlans(dashPlansRes.data);
      setSubscribers(subsRes.data);
      setPayments(paymentsRes.data);
      setTickets(ticketsRes.data);
    } catch (error) {
      toast.error("Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  // Dashboard Plan handlers
  const handleEditDashPlan = (plan) => {
    setDashPlanForm({
      name: plan.name,
      price: plan.price.toString(),
      duration_days: plan.duration_days.toString(),
      popular: plan.popular || false,
      save: plan.save || "",
      contact: plan.contact || false,
    });
    setDashPlanDialog({ open: true, plan });
  };

  const handleSaveDashPlan = async () => {
    try {
      await axios.put(
        `${API}/admin/dashboard-plans/${dashPlanDialog.plan.id}`,
        {
          name: dashPlanForm.name,
          price: parseFloat(dashPlanForm.price),
          duration_days: parseInt(dashPlanForm.duration_days),
          popular: dashPlanForm.popular,
          save: dashPlanForm.save,
          contact: dashPlanForm.contact,
        },
        getAuthHeaders()
      );
      toast.success("Dashboard plan updated!");
      setDashPlanDialog({ open: false, plan: null });
      fetchData();
    } catch (error) {
      toast.error("Failed to update plan");
    }
  };

  // Plan handlers
  const handleEditPlan = (plan) => {
    setPlanForm({
      name: plan.name,
      price: plan.price.toString(),
      duration_days: plan.duration_days.toString(),
      features: (plan.features || []).join("\n"),
      channel_id: plan.channel_id || "",
    });
    setPlanDialog({ open: true, plan, isNew: false });
  };

  const handleNewPlan = () => {
    setPlanForm({ name: "", price: "", duration_days: "", features: "", channel_id: "" });
    setPlanDialog({ open: true, plan: null, isNew: true });
  };

  const handleSavePlan = async () => {
    try {
      const data = {
        name: planForm.name,
        price: parseFloat(planForm.price),
        duration_days: parseInt(planForm.duration_days),
        features: planForm.features.split("\n").filter(f => f.trim()),
        channel_id: planForm.channel_id,
        is_active: true,
      };

      if (planDialog.isNew) {
        await axios.post(`${API}/plans`, data, getAuthHeaders());
        toast.success("Plan created!");
      } else {
        await axios.put(`${API}/plans/${planDialog.plan.id}`, data, getAuthHeaders());
        toast.success("Plan updated!");
      }
      setPlanDialog({ open: false, plan: null, isNew: false });
      fetchData();
    } catch (error) {
      toast.error("Failed to save plan");
    }
  };

  const handleDeletePlan = async (planId) => {
    if (!window.confirm("Delete this plan?")) return;
    try {
      await axios.delete(`${API}/plans/${planId}`, getAuthHeaders());
      toast.success("Plan deleted!");
      fetchData();
    } catch (error) {
      toast.error("Failed to delete plan");
    }
  };

  // Payment handlers
  const handleVerifyPayment = async (paymentId) => {
    try {
      await axios.put(`${API}/payments/${paymentId}/verify-manual`, {}, getAuthHeaders());
      toast.success("Payment verified!");
      setScreenshotModal({ open: false, url: "", payment: null });
      fetchData();
    } catch (error) {
      toast.error("Failed to verify");
    }
  };

  const handleRejectPayment = async (paymentId) => {
    if (!window.confirm("Reject this payment?")) return;
    try {
      await axios.put(`${API}/payments/${paymentId}/reject`, { reason: "Rejected by admin" }, getAuthHeaders());
      toast.success("Payment rejected!");
      setScreenshotModal({ open: false, url: "", payment: null });
      fetchData();
    } catch (error) {
      toast.error("Failed to reject");
    }
  };

  // Support handlers
  const handleAdminReply = async (ticketId) => {
    if (!adminReply.message.trim()) return;
    try {
      await axios.post(
        `${API}/admin/support/tickets/${ticketId}/reply`,
        { message: adminReply.message, status: adminReply.status },
        getAuthHeaders()
      );
      toast.success("Reply sent!");
      setAdminReply({ ticketId: null, message: "", status: "in_progress" });
      fetchData();
    } catch (error) {
      toast.error("Failed to send reply");
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  };

  const formatTime = (dateStr) => {
    if (!dateStr) return "";
    return new Date(dateStr).toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Filtered data
  const filteredSubscribers = subscribers.filter((s) => {
    const matchesSearch = s.telegram_user_id?.toLowerCase().includes(search.toLowerCase());
    if (subscriberFilter === "all") return matchesSearch;
    return matchesSearch && s.status === subscriberFilter;
  });

  const filteredPayments = payments.filter((p) => {
    if (paymentFilter === "all") return true;
    return p.status === paymentFilter;
  });

  const filteredTickets = tickets.filter((t) => {
    if (ticketFilter === "all") return true;
    return t.status === ticketFilter;
  });

  // Stats
  const totalSubscribers = subscribers.length;
  const activeSubscribers = subscribers.filter(s => s.status === "active").length;
  const pendingPayments = payments.filter(p => p.status === "pending").length;
  const openTickets = tickets.filter(t => t.status === "open").length;
  const totalRevenue = payments.filter(p => p.status === "verified").reduce((sum, p) => sum + (p.amount || 0), 0);

  if (!isSuperAdmin) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-900 via-black to-red-900 flex items-center justify-center p-4">
        <Card className="bg-black/60 border-red-500/50 backdrop-blur-lg max-w-md">
          <CardContent className="p-8 text-center">
            <AlertTriangle className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-white mb-2">Access Denied</h2>
            <p className="text-red-200">Super Admin access required</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-500 border-t-transparent mx-auto mb-4"></div>
          <p className="text-purple-200">Loading Control Panel...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
      <div className="bg-black/40 backdrop-blur-lg border-b border-purple-500/30 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center shadow-lg shadow-purple-500/30">
                <Crown className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white tracking-tight">
                  Super Admin Control Panel
                </h1>
                <p className="text-purple-300 text-sm">
                  Bot Subscription Management • {user.email}
                </p>
              </div>
            </div>
            <Button 
              onClick={fetchData} 
              variant="outline" 
              className="border-purple-500/50 text-purple-200 hover:bg-purple-500/20"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Quick Stats */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <Card className="bg-gradient-to-br from-blue-500/20 to-blue-600/10 border-blue-500/30 backdrop-blur">
            <CardContent className="p-4 text-center">
              <Package className="w-8 h-8 text-blue-400 mx-auto mb-2" />
              <p className="text-3xl font-bold text-white">{plans.length}</p>
              <p className="text-blue-300 text-xs">Bot Plans</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-green-500/20 to-green-600/10 border-green-500/30 backdrop-blur">
            <CardContent className="p-4 text-center">
              <Users className="w-8 h-8 text-green-400 mx-auto mb-2" />
              <p className="text-3xl font-bold text-white">{activeSubscribers}/{totalSubscribers}</p>
              <p className="text-green-300 text-xs">Active Subscribers</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-yellow-500/20 to-yellow-600/10 border-yellow-500/30 backdrop-blur">
            <CardContent className="p-4 text-center">
              <CreditCard className="w-8 h-8 text-yellow-400 mx-auto mb-2" />
              <p className="text-3xl font-bold text-white">{pendingPayments}</p>
              <p className="text-yellow-300 text-xs">Pending Payments</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-orange-500/20 to-orange-600/10 border-orange-500/30 backdrop-blur">
            <CardContent className="p-4 text-center">
              <MessageSquare className="w-8 h-8 text-orange-400 mx-auto mb-2" />
              <p className="text-3xl font-bold text-white">{openTickets}</p>
              <p className="text-orange-300 text-xs">Open Tickets</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 backdrop-blur">
            <CardContent className="p-4 text-center">
              <IndianRupee className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
              <p className="text-3xl font-bold text-white">₹{totalRevenue}</p>
              <p className="text-emerald-300 text-xs">Total Revenue</p>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="bg-black/40 border border-purple-500/30 p-1">
            <TabsTrigger 
              value="plans" 
              className="data-[state=active]:bg-purple-500 data-[state=active]:text-white text-purple-200"
            >
              <Package className="w-4 h-4 mr-2" />
              Bot Plans
            </TabsTrigger>
            <TabsTrigger 
              value="subscribers" 
              className="data-[state=active]:bg-purple-500 data-[state=active]:text-white text-purple-200"
            >
              <Users className="w-4 h-4 mr-2" />
              Subscribers
            </TabsTrigger>
            <TabsTrigger 
              value="payments" 
              className="data-[state=active]:bg-purple-500 data-[state=active]:text-white text-purple-200"
            >
              <CreditCard className="w-4 h-4 mr-2" />
              Payments
              {pendingPayments > 0 && (
                <Badge className="ml-2 bg-yellow-500 text-black">{pendingPayments}</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger 
              value="support" 
              className="data-[state=active]:bg-purple-500 data-[state=active]:text-white text-purple-200"
            >
              <MessageSquare className="w-4 h-4 mr-2" />
              Support
              {openTickets > 0 && (
                <Badge className="ml-2 bg-orange-500 text-black">{openTickets}</Badge>
              )}
            </TabsTrigger>
          </TabsList>

          {/* BOT PLANS TAB */}
          <TabsContent value="plans" className="space-y-6">
            <div className="flex justify-end">
              <Button onClick={handleNewPlan} className="bg-purple-500 hover:bg-purple-600">
                <Plus className="w-4 h-4 mr-2" />
                Add New Plan
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {plans.map((plan) => (
                <Card key={plan.id} className="bg-black/40 border-purple-500/30 backdrop-blur overflow-hidden">
                  <CardHeader className="border-b border-purple-500/30 pb-4">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-white text-xl">{plan.name}</CardTitle>
                      <Badge className={plan.is_active ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"}>
                        {plan.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="p-6 space-y-4">
                    <div className="text-center">
                      <p className="text-4xl font-bold text-white">₹{plan.price}</p>
                      <p className="text-purple-300 text-sm">{plan.duration_days} days</p>
                    </div>
                    
                    {plan.channel_id && (
                      <div className="p-3 bg-purple-500/10 rounded-lg">
                        <p className="text-xs text-purple-400">Channel ID</p>
                        <p className="text-white text-sm font-mono">{plan.channel_id}</p>
                      </div>
                    )}

                    {plan.features && plan.features.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-xs text-purple-400">Features</p>
                        {plan.features.map((f, i) => (
                          <p key={i} className="text-white text-sm flex items-center gap-2">
                            <CheckCircle className="w-3 h-3 text-green-400" />
                            {f}
                          </p>
                        ))}
                      </div>
                    )}

                    <div className="flex gap-2 pt-4">
                      <Button 
                        onClick={() => handleEditPlan(plan)} 
                        className="flex-1 bg-blue-500/20 hover:bg-blue-500/30 text-blue-300"
                      >
                        <Edit className="w-4 h-4 mr-2" />
                        Edit
                      </Button>
                      <Button 
                        onClick={() => handleDeletePlan(plan.id)} 
                        variant="outline"
                        className="border-red-500/50 text-red-400 hover:bg-red-500/20"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          {/* SUBSCRIBERS TAB */}
          <TabsContent value="subscribers" className="space-y-6">
            <Card className="bg-black/40 border-purple-500/30 backdrop-blur">
              <CardContent className="p-4">
                <div className="flex flex-col md:flex-row gap-4">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-purple-400" />
                    <Input
                      placeholder="Search by Telegram ID..."
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      className="pl-10 bg-black/30 border-purple-500/30 text-white placeholder:text-purple-400"
                    />
                  </div>
                  <Select value={subscriberFilter} onValueChange={setSubscriberFilter}>
                    <SelectTrigger className="w-[180px] bg-black/30 border-purple-500/30 text-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Subscribers</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="expired">Expired</SelectItem>
                      <SelectItem value="grace">Grace Period</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-black/40 border-purple-500/30 backdrop-blur overflow-hidden">
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-purple-500/30 hover:bg-transparent">
                        <TableHead className="text-purple-300">Telegram ID</TableHead>
                        <TableHead className="text-purple-300">Plan</TableHead>
                        <TableHead className="text-purple-300">Status</TableHead>
                        <TableHead className="text-purple-300">Start Date</TableHead>
                        <TableHead className="text-purple-300">End Date</TableHead>
                        <TableHead className="text-purple-300">Payment</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredSubscribers.map((sub) => {
                        const plan = plans.find(p => p.id === sub.plan_id);
                        return (
                          <TableRow key={sub.id} className="border-purple-500/20 hover:bg-purple-500/10">
                            <TableCell className="text-white font-mono">
                              @{sub.telegram_user_id}
                            </TableCell>
                            <TableCell>
                              <Badge className="bg-purple-500/20 text-purple-300">
                                {plan?.name || sub.plan_id}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <Badge className={`${
                                sub.status === "active"
                                  ? "bg-green-500/20 text-green-300 border-green-500/50"
                                  : sub.status === "grace"
                                    ? "bg-yellow-500/20 text-yellow-300 border-yellow-500/50"
                                    : "bg-red-500/20 text-red-300 border-red-500/50"
                              }`}>
                                {sub.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-slate-300 text-sm">
                              {formatDate(sub.start_date)}
                            </TableCell>
                            <TableCell className="text-slate-300 text-sm">
                              {formatDate(sub.end_date)}
                            </TableCell>
                            <TableCell>
                              <Badge className="bg-slate-500/20 text-slate-300">
                                {sub.payment_method}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
                {filteredSubscribers.length === 0 && (
                  <div className="py-12 text-center text-purple-300">
                    No subscribers found
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* PAYMENTS TAB */}
          <TabsContent value="payments" className="space-y-6">
            <Card className="bg-black/40 border-purple-500/30 backdrop-blur">
              <CardContent className="p-4">
                <Select value={paymentFilter} onValueChange={setPaymentFilter}>
                  <SelectTrigger className="w-[180px] bg-black/30 border-purple-500/30 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Payments</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="verified">Verified</SelectItem>
                    <SelectItem value="rejected">Rejected</SelectItem>
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>

            <Card className="bg-black/40 border-purple-500/30 backdrop-blur overflow-hidden">
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-purple-500/30 hover:bg-transparent">
                        <TableHead className="text-purple-300">Telegram ID</TableHead>
                        <TableHead className="text-purple-300">Plan</TableHead>
                        <TableHead className="text-purple-300">Amount</TableHead>
                        <TableHead className="text-purple-300">Method</TableHead>
                        <TableHead className="text-purple-300">Status</TableHead>
                        <TableHead className="text-purple-300">Date</TableHead>
                        <TableHead className="text-purple-300 text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredPayments.map((payment) => {
                        const plan = plans.find(p => p.id === payment.plan_id);
                        return (
                          <TableRow key={payment.id} className="border-purple-500/20 hover:bg-purple-500/10">
                            <TableCell className="text-white font-mono">
                              @{payment.telegram_user_id}
                            </TableCell>
                            <TableCell>
                              <Badge className="bg-purple-500/20 text-purple-300">
                                {plan?.name || payment.plan_id}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-white font-bold">
                              ₹{payment.amount}
                            </TableCell>
                            <TableCell>
                              <Badge className="bg-slate-500/20 text-slate-300">
                                {payment.payment_method}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <Badge className={`${
                                payment.status === "verified"
                                  ? "bg-green-500/20 text-green-300"
                                  : payment.status === "pending"
                                    ? "bg-yellow-500/20 text-yellow-300"
                                    : "bg-red-500/20 text-red-300"
                              }`}>
                                {payment.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-slate-300 text-sm">
                              {formatDate(payment.created_at)}
                            </TableCell>
                            <TableCell>
                              {payment.status === "pending" && (
                                <div className="flex justify-end gap-2">
                                  {payment.screenshot_url && (
                                    <Button 
                                      size="sm" 
                                      variant="ghost"
                                      onClick={() => setScreenshotModal({ open: true, url: payment.screenshot_url, payment })}
                                      className="text-blue-400 hover:bg-blue-500/20"
                                    >
                                      <Eye className="w-4 h-4" />
                                    </Button>
                                  )}
                                  <Button 
                                    size="sm" 
                                    onClick={() => handleVerifyPayment(payment.id)}
                                    className="bg-green-500/20 hover:bg-green-500/30 text-green-300"
                                  >
                                    <CheckCircle className="w-4 h-4" />
                                  </Button>
                                  <Button 
                                    size="sm" 
                                    onClick={() => handleRejectPayment(payment.id)}
                                    className="bg-red-500/20 hover:bg-red-500/30 text-red-300"
                                  >
                                    <XCircle className="w-4 h-4" />
                                  </Button>
                                </div>
                              )}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
                {filteredPayments.length === 0 && (
                  <div className="py-12 text-center text-purple-300">
                    No payments found
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* SUPPORT TAB */}
          <TabsContent value="support" className="space-y-6">
            <Card className="bg-black/40 border-purple-500/30 backdrop-blur">
              <CardContent className="p-4">
                <Select value={ticketFilter} onValueChange={setTicketFilter}>
                  <SelectTrigger className="w-[180px] bg-black/30 border-purple-500/30 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Tickets</SelectItem>
                    <SelectItem value="open">Open</SelectItem>
                    <SelectItem value="in_progress">In Progress</SelectItem>
                    <SelectItem value="resolved">Resolved</SelectItem>
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>

            <div className="space-y-4">
              {filteredTickets.length > 0 ? (
                filteredTickets.map((ticket) => (
                  <Card key={ticket.id} className="bg-black/40 border-purple-500/30 backdrop-blur overflow-hidden">
                    <div 
                      className="p-4 cursor-pointer hover:bg-purple-500/10 transition-colors"
                      onClick={() => setExpandedTicket(expandedTicket === ticket.id ? null : ticket.id)}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <Badge className={`${
                              ticket.status === "open" 
                                ? "bg-yellow-500/20 text-yellow-300"
                                : ticket.status === "in_progress"
                                  ? "bg-blue-500/20 text-blue-300"
                                  : "bg-green-500/20 text-green-300"
                            }`}>
                              {ticket.status}
                            </Badge>
                            <span className="text-purple-300 text-sm">
                              {ticket.messages?.length || 1} messages
                            </span>
                          </div>
                          <h3 className="text-white font-medium">{ticket.subject}</h3>
                          <div className="flex items-center gap-4 mt-2 text-sm text-purple-300">
                            <span className="flex items-center gap-1">
                              <User className="w-3 h-3" />
                              {ticket.user_name}
                            </span>
                            <span className="flex items-center gap-1">
                              <Mail className="w-3 h-3" />
                              {ticket.user_email}
                            </span>
                          </div>
                        </div>
                        {expandedTicket === ticket.id ? (
                          <ChevronUp className="w-5 h-5 text-purple-400" />
                        ) : (
                          <ChevronDown className="w-5 h-5 text-purple-400" />
                        )}
                      </div>
                    </div>

                    {expandedTicket === ticket.id && (
                      <div className="border-t border-purple-500/30">
                        <div className="max-h-80 overflow-y-auto p-4 space-y-3 bg-black/20">
                          {(ticket.messages || []).map((msg, idx) => (
                            <div
                              key={idx}
                              className={`flex ${msg.sender === "admin" ? "justify-start" : "justify-end"}`}
                            >
                              <div className={`max-w-[80%] rounded-xl p-3 ${
                                msg.sender === "admin"
                                  ? "bg-purple-500/20 border border-purple-500/30"
                                  : "bg-blue-500/20 border border-blue-500/30"
                              }`}>
                                <div className="flex items-center gap-2 mb-1">
                                  {msg.sender === "admin" ? (
                                    <Shield className="w-3 h-3 text-purple-400" />
                                  ) : (
                                    <User className="w-3 h-3 text-blue-400" />
                                  )}
                                  <span className="text-xs font-medium text-white">
                                    {msg.sender === "admin" ? "Admin" : msg.sender_name}
                                  </span>
                                  <span className="text-xs text-slate-400">
                                    {formatTime(msg.timestamp)}
                                  </span>
                                </div>
                                <p className="text-sm text-white/90">{msg.message}</p>
                              </div>
                            </div>
                          ))}
                        </div>

                        {ticket.status !== "resolved" && ticket.status !== "closed" && (
                          <div className="p-4 border-t border-purple-500/30 bg-black/30">
                            <Textarea
                              value={adminReply.ticketId === ticket.id ? adminReply.message : ""}
                              onChange={(e) =>
                                setAdminReply({ ...adminReply, ticketId: ticket.id, message: e.target.value })
                              }
                              placeholder="Type your reply..."
                              rows={3}
                              className="bg-black/30 border-purple-500/30 text-white placeholder:text-purple-400 resize-none mb-3"
                            />
                            <div className="flex items-center gap-3">
                              <Select
                                value={adminReply.ticketId === ticket.id ? adminReply.status : "in_progress"}
                                onValueChange={(val) =>
                                  setAdminReply({ ...adminReply, ticketId: ticket.id, status: val })
                                }
                              >
                                <SelectTrigger className="w-[150px] bg-black/30 border-purple-500/30 text-white">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="in_progress">In Progress</SelectItem>
                                  <SelectItem value="resolved">Resolved</SelectItem>
                                </SelectContent>
                              </Select>
                              <Button
                                onClick={() => handleAdminReply(ticket.id)}
                                disabled={!adminReply.message.trim() || adminReply.ticketId !== ticket.id}
                                className="flex-1 bg-purple-500 hover:bg-purple-600"
                              >
                                <Send className="w-4 h-4 mr-2" />
                                Send Reply
                              </Button>
                            </div>
                          </div>
                        )}

                        {(ticket.status === "resolved" || ticket.status === "closed") && (
                          <div className="p-4 text-center text-green-400 bg-green-500/10 border-t border-green-500/30">
                            <CheckCircle className="w-5 h-5 inline-block mr-2" />
                            Ticket {ticket.status}
                          </div>
                        )}
                      </div>
                    )}
                  </Card>
                ))
              ) : (
                <Card className="bg-black/40 border-purple-500/30 backdrop-blur">
                  <CardContent className="p-12 text-center">
                    <MessageSquare className="w-12 h-12 text-purple-500/50 mx-auto mb-4" />
                    <h3 className="text-xl font-bold text-white mb-2">No Tickets</h3>
                    <p className="text-purple-300">No support tickets found</p>
                  </CardContent>
                </Card>
              )}
            </div>
          </TabsContent>
        </Tabs>

        {/* Plan Edit Dialog */}
        <Dialog open={planDialog.open} onOpenChange={(open) => setPlanDialog({ ...planDialog, open })}>
          <DialogContent className="bg-slate-900 border-purple-500/30 max-w-md">
            <DialogHeader>
              <DialogTitle className="text-white">
                {planDialog.isNew ? "Create New Plan" : "Edit Plan"}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label className="text-purple-300">Plan Name</Label>
                <Input
                  value={planForm.name}
                  onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })}
                  placeholder="e.g., Premium Monthly"
                  className="bg-black/30 border-purple-500/30 text-white"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-purple-300">Price (₹)</Label>
                  <Input
                    type="number"
                    value={planForm.price}
                    onChange={(e) => setPlanForm({ ...planForm, price: e.target.value })}
                    placeholder="499"
                    className="bg-black/30 border-purple-500/30 text-white"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-purple-300">Duration (days)</Label>
                  <Input
                    type="number"
                    value={planForm.duration_days}
                    onChange={(e) => setPlanForm({ ...planForm, duration_days: e.target.value })}
                    placeholder="30"
                    className="bg-black/30 border-purple-500/30 text-white"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-purple-300">Channel ID</Label>
                <Input
                  value={planForm.channel_id}
                  onChange={(e) => setPlanForm({ ...planForm, channel_id: e.target.value })}
                  placeholder="-1001234567890"
                  className="bg-black/30 border-purple-500/30 text-white font-mono"
                />
              </div>

              <div className="space-y-2">
                <Label className="text-purple-300">Features (one per line)</Label>
                <Textarea
                  value={planForm.features}
                  onChange={(e) => setPlanForm({ ...planForm, features: e.target.value })}
                  placeholder="Feature 1&#10;Feature 2&#10;Feature 3"
                  rows={3}
                  className="bg-black/30 border-purple-500/30 text-white resize-none"
                />
              </div>

              <div className="flex gap-2 pt-4">
                <Button 
                  onClick={handleSavePlan}
                  className="flex-1 bg-purple-500 hover:bg-purple-600"
                  disabled={!planForm.name || !planForm.price || !planForm.duration_days}
                >
                  <CheckCircle className="w-4 h-4 mr-2" />
                  {planDialog.isNew ? "Create Plan" : "Save Changes"}
                </Button>
                <Button 
                  variant="outline" 
                  className="border-purple-500/30 text-purple-300"
                  onClick={() => setPlanDialog({ open: false, plan: null, isNew: false })}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Screenshot Modal */}
        <Dialog open={screenshotModal.open} onOpenChange={(open) => setScreenshotModal({ ...screenshotModal, open })}>
          <DialogContent className="bg-slate-900 border-purple-500/30 max-w-2xl">
            <DialogHeader>
              <DialogTitle className="text-white">Payment Screenshot</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              {screenshotModal.url ? (
                <img 
                  src={screenshotModal.url} 
                  alt="Payment Screenshot" 
                  className="w-full rounded-lg border border-purple-500/30"
                />
              ) : (
                <div className="h-64 flex items-center justify-center bg-black/30 rounded-lg">
                  <p className="text-purple-300">No screenshot available</p>
                </div>
              )}
              
              {screenshotModal.payment && (
                <div className="p-4 bg-black/30 rounded-lg space-y-2">
                  <p className="text-purple-300 text-sm">
                    <span className="text-white">Telegram:</span> @{screenshotModal.payment.telegram_user_id}
                  </p>
                  <p className="text-purple-300 text-sm">
                    <span className="text-white">Amount:</span> ₹{screenshotModal.payment.amount}
                  </p>
                </div>
              )}

              {screenshotModal.payment?.status === "pending" && (
                <div className="flex gap-2">
                  <Button 
                    onClick={() => handleVerifyPayment(screenshotModal.payment.id)}
                    className="flex-1 bg-green-500 hover:bg-green-600"
                  >
                    <CheckCircle className="w-4 h-4 mr-2" />
                    Verify
                  </Button>
                  <Button 
                    onClick={() => handleRejectPayment(screenshotModal.payment.id)}
                    className="flex-1 bg-red-500 hover:bg-red-600"
                  >
                    <XCircle className="w-4 h-4 mr-2" />
                    Reject
                  </Button>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
