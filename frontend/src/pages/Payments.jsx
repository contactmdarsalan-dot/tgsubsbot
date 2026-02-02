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
  CreditCard,
  Search,
  Filter,
  CheckCircle,
  Clock,
  XCircle,
  QrCode,
  IndianRupee,
  Image,
  Eye,
  X,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function Payments() {
  const [payments, setPayments] = useState([]);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [screenshotModal, setScreenshotModal] = useState({ open: false, url: "", payment: null });
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [form, setForm] = useState({
    telegram_user_id: "",
    plan_id: "",
    amount: "",
  });

  useEffect(() => {
    fetchData();
  }, [filter]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [paymentsResponse, plansResponse] = await Promise.all([
        axios.get(`${API}/payments${filter !== "all" ? `?status=${filter}` : ""}`, getAuthHeaders()),
        axios.get(`${API}/plans`, getAuthHeaders()),
      ]);
      setPayments(paymentsResponse.data);
      setPlans(plansResponse.data);
    } catch (error) {
      toast.error("Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateManual = async (e) => {
    e.preventDefault();
    try {
      await axios.post(
        `${API}/payments/manual`,
        {
          telegram_user_id: form.telegram_user_id,
          plan_id: form.plan_id,
          amount: parseFloat(form.amount),
          payment_method: "manual",
        },
        getAuthHeaders()
      );
      toast.success("Manual payment created. Verify after receiving payment.");
      setDialogOpen(false);
      resetForm();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to create payment");
    }
  };

  const handleVerify = async (paymentId) => {
    try {
      await axios.put(`${API}/payments/${paymentId}/verify-manual`, {}, getAuthHeaders());
      toast.success("Payment verified and subscriber added");
      fetchData();
    } catch (error) {
      toast.error("Failed to verify payment");
    }
  };

  const resetForm = () => {
    setForm({
      telegram_user_id: "",
      plan_id: "",
      amount: "",
    });
  };

  const handlePlanChange = (planId) => {
    const plan = plans.find((p) => p.id === planId);
    setForm({
      ...form,
      plan_id: planId,
      amount: plan ? plan.price.toString() : "",
    });
  };

  const filteredPayments = payments.filter((p) =>
    p.telegram_user_id.includes(search)
  );

  const getStatusIcon = (status) => {
    switch (status) {
      case "verified":
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case "pending":
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case "failed":
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      verified: "bg-green-100 text-green-700",
      pending: "bg-yellow-100 text-yellow-700",
      failed: "bg-red-100 text-red-700",
    };
    return (
      <Badge className={`flex items-center gap-1 ${styles[status] || ""}`}>
        {getStatusIcon(status)}
        {status}
      </Badge>
    );
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-IN", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Calculate totals
  const totalVerified = payments
    .filter((p) => p.status === "verified")
    .reduce((sum, p) => sum + p.amount, 0);
  const pendingCount = payments.filter((p) => p.status === "pending").length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-4xl font-bold tracking-tight">Payments</h1>
          <p className="text-muted-foreground mt-1">
            Track and verify subscription payments
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) resetForm();
        }}>
          <DialogTrigger asChild>
            <Button className="btn-hover" data-testid="create-payment-btn">
              <Plus className="w-4 h-4 mr-2" />
              Record Payment
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle className="font-heading text-xl font-bold">
                Record Manual Payment
              </DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreateManual} className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label htmlFor="telegram_user_id">Telegram User ID</Label>
                <Input
                  id="telegram_user_id"
                  value={form.telegram_user_id}
                  onChange={(e) => setForm({ ...form, telegram_user_id: e.target.value })}
                  placeholder="e.g., 123456789"
                  required
                  data-testid="payment-userid-input"
                  className="bg-muted/50 border-transparent focus:border-primary"
                />
              </div>

              <div className="space-y-2">
                <Label>Subscription Plan</Label>
                <Select value={form.plan_id} onValueChange={handlePlanChange}>
                  <SelectTrigger data-testid="payment-plan-select" className="bg-muted/50 border-transparent">
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
                <Label htmlFor="amount">Amount (₹)</Label>
                <Input
                  id="amount"
                  type="number"
                  value={form.amount}
                  onChange={(e) => setForm({ ...form, amount: e.target.value })}
                  placeholder="Amount received"
                  required
                  data-testid="payment-amount-input"
                  className="bg-muted/50 border-transparent focus:border-primary"
                />
              </div>

              <div className="p-4 bg-muted/50 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <QrCode className="w-4 h-4" />
                  <span>This creates a pending payment. Verify after receiving.</span>
                </div>
              </div>

              <Button type="submit" className="w-full btn-hover" data-testid="payment-submit-btn">
                Record Payment
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border card-hover" data-testid="total-collected">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Collected</p>
                <p className="font-heading text-3xl font-bold mt-1 font-mono">
                  ₹{totalVerified.toLocaleString("en-IN")}
                </p>
              </div>
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
                <IndianRupee className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border card-hover" data-testid="pending-verifications">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Pending Verification</p>
                <p className="font-heading text-3xl font-bold mt-1">{pendingCount}</p>
              </div>
              <div className="w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center">
                <Clock className="w-6 h-6 text-yellow-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border card-hover" data-testid="total-transactions">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Transactions</p>
                <p className="font-heading text-3xl font-bold mt-1">{payments.length}</p>
              </div>
              <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
                <CreditCard className="w-6 h-6 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="border">
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search by Telegram User ID..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                data-testid="payment-search-input"
                className="pl-10 bg-muted/50 border-transparent focus:border-primary"
              />
            </div>
            <Select value={filter} onValueChange={setFilter}>
              <SelectTrigger className="w-[160px] bg-muted/50 border-transparent" data-testid="payment-filter">
                <Filter className="w-4 h-4 mr-2" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Payments</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="verified">Verified</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Payments Table */}
      <Card className="border">
        <CardContent className="p-0">
          {filteredPayments.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/50">
                    <TableHead className="font-heading font-bold">User</TableHead>
                    <TableHead className="font-heading font-bold">Plan</TableHead>
                    <TableHead className="font-heading font-bold">Amount</TableHead>
                    <TableHead className="font-heading font-bold">Status</TableHead>
                    <TableHead className="font-heading font-bold">Date</TableHead>
                    <TableHead className="font-heading font-bold text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPayments.map((payment) => (
                    <TableRow key={payment.id} className="hover:bg-muted/30" data-testid={`payment-row-${payment.id}`}>
                      <TableCell>
                        <div>
                          <p className="font-mono text-sm font-medium">
                            {payment.telegram_username ? `@${payment.telegram_username}` : payment.telegram_user_id}
                          </p>
                          {payment.telegram_username && (
                            <p className="text-xs text-muted-foreground">{payment.telegram_user_id}</p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="font-medium">{payment.plan_name || "-"}</TableCell>
                      <TableCell className="font-mono font-medium">
                        ₹{payment.amount.toLocaleString("en-IN")}
                      </TableCell>
                      <TableCell>{getStatusBadge(payment.status)}</TableCell>
                      <TableCell className="font-mono text-sm">{formatDate(payment.created_at)}</TableCell>
                      <TableCell className="text-right">
                        {payment.status === "pending" && (
                          <Button
                            size="sm"
                            onClick={() => handleVerify(payment.id)}
                            data-testid={`verify-payment-${payment.id}`}
                            className="btn-hover"
                          >
                            <CheckCircle className="w-4 h-4 mr-1" />
                            Verify
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16">
              <CreditCard className="w-12 h-12 text-muted-foreground mb-4" />
              <h3 className="font-heading text-xl font-bold mb-2">No Payments Found</h3>
              <p className="text-muted-foreground text-center">
                {search || filter !== "all"
                  ? "No payments match your filters"
                  : "Payments will appear here when users subscribe"}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
