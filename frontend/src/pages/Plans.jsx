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
import { Switch } from "../components/ui/switch";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Package, IndianRupee, Clock } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function Plans() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);
  const [form, setForm] = useState({
    name: "",
    price: "",
    duration_days: "",
    features: "",
    is_active: true,
  });

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      const response = await axios.get(`${API}/plans`, getAuthHeaders());
      setPlans(response.data);
    } catch (error) {
      toast.error("Failed to fetch plans");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        name: form.name,
        price: parseFloat(form.price),
        duration_days: parseInt(form.duration_days),
        features: form.features.split("\n").filter((f) => f.trim()),
        is_active: form.is_active,
      };

      if (editingPlan) {
        await axios.put(`${API}/plans/${editingPlan.id}`, payload, getAuthHeaders());
        toast.success("Plan updated successfully");
      } else {
        await axios.post(`${API}/plans`, payload, getAuthHeaders());
        toast.success("Plan created successfully");
      }

      setDialogOpen(false);
      resetForm();
      fetchPlans();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to save plan");
    }
  };

  const handleEdit = (plan) => {
    setEditingPlan(plan);
    setForm({
      name: plan.name,
      price: plan.price.toString(),
      duration_days: plan.duration_days.toString(),
      features: plan.features.join("\n"),
      is_active: plan.is_active,
    });
    setDialogOpen(true);
  };

  const handleDelete = async (planId) => {
    if (!window.confirm("Are you sure you want to delete this plan?")) return;
    try {
      await axios.delete(`${API}/plans/${planId}`, getAuthHeaders());
      toast.success("Plan deleted");
      fetchPlans();
    } catch (error) {
      toast.error("Failed to delete plan");
    }
  };

  const resetForm = () => {
    setEditingPlan(null);
    setForm({
      name: "",
      price: "",
      duration_days: "",
      features: "",
      is_active: true,
    });
  };

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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-4xl font-bold tracking-tight">
            Subscription Plans
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage your subscription tiers and pricing
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) resetForm();
        }}>
          <DialogTrigger asChild>
            <Button className="btn-hover" data-testid="create-plan-btn">
              <Plus className="w-4 h-4 mr-2" />
              Create Plan
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle className="font-heading text-xl font-bold">
                {editingPlan ? "Edit Plan" : "Create New Plan"}
              </DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label htmlFor="name">Plan Name</Label>
                <Input
                  id="name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g., Premium Monthly"
                  required
                  data-testid="plan-name-input"
                  className="bg-muted/50 border-transparent focus:border-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="price">Price (₹)</Label>
                  <Input
                    id="price"
                    type="number"
                    value={form.price}
                    onChange={(e) => setForm({ ...form, price: e.target.value })}
                    placeholder="299"
                    required
                    data-testid="plan-price-input"
                    className="bg-muted/50 border-transparent focus:border-primary"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="duration">Duration (Days)</Label>
                  <Input
                    id="duration"
                    type="number"
                    value={form.duration_days}
                    onChange={(e) => setForm({ ...form, duration_days: e.target.value })}
                    placeholder="30"
                    required
                    data-testid="plan-duration-input"
                    className="bg-muted/50 border-transparent focus:border-primary"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="features">Features (one per line)</Label>
                <textarea
                  id="features"
                  value={form.features}
                  onChange={(e) => setForm({ ...form, features: e.target.value })}
                  placeholder="Access to premium channel&#10;Daily signals&#10;24/7 support"
                  rows={4}
                  data-testid="plan-features-input"
                  className="w-full px-3 py-2 bg-muted/50 border-transparent focus:border-primary rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="flex items-center justify-between">
                <Label htmlFor="active">Active</Label>
                <Switch
                  id="active"
                  checked={form.is_active}
                  onCheckedChange={(checked) => setForm({ ...form, is_active: checked })}
                  data-testid="plan-active-switch"
                />
              </div>

              <Button type="submit" className="w-full btn-hover" data-testid="plan-submit-btn">
                {editingPlan ? "Update Plan" : "Create Plan"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Plans Grid */}
      {plans.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {plans.map((plan, index) => (
            <Card
              key={plan.id}
              className={`card-hover border relative overflow-hidden animate-fade-in-up stagger-${index + 1} ${
                plan.is_active ? "tracing-beam" : ""
              }`}
              data-testid={`plan-card-${plan.id}`}
            >
              <CardHeader className="pb-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <Package className="w-5 h-5 text-primary" />
                    <CardTitle className="font-heading text-xl font-bold">
                      {plan.name}
                    </CardTitle>
                  </div>
                  <Badge className={plan.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"}>
                    {plan.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-baseline gap-1">
                  <IndianRupee className="w-6 h-6 text-foreground" />
                  <span className="font-heading text-4xl font-bold tracking-tight">
                    {plan.price.toLocaleString("en-IN")}
                  </span>
                </div>

                <div className="flex items-center gap-2 text-muted-foreground">
                  <Clock className="w-4 h-4" />
                  <span className="text-sm">{plan.duration_days} days</span>
                </div>

                {plan.features.length > 0 && (
                  <ul className="space-y-2 pt-2 border-t border-border">
                    {plan.features.map((feature, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                )}

                <div className="flex gap-2 pt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleEdit(plan)}
                    data-testid={`edit-plan-${plan.id}`}
                    className="flex-1"
                  >
                    <Pencil className="w-4 h-4 mr-2" />
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDelete(plan.id)}
                    data-testid={`delete-plan-${plan.id}`}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="border">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Package className="w-12 h-12 text-muted-foreground mb-4" />
            <h3 className="font-heading text-xl font-bold mb-2">No Plans Yet</h3>
            <p className="text-muted-foreground text-center mb-4">
              Create your first subscription plan to get started
            </p>
            <Button onClick={() => setDialogOpen(true)} data-testid="empty-create-plan-btn">
              <Plus className="w-4 h-4 mr-2" />
              Create Plan
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
