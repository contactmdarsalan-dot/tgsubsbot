import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
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
  const [requests, setRequests] = useState([]);
  const [allUsers, setAllUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [stats, setStats] = useState({});
  const [changePlanDialog, setChangePlanDialog] = useState({ open: false, user: null });
  const [selectedPlan, setSelectedPlan] = useState("");
  
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
      const [requestsRes, usersRes, statsRes] = await Promise.all([
        axios.get(`${API}/admin/subscription-requests`, getAuthHeaders()),
        axios.get(`${API}/admin/all-users`, getAuthHeaders()),
        axios.get(`${API}/admin/stats`, getAuthHeaders())
      ]);
      setRequests(requestsRes.data);
      setAllUsers(usersRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (requestId) => {
    try {
      await axios.put(`${API}/dashboard-subscription/approve/${requestId}`, {}, getAuthHeaders());
      toast.success("Subscription approved!");
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to approve");
    }
  };

  const handleReject = async (requestId) => {
    if (!window.confirm("Reject this subscription request?")) return;
    try {
      await axios.put(`${API}/admin/reject-subscription/${requestId}`, {}, getAuthHeaders());
      toast.success("Request rejected");
      fetchData();
    } catch (error) {
      toast.error("Failed to reject");
    }
  };

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

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("en-IN", {
      year: "numeric",
      month: "short",
      day: "numeric"
    });
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending: "bg-yellow-100 text-yellow-700",
      approved: "bg-green-100 text-green-700",
      rejected: "bg-red-100 text-red-700",
      active: "bg-green-100 text-green-700",
      inactive: "bg-gray-100 text-gray-700",
      expired: "bg-red-100 text-red-700",
    };
    return <Badge className={styles[status] || "bg-gray-100"}>{status}</Badge>;
  };

  const filteredRequests = requests.filter(r => {
    if (filter !== "all" && r.status !== filter) return false;
    if (search && !r.user_email?.toLowerCase().includes(search.toLowerCase()) && 
        !r.user_name?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const filteredUsers = allUsers.filter(u => {
    if (search && !u.email?.toLowerCase().includes(search.toLowerCase()) && 
        !u.name?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  if (!isSuperAdmin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-background to-muted/30">
        <Card className="max-w-md">
          <CardContent className="p-8 text-center">
            <Shield className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <h1 className="font-heading text-2xl font-bold mb-2">Access Denied</h1>
            <p className="text-muted-foreground">
              This page is restricted to Super Admin only.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/30 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Crown className="w-8 h-8 text-primary" />
              <h1 className="font-heading text-3xl font-bold tracking-tight">
                Super Admin Dashboard
              </h1>
            </div>
            <p className="text-muted-foreground mt-1">
              Manage SubsBot Dashboard Subscriptions
            </p>
          </div>
          <Button onClick={fetchData} variant="outline" className="gap-2">
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="border bg-gradient-to-br from-blue-50 to-white">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Total Users</p>
                  <p className="font-heading text-3xl font-bold">{stats.total_users || 0}</p>
                </div>
                <Users className="w-10 h-10 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          <Card className="border bg-gradient-to-br from-green-50 to-white">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Active Subscribers</p>
                  <p className="font-heading text-3xl font-bold text-green-600">{stats.active_subscribers || 0}</p>
                </div>
                <CheckCircle className="w-10 h-10 text-green-500" />
              </div>
            </CardContent>
          </Card>

          <Card className="border bg-gradient-to-br from-yellow-50 to-white">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Pending Requests</p>
                  <p className="font-heading text-3xl font-bold text-yellow-600">{stats.pending_requests || 0}</p>
                </div>
                <Clock className="w-10 h-10 text-yellow-500" />
              </div>
            </CardContent>
          </Card>

          <Card className="border bg-gradient-to-br from-purple-50 to-white">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Total Revenue</p>
                  <p className="font-heading text-3xl font-bold text-purple-600">₹{(stats.total_revenue || 0).toLocaleString()}</p>
                </div>
                <IndianRupee className="w-10 h-10 text-purple-500" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Search & Filter */}
        <Card className="border">
          <CardContent className="p-4">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Search by email or name..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Select value={filter} onValueChange={setFilter}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Filter" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Subscription Requests */}
        <Card className="border">
          <CardHeader>
            <CardTitle className="font-heading text-lg font-bold flex items-center gap-2">
              <Clock className="w-5 h-5" />
              Subscription Requests ({filteredRequests.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {filteredRequests.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/50">
                      <TableHead>User</TableHead>
                      <TableHead>Plan</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredRequests.map((req) => (
                      <TableRow key={req.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center">
                              <User className="w-4 h-4 text-primary" />
                            </div>
                            <div>
                              <p className="font-medium">{req.user_name}</p>
                              <p className="text-xs text-muted-foreground">{req.user_email}</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="font-medium">{req.plan_name}</TableCell>
                        <TableCell className="font-mono">₹{req.amount?.toLocaleString()}</TableCell>
                        <TableCell>{getStatusBadge(req.status)}</TableCell>
                        <TableCell className="text-sm">{formatDate(req.created_at)}</TableCell>
                        <TableCell className="text-right">
                          {req.status === "pending" && (
                            <div className="flex justify-end gap-2">
                              <Button size="sm" onClick={() => handleApprove(req.id)} className="bg-green-600 hover:bg-green-700">
                                <CheckCircle className="w-4 h-4 mr-1" />
                                Approve
                              </Button>
                              <Button size="sm" variant="outline" onClick={() => handleReject(req.id)} className="text-red-600">
                                <XCircle className="w-4 h-4" />
                              </Button>
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="py-12 text-center text-muted-foreground">
                No subscription requests found
              </div>
            )}
          </CardContent>
        </Card>

        {/* All Users */}
        <Card className="border">
          <CardHeader>
            <CardTitle className="font-heading text-lg font-bold flex items-center gap-2">
              <Users className="w-5 h-5" />
              All Users ({filteredUsers.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {filteredUsers.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/50">
                      <TableHead>User</TableHead>
                      <TableHead>Plan</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Expires</TableHead>
                      <TableHead>Joined</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredUsers.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center">
                              {u.email === SUPER_ADMIN_EMAIL ? (
                                <Crown className="w-4 h-4 text-primary" />
                              ) : (
                                <User className="w-4 h-4 text-primary" />
                              )}
                            </div>
                            <div>
                              <p className="font-medium">{u.name}</p>
                              <p className="text-xs text-muted-foreground flex items-center gap-1">
                                <Mail className="w-3 h-3" />
                                {u.email}
                              </p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          {u.dashboard_plan ? (
                            <Badge variant="outline">{u.dashboard_plan}</Badge>
                          ) : "-"}
                        </TableCell>
                        <TableCell>{getStatusBadge(u.dashboard_subscription_status || "inactive")}</TableCell>
                        <TableCell className="text-sm">
                          {u.dashboard_subscription_end ? (
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {formatDate(u.dashboard_subscription_end)}
                            </span>
                          ) : "-"}
                        </TableCell>
                        <TableCell className="text-sm">{formatDate(u.created_at)}</TableCell>
                        <TableCell className="text-right">
                          {u.email !== SUPER_ADMIN_EMAIL && (
                            <div className="flex justify-end gap-2">
                              {u.dashboard_plan !== "lifetime" && (
                                <Button size="sm" variant="outline" onClick={() => handleSetLifetime(u.id)} className="text-purple-600">
                                  <Crown className="w-4 h-4 mr-1" />
                                  Lifetime
                                </Button>
                              )}
                              {u.dashboard_subscription_status === "active" && (
                                <Button size="sm" variant="outline" onClick={() => handleRevokeAccess(u.id)} className="text-red-600">
                                  <XCircle className="w-4 h-4" />
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
            ) : (
              <div className="py-12 text-center text-muted-foreground">
                No users found
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
