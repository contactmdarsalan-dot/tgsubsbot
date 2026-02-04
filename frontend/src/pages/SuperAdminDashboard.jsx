import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
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
  UserCog,
  Edit,
  MessageSquare,
  Send,
  AlertTriangle,
  Activity,
  TrendingUp,
  Zap,
  Settings,
  Eye,
  Ban,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

// Only this email can access
const SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com";

// Dashboard subscription plans
const DASHBOARD_PLANS = [
  { id: "1month", name: "1 Month", days: 30 },
  { id: "6month", name: "6 Months", days: 180 },
  { id: "12month", name: "12 Months", days: 365 },
  { id: "lifetime", name: "Lifetime", days: 36500 },
];

export default function SuperAdminDashboard() {
  const [activeTab, setActiveTab] = useState("overview");
  const [allUsers, setAllUsers] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [userFilter, setUserFilter] = useState("all");
  const [ticketFilter, setTicketFilter] = useState("all");
  const [stats, setStats] = useState({});
  const [changePlanDialog, setChangePlanDialog] = useState({ open: false, user: null });
  const [selectedPlan, setSelectedPlan] = useState("");
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
      const [usersRes, statsRes, ticketsRes] = await Promise.all([
        axios.get(`${API}/admin/all-users`, getAuthHeaders()),
        axios.get(`${API}/admin/stats`, getAuthHeaders()),
        axios.get(`${API}/admin/support/tickets`, getAuthHeaders()),
      ]);
      setAllUsers(usersRes.data);
      setStats(statsRes.data);
      setTickets(ticketsRes.data);
    } catch (error) {
      toast.error("Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  // Handler functions
  const handleSetLifetime = async (userId) => {
    if (!window.confirm("Give lifetime access to this user?")) return;
    try {
      await axios.put(`${API}/admin/set-lifetime/${userId}`, {}, getAuthHeaders());
      toast.success("Lifetime access granted!");
      fetchData();
    } catch (error) {
      toast.error("Failed to set lifetime");
    }
  };

  const handleRevokeAccess = async (userId) => {
    if (!window.confirm("Revoke access for this user?")) return;
    try {
      await axios.put(`${API}/admin/revoke-access/${userId}`, {}, getAuthHeaders());
      toast.success("Access revoked");
      fetchData();
    } catch (error) {
      toast.error("Failed to revoke");
    }
  };

  const handleMakeAdmin = async (userId) => {
    if (!window.confirm("Make this user an admin? (Limited powers)")) return;
    try {
      await axios.put(`${API}/admin/make-admin/${userId}`, {}, getAuthHeaders());
      toast.success("User is now an admin!");
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to make admin");
    }
  };

  const handleRemoveAdmin = async (userId) => {
    if (!window.confirm("Remove admin status from this user?")) return;
    try {
      await axios.put(`${API}/admin/remove-admin/${userId}`, {}, getAuthHeaders());
      toast.success("Admin status removed");
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to remove admin");
    }
  };

  const handleChangePlan = async () => {
    if (!changePlanDialog.user || !selectedPlan) return;
    try {
      await axios.put(
        `${API}/admin/change-subscription/${changePlanDialog.user.id}`,
        { plan_id: selectedPlan },
        getAuthHeaders()
      );
      toast.success("Subscription plan changed!");
      setChangePlanDialog({ open: false, user: null });
      setSelectedPlan("");
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to change plan");
    }
  };

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

  // Filter users
  const filteredUsers = allUsers.filter((u) => {
    const matchesSearch = 
      u.email?.toLowerCase().includes(search.toLowerCase()) ||
      u.name?.toLowerCase().includes(search.toLowerCase());
    
    if (userFilter === "all") return matchesSearch;
    if (userFilter === "active") return matchesSearch && u.dashboard_subscription_status === "active";
    if (userFilter === "inactive") return matchesSearch && u.dashboard_subscription_status !== "active";
    if (userFilter === "admin") return matchesSearch && u.is_admin;
    return matchesSearch;
  });

  // Filter tickets
  const filteredTickets = tickets.filter((t) => {
    if (ticketFilter === "all") return true;
    return t.status === ticketFilter;
  });

  // Calculate additional stats
  const adminCount = allUsers.filter(u => u.is_admin).length;
  const openTicketsCount = tickets.filter(t => t.status === "open").length;
  const lifetimeUsers = allUsers.filter(u => u.dashboard_plan === "lifetime").length;

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
                  Complete system management • {user.email}
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
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
          <Card className="bg-gradient-to-br from-blue-500/20 to-blue-600/10 border-blue-500/30 backdrop-blur">
            <CardContent className="p-4 text-center">
              <Users className="w-8 h-8 text-blue-400 mx-auto mb-2" />
              <p className="text-3xl font-bold text-white">{stats.total_users || 0}</p>
              <p className="text-blue-300 text-xs">Total Users</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-green-500/20 to-green-600/10 border-green-500/30 backdrop-blur">
            <CardContent className="p-4 text-center">
              <CheckCircle className="w-8 h-8 text-green-400 mx-auto mb-2" />
              <p className="text-3xl font-bold text-white">{stats.active_subscribers || 0}</p>
              <p className="text-green-300 text-xs">Active Subs</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-purple-500/20 to-purple-600/10 border-purple-500/30 backdrop-blur">
            <CardContent className="p-4 text-center">
              <Crown className="w-8 h-8 text-purple-400 mx-auto mb-2" />
              <p className="text-3xl font-bold text-white">{lifetimeUsers}</p>
              <p className="text-purple-300 text-xs">Lifetime</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-orange-500/20 to-orange-600/10 border-orange-500/30 backdrop-blur">
            <CardContent className="p-4 text-center">
              <Shield className="w-8 h-8 text-orange-400 mx-auto mb-2" />
              <p className="text-3xl font-bold text-white">{adminCount}</p>
              <p className="text-orange-300 text-xs">Admins</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-yellow-500/20 to-yellow-600/10 border-yellow-500/30 backdrop-blur">
            <CardContent className="p-4 text-center">
              <MessageSquare className="w-8 h-8 text-yellow-400 mx-auto mb-2" />
              <p className="text-3xl font-bold text-white">{openTicketsCount}</p>
              <p className="text-yellow-300 text-xs">Open Tickets</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 backdrop-blur">
            <CardContent className="p-4 text-center">
              <IndianRupee className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
              <p className="text-3xl font-bold text-white">₹{stats.total_revenue || 0}</p>
              <p className="text-emerald-300 text-xs">Revenue</p>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="bg-black/40 border border-purple-500/30 p-1">
            <TabsTrigger 
              value="overview" 
              className="data-[state=active]:bg-purple-500 data-[state=active]:text-white text-purple-200"
            >
              <Activity className="w-4 h-4 mr-2" />
              User Management
            </TabsTrigger>
            <TabsTrigger 
              value="support" 
              className="data-[state=active]:bg-purple-500 data-[state=active]:text-white text-purple-200"
            >
              <MessageSquare className="w-4 h-4 mr-2" />
              Support Tickets
              {openTicketsCount > 0 && (
                <Badge className="ml-2 bg-yellow-500 text-black">{openTicketsCount}</Badge>
              )}
            </TabsTrigger>
          </TabsList>

          {/* User Management Tab */}
          <TabsContent value="overview" className="space-y-6">
            {/* Search & Filter */}
            <Card className="bg-black/40 border-purple-500/30 backdrop-blur">
              <CardContent className="p-4">
                <div className="flex flex-col md:flex-row gap-4">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-purple-400" />
                    <Input
                      placeholder="Search by email or name..."
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      className="pl-10 bg-black/30 border-purple-500/30 text-white placeholder:text-purple-400"
                    />
                  </div>
                  <Select value={userFilter} onValueChange={setUserFilter}>
                    <SelectTrigger className="w-[180px] bg-black/30 border-purple-500/30 text-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Users</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="inactive">Inactive</SelectItem>
                      <SelectItem value="admin">Admins Only</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            {/* Users Table */}
            <Card className="bg-black/40 border-purple-500/30 backdrop-blur overflow-hidden">
              <CardHeader className="border-b border-purple-500/30">
                <CardTitle className="text-white flex items-center gap-2">
                  <Users className="w-5 h-5 text-purple-400" />
                  All Users ({filteredUsers.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-purple-500/30 hover:bg-transparent">
                        <TableHead className="text-purple-300">User</TableHead>
                        <TableHead className="text-purple-300">Role</TableHead>
                        <TableHead className="text-purple-300">Plan</TableHead>
                        <TableHead className="text-purple-300">Status</TableHead>
                        <TableHead className="text-purple-300">Expires</TableHead>
                        <TableHead className="text-purple-300 text-right">Quick Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredUsers.map((u) => (
                        <TableRow key={u.id} className="border-purple-500/20 hover:bg-purple-500/10">
                          <TableCell>
                            <div className="flex items-center gap-3">
                              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                                u.email === SUPER_ADMIN_EMAIL 
                                  ? "bg-gradient-to-br from-purple-500 to-pink-500" 
                                  : u.is_admin 
                                    ? "bg-gradient-to-br from-blue-500 to-cyan-500"
                                    : "bg-gradient-to-br from-slate-600 to-slate-700"
                              }`}>
                                {u.email === SUPER_ADMIN_EMAIL ? (
                                  <Crown className="w-5 h-5 text-white" />
                                ) : u.is_admin ? (
                                  <Shield className="w-5 h-5 text-white" />
                                ) : (
                                  <User className="w-5 h-5 text-white" />
                                )}
                              </div>
                              <div>
                                <p className="font-medium text-white">{u.name || "No Name"}</p>
                                <p className="text-xs text-purple-300">{u.email}</p>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            {u.email === SUPER_ADMIN_EMAIL ? (
                              <Badge className="bg-gradient-to-r from-purple-500 to-pink-500 text-white border-0">
                                Super Admin
                              </Badge>
                            ) : u.is_admin ? (
                              <Badge className="bg-blue-500/20 text-blue-300 border-blue-500/50">
                                Admin
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="text-slate-300 border-slate-500">
                                User
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            {u.dashboard_plan ? (
                              <Badge className={`${
                                u.dashboard_plan === "lifetime" 
                                  ? "bg-purple-500/20 text-purple-300 border-purple-500/50" 
                                  : "bg-slate-500/20 text-slate-300 border-slate-500/50"
                              }`}>
                                {u.dashboard_plan}
                              </Badge>
                            ) : (
                              <span className="text-slate-500">-</span>
                            )}
                          </TableCell>
                          <TableCell>
                            <Badge className={`${
                              u.dashboard_subscription_status === "active"
                                ? "bg-green-500/20 text-green-300 border-green-500/50"
                                : u.dashboard_subscription_status === "expired"
                                  ? "bg-red-500/20 text-red-300 border-red-500/50"
                                  : "bg-slate-500/20 text-slate-400 border-slate-500/50"
                            }`}>
                              {u.dashboard_subscription_status || "inactive"}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-slate-300 text-sm">
                            {u.dashboard_subscription_end ? formatDate(u.dashboard_subscription_end) : "-"}
                          </TableCell>
                          <TableCell>
                            {u.email !== SUPER_ADMIN_EMAIL && (
                              <div className="flex justify-end gap-1">
                                {/* Change Plan */}
                                <Button 
                                  size="sm" 
                                  variant="ghost"
                                  onClick={() => {
                                    setChangePlanDialog({ open: true, user: u });
                                    setSelectedPlan(u.dashboard_plan || "");
                                  }}
                                  className="h-8 w-8 p-0 text-blue-400 hover:text-blue-300 hover:bg-blue-500/20"
                                  title="Change Plan"
                                >
                                  <Edit className="w-4 h-4" />
                                </Button>
                                
                                {/* Lifetime */}
                                {u.dashboard_plan !== "lifetime" && (
                                  <Button 
                                    size="sm" 
                                    variant="ghost"
                                    onClick={() => handleSetLifetime(u.id)} 
                                    className="h-8 w-8 p-0 text-purple-400 hover:text-purple-300 hover:bg-purple-500/20"
                                    title="Give Lifetime"
                                  >
                                    <Crown className="w-4 h-4" />
                                  </Button>
                                )}
                                
                                {/* Admin Toggle */}
                                {u.is_admin ? (
                                  <Button 
                                    size="sm" 
                                    variant="ghost"
                                    onClick={() => handleRemoveAdmin(u.id)} 
                                    className="h-8 w-8 p-0 text-orange-400 hover:text-orange-300 hover:bg-orange-500/20"
                                    title="Remove Admin"
                                  >
                                    <UserCog className="w-4 h-4" />
                                  </Button>
                                ) : (
                                  <Button 
                                    size="sm" 
                                    variant="ghost"
                                    onClick={() => handleMakeAdmin(u.id)} 
                                    className="h-8 w-8 p-0 text-green-400 hover:text-green-300 hover:bg-green-500/20"
                                    title="Make Admin"
                                  >
                                    <Shield className="w-4 h-4" />
                                  </Button>
                                )}
                                
                                {/* Revoke */}
                                {u.dashboard_subscription_status === "active" && (
                                  <Button 
                                    size="sm" 
                                    variant="ghost"
                                    onClick={() => handleRevokeAccess(u.id)} 
                                    className="h-8 w-8 p-0 text-red-400 hover:text-red-300 hover:bg-red-500/20"
                                    title="Revoke Access"
                                  >
                                    <Ban className="w-4 h-4" />
                                  </Button>
                                )}
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Support Tickets Tab */}
          <TabsContent value="support" className="space-y-6">
            {/* Ticket Filter */}
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

            {/* Tickets List */}
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
                                ? "bg-yellow-500/20 text-yellow-300 border-yellow-500/50"
                                : ticket.status === "in_progress"
                                  ? "bg-blue-500/20 text-blue-300 border-blue-500/50"
                                  : "bg-green-500/20 text-green-300 border-green-500/50"
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
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {formatDate(ticket.created_at)}
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

                    {/* Expanded Content */}
                    {expandedTicket === ticket.id && (
                      <div className="border-t border-purple-500/30">
                        {/* Messages */}
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

                        {/* Reply Box */}
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

        {/* Change Plan Dialog */}
        <Dialog open={changePlanDialog.open} onOpenChange={(open) => setChangePlanDialog({ ...changePlanDialog, open })}>
          <DialogContent className="bg-slate-900 border-purple-500/30">
            <DialogHeader>
              <DialogTitle className="text-white">Change Subscription Plan</DialogTitle>
            </DialogHeader>
            {changePlanDialog.user && (
              <div className="space-y-4 mt-4">
                <div className="p-4 bg-black/30 rounded-lg border border-purple-500/30">
                  <p className="text-purple-300 text-sm">User</p>
                  <p className="text-white font-medium">{changePlanDialog.user.name}</p>
                  <p className="text-purple-400 text-sm">{changePlanDialog.user.email}</p>
                </div>
                
                <div className="space-y-2">
                  <p className="text-purple-300 text-sm">Select Plan</p>
                  <Select value={selectedPlan} onValueChange={setSelectedPlan}>
                    <SelectTrigger className="bg-black/30 border-purple-500/30 text-white">
                      <SelectValue placeholder="Choose a plan" />
                    </SelectTrigger>
                    <SelectContent>
                      {DASHBOARD_PLANS.map((plan) => (
                        <SelectItem key={plan.id} value={plan.id}>
                          {plan.name} ({plan.days} days)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex gap-2">
                  <Button 
                    className="flex-1 bg-purple-500 hover:bg-purple-600" 
                    onClick={handleChangePlan}
                    disabled={!selectedPlan}
                  >
                    <CheckCircle className="w-4 h-4 mr-2" />
                    Update Plan
                  </Button>
                  <Button 
                    variant="outline" 
                    className="border-purple-500/30 text-purple-300"
                    onClick={() => setChangePlanDialog({ open: false, user: null })}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
