import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { toast } from "sonner";
import {
  Plus,
  Trash2,
  Users,
  Search,
  RefreshCw,
  Filter,
  UserX,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function Subscribers() {
  const [subscribers, setSubscribers] = useState([]);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [renewDialogOpen, setRenewDialogOpen] = useState(false);
  const [selectedSubscriber, setSelectedSubscriber] = useState(null);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [serverStats, setServerStats] = useState({ total_subscribers: 0, active_count: 0, expired_count: 0 });
  const [form, setForm] = useState({
    telegram_user_id: "",
    telegram_username: "",
    plan_id: "",
    payment_method: "manual",
  });
  const [bulkAdding, setBulkAdding] = useState(false);

  useEffect(() => {
    fetchData();
  }, [filter, page]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter !== "all") params.append("status", filter);
      params.append("page", page);
      params.append("limit", 50);
      if (search.trim()) params.append("search", search.trim());
      
      const [subsResponse, plansResponse] = await Promise.all([
        axios.get(`${API}/subscribers?${params.toString()}`, getAuthHeaders()),
        axios.get(`${API}/plans`, getAuthHeaders()),
      ]);
      const data = subsResponse.data;
      setSubscribers(data.subscribers || data);
      setTotalPages(data.total_pages || 1);
      setTotalCount(data.total || 0);
      if (data.stats) setServerStats(data.stats);
      setPlans(plansResponse.data);
    } catch (error) {
      toast.error("Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/subscribers`, form, getAuthHeaders());
      toast.success("Subscriber added successfully");
      setDialogOpen(false);
      resetForm();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to add subscriber");
    }
  };

  const handleRenew = async () => {
    if (!selectedSubscriber || !form.plan_id) return;
    try {
      await axios.put(
        `${API}/subscribers/${selectedSubscriber.id}/renew?plan_id=${form.plan_id}`,
        {},
        getAuthHeaders()
      );
      toast.success("Subscription renewed");
      setRenewDialogOpen(false);
      setSelectedSubscriber(null);
      fetchData();
    } catch (error) {
      toast.error("Failed to renew subscription");
    }
  };

  const handleDelete = async (subscriberId) => {
    if (!window.confirm("Remove this subscriber? They will be removed from the channel.")) return;
    try {
      await axios.delete(`${API}/subscribers/${subscriberId}`, getAuthHeaders());
      toast.success("Subscriber removed");
      fetchData();
    } catch (error) {
      toast.error("Failed to remove subscriber");
    }
  };

  const resetForm = () => {
    setForm({
      telegram_user_id: "",
      telegram_username: "",
      plan_id: "",
      payment_method: "manual",
    });
  };

  // Server-side filtering - subscribers are already filtered
  const filteredSubscribers = subscribers;

  const getStatusBadge = (status) => {
    const styles = {
      active: "bg-green-100 text-green-700",
      grace: "bg-yellow-100 text-yellow-700",
      expired: "bg-red-100 text-red-700",
    };
    return <Badge className={styles[status] || ""}>{status}</Badge>;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-IN", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  const handleBulkAddToChannel = async () => {
    if (!window.confirm("Sab active subscribers ko channel mein add karna hai? Ye sabko invite link bhejega.")) return;
    setBulkAdding(true);
    try {
      const response = await axios.post(`${API}/subscribers/bulk-add-to-channel`, {}, getAuthHeaders());
      const data = response.data;
      toast.success(`Done! ${data.success} added, ${data.failed} failed out of ${data.total}`);
    } catch (error) {
      toast.error("Failed to bulk add subscribers");
    } finally {
      setBulkAdding(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-4xl font-bold tracking-tight text-white">Subscribers</h1>
          <p className="text-muted-foreground mt-1">
            Manage your channel members and subscriptions
          </p>
        </div>
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            onClick={handleBulkAddToChannel} 
            disabled={bulkAdding}
            data-testid="bulk-add-channel-btn"
            className="border-green-600 text-green-500 hover:bg-green-900/30"
          >
            <Users className="w-4 h-4 mr-2" />
            {bulkAdding ? "Adding..." : "Bulk Add to Channel"}
          </Button>
          <Dialog open={dialogOpen} onOpenChange={(open) => {
            setDialogOpen(open);
            if (!open) resetForm();
          }}>
          <DialogTrigger asChild>
            <Button className="btn-hover" data-testid="add-subscriber-btn">
              <Plus className="w-4 h-4 mr-2" />
              Add Subscriber
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle className="font-heading text-xl font-bold">
                Add New Subscriber
              </DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label htmlFor="telegram_user_id">Telegram User ID</Label>
                <Input
                  id="telegram_user_id"
                  value={form.telegram_user_id}
                  onChange={(e) => setForm({ ...form, telegram_user_id: e.target.value })}
                  placeholder="e.g., 123456789"
                  required
                  data-testid="subscriber-userid-input"
                  className="bg-muted/50 border-transparent focus:border-primary"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="telegram_username">Username (Optional)</Label>
                <Input
                  id="telegram_username"
                  value={form.telegram_username}
                  onChange={(e) => setForm({ ...form, telegram_username: e.target.value })}
                  placeholder="@username"
                  data-testid="subscriber-username-input"
                  className="bg-muted/50 border-transparent focus:border-primary"
                />
              </div>

              <div className="space-y-2">
                <Label>Subscription Plan</Label>
                <Select
                  value={form.plan_id}
                  onValueChange={(value) => setForm({ ...form, plan_id: value })}
                >
                  <SelectTrigger data-testid="subscriber-plan-select" className="bg-muted/50 border-transparent">
                    <SelectValue placeholder="Select a plan" />
                  </SelectTrigger>
                  <SelectContent>
                    {plans.filter(p => p.is_active).map((plan) => (
                      <SelectItem key={plan.id} value={plan.id}>
                        {plan.name} - ₹{plan.price}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Payment Method</Label>
                <Select
                  value={form.payment_method}
                  onValueChange={(value) => setForm({ ...form, payment_method: value })}
                >
                  <SelectTrigger data-testid="subscriber-payment-select" className="bg-muted/50 border-transparent">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manual">Manual/QR</SelectItem>
                    <SelectItem value="razorpay">Razorpay</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button type="submit" className="w-full btn-hover" data-testid="subscriber-submit-btn">
                Add Subscriber
              </Button>
            </form>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {/* Filters */}
      <Card className="border">
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search by user ID or username..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { setPage(1); fetchData(); } }}
                data-testid="subscriber-search-input"
                className="pl-10 bg-muted/50 border-transparent focus:border-primary"
              />
            </div>
            <div className="flex gap-2">
              <Select value={filter} onValueChange={(val) => { setFilter(val); setPage(1); }}>
                <SelectTrigger className="w-[140px] bg-muted/50 border-transparent" data-testid="subscriber-filter">
                  <Filter className="w-4 h-4 mr-2" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="grace">Grace</SelectItem>
                  <SelectItem value="expired">Expired</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline" size="icon" onClick={fetchData} data-testid="refresh-subscribers">
                <RefreshCw className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Subscribers Table */}
      <Card className="border">
        <CardContent className="p-0">
          {filteredSubscribers.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/50">
                    <TableHead className="font-heading font-bold">User</TableHead>
                    <TableHead className="font-heading font-bold">Telegram ID</TableHead>
                    <TableHead className="font-heading font-bold">Channel ID</TableHead>
                    <TableHead className="font-heading font-bold">Group Name</TableHead>
                    <TableHead className="font-heading font-bold">Plan</TableHead>
                    <TableHead className="font-heading font-bold">Status</TableHead>
                    <TableHead className="font-heading font-bold">Start</TableHead>
                    <TableHead className="font-heading font-bold">End</TableHead>
                    <TableHead className="font-heading font-bold">Payment</TableHead>
                    <TableHead className="font-heading font-bold text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredSubscribers.map((sub) => (
                    <TableRow key={sub.id} className="hover:bg-muted/30" data-testid={`subscriber-row-${sub.id}`}>
                      <TableCell>
                        <div>
                          <p className="font-mono text-sm font-medium">
                            {sub.telegram_username ? `@${sub.telegram_username}` : sub.telegram_user_id}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-sm" data-testid={`subscriber-telegram-id-${sub.id}`}>
                          {sub.telegram_user_id || "-"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-xs" data-testid={`subscriber-channel-id-${sub.id}`}>
                          {sub.channel_id || "-"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm" data-testid={`subscriber-group-name-${sub.id}`}>
                          {sub.group_name || "-"}
                        </span>
                      </TableCell>
                      <TableCell>{sub.plan_name}</TableCell>
                      <TableCell>{getStatusBadge(sub.status)}</TableCell>
                      <TableCell className="font-mono text-sm">{formatDate(sub.start_date)}</TableCell>
                      <TableCell className="font-mono text-sm">{formatDate(sub.end_date)}</TableCell>
                      <TableCell className="capitalize">{sub.payment_method}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setSelectedSubscriber(sub);
                              setForm({ ...form, plan_id: sub.plan_id });
                              setRenewDialogOpen(true);
                            }}
                            data-testid={`renew-subscriber-${sub.id}`}
                          >
                            <RefreshCw className="w-4 h-4 mr-1" />
                            Renew
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDelete(sub.id)}
                            data-testid={`delete-subscriber-${sub.id}`}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16">
              <UserX className="w-12 h-12 text-muted-foreground mb-4" />
              <h3 className="font-heading text-xl font-bold mb-2">No Subscribers Found</h3>
              <p className="text-muted-foreground text-center">
                {search || filter !== "all"
                  ? "No subscribers match your filters"
                  : "Add your first subscriber to get started"}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-2" data-testid="subscribers-pagination">
          <p className="text-sm text-muted-foreground">
            Showing {((page - 1) * 50) + 1}-{Math.min(page * 50, totalCount)} of {totalCount} subscribers
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setPage(1)} disabled={page <= 1}>First</Button>
            <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}>
              <ChevronLeft className="w-4 h-4" /> Prev
            </Button>
            <span className="text-sm font-medium px-3">Page {page} of {totalPages}</span>
            <Button variant="outline" size="sm" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>
              Next <ChevronRight className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={() => setPage(totalPages)} disabled={page >= totalPages}>Last</Button>
          </div>
        </div>
      )}

      {/* Renew Dialog */}
      <Dialog open={renewDialogOpen} onOpenChange={setRenewDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="font-heading text-xl font-bold">
              Renew Subscription
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <p className="text-muted-foreground">
              Renewing subscription for{" "}
              <span className="font-mono font-medium">
                {selectedSubscriber?.telegram_username
                  ? `@${selectedSubscriber.telegram_username}`
                  : selectedSubscriber?.telegram_user_id}
              </span>
            </p>

            <div className="space-y-2">
              <Label>Select Plan</Label>
              <Select
                value={form.plan_id}
                onValueChange={(value) => setForm({ ...form, plan_id: value })}
              >
                <SelectTrigger data-testid="renew-plan-select" className="bg-muted/50 border-transparent">
                  <SelectValue placeholder="Select a plan" />
                </SelectTrigger>
                <SelectContent>
                  {plans.filter(p => p.is_active).map((plan) => (
                    <SelectItem key={plan.id} value={plan.id}>
                      {plan.name} - ₹{plan.price} ({plan.duration_days} days)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button onClick={handleRenew} className="w-full btn-hover" data-testid="confirm-renew-btn">
              Confirm Renewal
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
