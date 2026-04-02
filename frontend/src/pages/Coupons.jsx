import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Badge } from "../components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { toast } from "sonner";
import {
  Ticket,
  Plus,
  Pencil,
  Trash2,
  Percent,
  IndianRupee,
  Copy,
  CheckCircle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function Coupons() {
  const [coupons, setCoupons] = useState([]);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingCoupon, setEditingCoupon] = useState(null);
  const [copiedCode, setCopiedCode] = useState(null);
  const [form, setForm] = useState({
    code: "",
    discount_type: "percentage",
    discount_value: "",
    min_purchase: "",
    max_uses: "",
    valid_until: "",
    applicable_plans: [],
    is_active: true,
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [couponsRes, plansRes] = await Promise.all([
        axios.get(`${API}/coupons`, getAuthHeaders()),
        axios.get(`${API}/plans`, getAuthHeaders()),
      ]);
      setCoupons(couponsRes.data);
      setPlans(plansRes.data);
    } catch (error) {
      toast.error("Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...form,
        discount_value: parseFloat(form.discount_value) || 0,
        min_purchase: parseFloat(form.min_purchase) || 0,
        max_uses: parseInt(form.max_uses) || 0,
      };

      if (editingCoupon) {
        await axios.put(`${API}/coupons/${editingCoupon.id}`, payload, getAuthHeaders());
        toast.success("Coupon updated successfully");
      } else {
        await axios.post(`${API}/coupons`, payload, getAuthHeaders());
        toast.success("Coupon created successfully");
      }

      setDialogOpen(false);
      resetForm();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to save coupon");
    }
  };

  const handleEdit = (coupon) => {
    setEditingCoupon(coupon);
    setForm({
      code: coupon.code,
      discount_type: coupon.discount_type,
      discount_value: coupon.discount_value.toString(),
      min_purchase: coupon.min_purchase?.toString() || "",
      max_uses: coupon.max_uses?.toString() || "",
      valid_until: coupon.valid_until?.split("T")[0] || "",
      applicable_plans: coupon.applicable_plans || [],
      is_active: coupon.is_active,
    });
    setDialogOpen(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this coupon?")) return;
    try {
      await axios.delete(`${API}/coupons/${id}`, getAuthHeaders());
      toast.success("Coupon deleted");
      fetchData();
    } catch (error) {
      toast.error("Failed to delete coupon");
    }
  };

  const resetForm = () => {
    setEditingCoupon(null);
    setForm({
      code: "",
      discount_type: "percentage",
      discount_value: "",
      min_purchase: "",
      max_uses: "",
      valid_until: "",
      applicable_plans: [],
      is_active: true,
    });
  };

  const copyCode = (code) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const activeCoupons = coupons.filter(c => c.is_active);
  const totalUsage = coupons.reduce((sum, c) => sum + (c.used_count || 0), 0);

  return (
    <div className="space-y-8" data-testid="coupons-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Coupons & Discounts</h1>
          <p className="text-muted-foreground mt-1">
            Create and manage discount codes for your subscribers
          </p>
        </div>
        <Button onClick={() => { resetForm(); setDialogOpen(true); }} data-testid="add-coupon-btn">
          <Plus className="w-4 h-4 mr-2" />
          Create Coupon
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-primary/10 rounded-lg">
              <Ticket className="w-6 h-6 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold">{coupons.length}</p>
              <p className="text-sm text-muted-foreground">Total Coupons</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-green-100 rounded-lg">
              <CheckCircle className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{activeCoupons.length}</p>
              <p className="text-sm text-muted-foreground">Active Coupons</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-blue-100 rounded-lg">
              <Percent className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{totalUsage}</p>
              <p className="text-sm text-muted-foreground">Total Uses</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Coupons List */}
      <Card>
        <CardHeader>
          <CardTitle>All Coupons</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">Loading...</div>
          ) : coupons.length === 0 ? (
            <div className="text-center py-12">
              <Ticket className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No coupons created yet</p>
              <Button onClick={() => setDialogOpen(true)} className="mt-4">
                <Plus className="w-4 h-4 mr-2" />
                Create First Coupon
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {coupons.map((coupon) => (
                <div
                  key={coupon.id}
                  className="flex items-center justify-between p-4 bg-muted/30 rounded-lg border"
                  data-testid={`coupon-${coupon.id}`}
                >
                  <div className="flex items-center gap-4">
                    <div
                      className="font-mono text-lg font-bold bg-primary/10 px-4 py-2 rounded-lg cursor-pointer hover:bg-primary/20 transition-colors flex items-center gap-2"
                      onClick={() => copyCode(coupon.code)}
                    >
                      {coupon.code}
                      {copiedCode === coupon.code ? (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      ) : (
                        <Copy className="w-4 h-4 text-muted-foreground" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        {coupon.discount_type === "percentage" ? (
                          <Badge variant="secondary" className="bg-purple-100 text-purple-700">
                            {coupon.discount_value}% OFF
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="bg-green-100 text-green-700">
                            ₹{coupon.discount_value} OFF
                          </Badge>
                        )}
                        <Badge variant={coupon.is_active ? "default" : "outline"}>
                          {coupon.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        Used {coupon.used_count || 0} times
                        {coupon.max_uses > 0 && ` / ${coupon.max_uses} max`}
                        {coupon.valid_until && ` • Expires: ${new Date(coupon.valid_until).toLocaleDateString()}`}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="ghost" size="icon" onClick={() => handleEdit(coupon)}>
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => handleDelete(coupon.id)}>
                      <Trash2 className="w-4 h-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editingCoupon ? "Edit Coupon" : "Create New Coupon"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="code">Coupon Code</Label>
              <Input
                id="code"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
                placeholder="SAVE20"
                required
                data-testid="coupon-code-input"
                className="font-mono uppercase"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Discount Type</Label>
                <Select
                  value={form.discount_type}
                  onValueChange={(val) => setForm({ ...form, discount_type: val })}
                >
                  <SelectTrigger data-testid="discount-type-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="percentage">
                      <div className="flex items-center gap-2">
                        <Percent className="w-4 h-4" />
                        Percentage
                      </div>
                    </SelectItem>
                    <SelectItem value="flat">
                      <div className="flex items-center gap-2">
                        <IndianRupee className="w-4 h-4" />
                        Flat Amount
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="discount_value">
                  {form.discount_type === "percentage" ? "Discount %" : "Amount ₹"}
                </Label>
                <Input
                  id="discount_value"
                  type="number"
                  value={form.discount_value}
                  onChange={(e) => setForm({ ...form, discount_value: e.target.value })}
                  placeholder={form.discount_type === "percentage" ? "20" : "50"}
                  required
                  data-testid="discount-value-input"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="min_purchase">Min Purchase ₹</Label>
                <Input
                  id="min_purchase"
                  type="number"
                  value={form.min_purchase}
                  onChange={(e) => setForm({ ...form, min_purchase: e.target.value })}
                  placeholder="0"
                  data-testid="min-purchase-input"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="max_uses">Max Uses (0=unlimited)</Label>
                <Input
                  id="max_uses"
                  type="number"
                  value={form.max_uses}
                  onChange={(e) => setForm({ ...form, max_uses: e.target.value })}
                  placeholder="0"
                  data-testid="max-uses-input"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="valid_until">Expiry Date (Optional)</Label>
              <Input
                id="valid_until"
                type="date"
                value={form.valid_until}
                onChange={(e) => setForm({ ...form, valid_until: e.target.value })}
                data-testid="expiry-date-input"
              />
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="is_active">Active</Label>
              <Switch
                id="is_active"
                checked={form.is_active}
                onCheckedChange={(checked) => setForm({ ...form, is_active: checked })}
                data-testid="coupon-active-switch"
              />
            </div>

            <Button type="submit" className="w-full" data-testid="save-coupon-btn">
              {editingCoupon ? "Update Coupon" : "Create Coupon"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
