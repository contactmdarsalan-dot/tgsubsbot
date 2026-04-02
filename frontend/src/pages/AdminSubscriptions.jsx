import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
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
  Shield,
  UserCheck,
  Image,
  ExternalLink,
  RefreshCw,
  XCircle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function AdminSubscriptions() {
  const [requests, setRequests] = useState([]);
  const [tenantUsers, setTenantUsers] = useState([]);
  const [platformUsers, setPlatformUsers] = useState([]);
  const [platformStats, setPlatformStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [activeTab, setActiveTab] = useState("users");
  const [screenshotUrl, setScreenshotUrl] = useState(null);

  useEffect(() => {
    checkAdmin();
  }, []);

  const checkAdmin = async () => {
    try {
      const response = await axios.get(`${API}/auth/check-admin`, getAuthHeaders());
      setIsAdmin(response.data.is_admin);
      if (response.data.is_admin) {
        await Promise.all([fetchRequests(), fetchTenantUsers(), fetchPlatformUsers()]);
      }
    } catch {
      setIsAdmin(false);
    } finally {
      setLoading(false);
    }
  };

  const fetchRequests = async () => {
    try {
      const response = await axios.get(`${API}/dashboard-subscription/requests`, getAuthHeaders());
      setRequests(response.data);
    } catch (error) {
      console.error("Failed to fetch requests:", error);
    }
  };

  const fetchTenantUsers = async () => {
    try {
      const response = await axios.get(`${API}/tenant-users`, getAuthHeaders());
      const users = response.data.users || response.data || [];
      setTenantUsers(Array.isArray(users) ? users : []);
      setPlatformStats(response.data.platform_stats || {});
    } catch (error) {
      console.error("Failed to fetch tenant users:", error);
    }
  };

  const fetchPlatformUsers = async () => {
    try {
      const response = await axios.get(`${API}/platform-users`, getAuthHeaders());
      setPlatformUsers(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error("Failed to fetch platform users:", error);
    }
  };

  const handleApprove = async (requestId) => {
    try {
      await axios.put(`${API}/dashboard-subscription/approve/${requestId}`, {}, getAuthHeaders());
      toast.success("Subscription approved!");
      fetchRequests();
      fetchTenantUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to approve");
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      approved: "bg-green-500/20 text-green-400 border-green-500/30",
      rejected: "bg-red-500/20 text-red-400 border-red-500/30",
      active: "bg-green-500/20 text-green-400 border-green-500/30",
      expired: "bg-red-500/20 text-red-400 border-red-500/30",
      inactive: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
    };
    return (
      <Badge className={`${styles[status] || styles.inactive} border`}>
        {status?.charAt(0).toUpperCase() + status?.slice(1) || "None"}
      </Badge>
    );
  };

  const getRoleBadge = (user) => {
    if (user.role === "super_admin") {
      return <Badge className="bg-amber-500/20 text-amber-400 border border-amber-500/30">Super Admin</Badge>;
    }
    if (user.role === "admin" || user.is_admin) {
      return <Badge className="bg-purple-500/20 text-purple-400 border border-purple-500/30">Admin</Badge>;
    }
    return <Badge variant="outline">User</Badge>;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <Crown className="w-12 h-12 text-muted-foreground mb-4" />
        <h2 className="text-xl font-bold">Admin Access Required</h2>
        <p className="text-muted-foreground">Super Admin or Admin role is required to access this page.</p>
      </div>
    );
  }

  const pendingCount = requests.filter((r) => r.status === "pending").length;
  const approvedCount = requests.filter((r) => r.status === "approved").length;
  const activeUsersCount = tenantUsers.filter((u) => u.has_active_plan).length;

  return (
    <div className="space-y-8" data-testid="admin-subs-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">SaaS Management</h1>
          <p className="text-muted-foreground mt-1">Manage tenant users and dashboard subscriptions</p>
        </div>
        <Button variant="outline" onClick={() => { fetchRequests(); fetchTenantUsers(); fetchPlatformUsers(); }}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-primary/10">
                <Users className="w-6 h-6 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Users</p>
                <p className="text-2xl font-bold">{tenantUsers.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-green-500/10">
                <UserCheck className="w-6 h-6 text-green-500" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Active Plans</p>
                <p className="text-2xl font-bold text-green-500">{activeUsersCount}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-yellow-500/10">
                <Clock className="w-6 h-6 text-yellow-500" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Pending Requests</p>
                <p className="text-2xl font-bold text-yellow-500">{pendingCount}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-blue-500/10">
                <CheckCircle className="w-6 h-6 text-blue-500" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Approved</p>
                <p className="text-2xl font-bold text-blue-500">{approvedCount}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab("users")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === "users" ? "text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-white"
          }`}
          data-testid="tab-users"
        >
          Tenant Users ({tenantUsers.length})
        </button>
        <button
          onClick={() => setActiveTab("requests")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === "requests" ? "text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-white"
          }`}
          data-testid="tab-requests"
        >
          Subscription Requests ({requests.length})
          {pendingCount > 0 && (
            <span className="ml-2 inline-flex items-center justify-center w-5 h-5 text-xs font-bold bg-red-500 text-white rounded-full">
              {pendingCount}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab("platform")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === "platform" ? "text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-white"
          }`}
          data-testid="tab-platform"
        >
          Platform Users ({platformUsers.length})
        </button>
      </div>

      {/* Tenant Users Tab */}
      {activeTab === "users" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5" />
              Registered Users
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {tenantUsers.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Plan</TableHead>
                      <TableHead>Subscription Status</TableHead>
                      <TableHead>Plan Expiry</TableHead>
                      <TableHead>Joined</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tenantUsers.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-lime-500/20 to-emerald-600/20 flex items-center justify-center border border-primary/20">
                              <span className="text-xs font-semibold text-primary">
                                {u.name?.charAt(0)?.toUpperCase() || "U"}
                              </span>
                            </div>
                            <div>
                              <p className="font-medium">{u.name || "Unnamed"}</p>
                              <p className="text-xs text-muted-foreground">{u.email}</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>{getRoleBadge(u)}</TableCell>
                        <TableCell>
                          <span className="font-medium">{u.dashboard_plan || "-"}</span>
                        </TableCell>
                        <TableCell>
                          {getStatusBadge(u.dashboard_subscription_status || "inactive")}
                        </TableCell>
                        <TableCell>
                          {u.dashboard_subscription_end ? formatDate(u.dashboard_subscription_end) : "-"}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(u.created_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="text-center py-16">
                <Users className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground">No registered users yet</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Subscription Requests Tab */}
      {activeTab === "requests" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Crown className="w-5 h-5" />
              Subscription Requests
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {requests.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Screenshot</TableHead>
                      <TableHead>User</TableHead>
                      <TableHead>Plan</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {requests.map((request) => (
                      <TableRow key={request.id}>
                        <TableCell>
                          {request.payment_screenshot || request.screenshot_url ? (
                            <button
                              onClick={() => setScreenshotUrl(request.payment_screenshot || request.screenshot_url)}
                              className="group relative w-14 h-14 rounded-lg overflow-hidden bg-muted/50 border border-border/50 hover:border-primary/50 transition-colors"
                              data-testid={`view-screenshot-${request.id}`}
                            >
                              <img
                                src={request.payment_screenshot || request.screenshot_url}
                                alt="Payment"
                                className="w-full h-full object-cover"
                              />
                              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                <Image className="w-5 h-5 text-white" />
                              </div>
                            </button>
                          ) : (
                            <div className="w-14 h-14 rounded-lg bg-muted/30 border border-dashed border-border flex items-center justify-center">
                              <Image className="w-5 h-5 text-muted-foreground" />
                            </div>
                          )}
                        </TableCell>
                        <TableCell>
                          <div>
                            <p className="font-medium">{request.user_name || "Unknown"}</p>
                            <p className="text-xs text-muted-foreground">{request.user_email}</p>
                          </div>
                        </TableCell>
                        <TableCell className="font-medium">{request.plan_name}</TableCell>
                        <TableCell className="font-mono font-medium">
                          {request.amount ? `₹${request.amount.toLocaleString()}` : "-"}
                        </TableCell>
                        <TableCell>{getStatusBadge(request.status)}</TableCell>
                        <TableCell className="text-sm">{formatDate(request.created_at)}</TableCell>
                        <TableCell className="text-right">
                          {request.status === "pending" && (
                            <div className="flex justify-end gap-2">
                              <Button
                                size="sm"
                                onClick={() => handleApprove(request.id)}
                                data-testid={`approve-${request.id}`}
                              >
                                <CheckCircle className="w-4 h-4 mr-1" />
                                Approve
                              </Button>
                            </div>
                          )}
                          {request.status === "approved" && (
                            <Badge className="bg-green-500/20 text-green-400 border border-green-500/30">
                              Approved
                            </Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="text-center py-16">
                <Crown className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="text-lg font-bold mb-2">No Requests Yet</h3>
                <p className="text-muted-foreground">Subscription requests will appear here</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Platform Users Tab */}
      {activeTab === "platform" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5" />
              Platform Users (Bot Users)
              <Badge variant="outline" className="ml-2">{platformUsers.length} total</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {platformUsers.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Telegram ID</TableHead>
                      <TableHead>Subscriber</TableHead>
                      <TableHead>Plan</TableHead>
                      <TableHead>Payments</TableHead>
                      <TableHead>Last Seen</TableHead>
                      <TableHead>Joined</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {platformUsers.map((pu, idx) => (
                      <TableRow key={pu.user_id || idx}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                              <span className="text-xs font-semibold text-blue-400">
                                {pu.first_name?.charAt(0)?.toUpperCase() || pu.username?.charAt(0)?.toUpperCase() || "U"}
                              </span>
                            </div>
                            <div>
                              <p className="font-medium">{pu.first_name || "Unknown"}</p>
                              {pu.username && <p className="text-xs text-muted-foreground">@{pu.username}</p>}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <code className="text-xs bg-muted px-2 py-1 rounded">{pu.user_id}</code>
                        </TableCell>
                        <TableCell>
                          {pu.is_subscriber ? (
                            <Badge className="bg-green-500/20 text-green-400 border border-green-500/30">Active</Badge>
                          ) : (
                            <Badge variant="outline" className="text-muted-foreground">No</Badge>
                          )}
                        </TableCell>
                        <TableCell className="font-medium">{pu.plan_name || "-"}</TableCell>
                        <TableCell>
                          <span className="font-mono">{pu.payment_count || 0}</span>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">{formatDate(pu.last_seen)}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">{formatDate(pu.created_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="text-center py-16">
                <Users className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="text-lg font-bold mb-2">No Platform Users</h3>
                <p className="text-muted-foreground">Users who interact with your Telegram bot will appear here</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Screenshot Preview Dialog */}
      <Dialog open={!!screenshotUrl} onOpenChange={() => setScreenshotUrl(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Payment Screenshot</DialogTitle>
          </DialogHeader>
          <div className="rounded-lg overflow-hidden border border-border">
            {screenshotUrl && (
              <img
                src={screenshotUrl}
                alt="Payment Screenshot"
                className="w-full h-auto max-h-[70vh] object-contain bg-black"
              />
            )}
          </div>
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={() => window.open(screenshotUrl, "_blank")}>
              <ExternalLink className="w-4 h-4 mr-2" />
              Open Full Size
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
