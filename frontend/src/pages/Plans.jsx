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
} from "../components/ui/dialog";
import { Switch } from "../components/ui/switch";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Package, IndianRupee, Clock, Megaphone } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function Plans() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);
  const [promoteDialogOpen, setPromoteDialogOpen] = useState(false);
  const [promotePlan, setPromotePlan] = useState(null);
  const [groups, setGroups] = useState([]);
  const [channels, setChannels] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState("");
  const [form, setForm] = useState({
    name: "",
    price: "",
    duration_days: "",
    features: "",
    channel_id: "",
    group_id: "",
    auto_assign_group: false,
    is_active: true,
    discount_percentage: "0",
  });

  useEffect(() => {
    fetchPlans();
    fetchGroups();
    fetchChannels();
  }, []);

  const fetchGroups = async () => {
    try {
      const response = await axios.get(`${API}/chat-groups`, getAuthHeaders());
      setGroups(response.data);
    } catch (error) {
      console.error("Failed to fetch groups");
    }
  };

  const fetchChannels = async () => {
    try {
      const response = await axios.get(`${API}/channels`, getAuthHeaders());
      setChannels(response.data || []);
    } catch (error) {
      console.error("Failed to fetch channels");
    }
  };

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
        channel_id: form.channel_id,
        group_id: form.group_id,
        auto_assign_group: form.auto_assign_group,
        is_active: form.is_active,
        discount_percentage: parseInt(form.discount_percentage) || 0,
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
      features: Array.isArray(plan.features) ? plan.features.join("\n") : "",
      channel_id: plan.channel_id || "",
      group_id: plan.group_id || "",
      auto_assign_group: plan.auto_assign_group || false,
      is_active: plan.is_active,
      discount_percentage: (plan.discount_percentage || 0).toString(),
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
      toast.error(error.response?.data?.detail || "Failed to delete plan");
    }
  };

  const handleCreateNew = () => {
    resetForm();
    setDialogOpen(true);
  };

  const resetForm = () => {
    setEditingPlan(null);
    setForm({
      name: "",
      price: "",
      duration_days: "",
      features: "",
      channel_id: "",
      group_id: "",
      auto_assign_group: false,
      is_active: true,
      discount_percentage: "0",
    });
  };

  const handleDialogClose = (open) => {
    setDialogOpen(open);
    if (!open) {
      resetForm();
    }
  };

  const handlePromote = async () => {
    if (!promotePlan || !selectedGroup) {
      toast.error("Group select karo!");
      return;
    }
    try {
      const response = await axios.post(`${API}/promote-plan`, {
        plan_id: promotePlan.id,
        group_id: selectedGroup
      }, getAuthHeaders());
      if (response.data.success) {
        toast.success("Plan promoted to group!");
      } else {
        toast.error(response.data.message || "Failed to promote");
      }
      setPromoteDialogOpen(false);
      setPromotePlan(null);
      setSelectedGroup("");
    } catch (error) {
      toast.error("Failed to promote plan");
    }
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
          <h1 className="font-heading text-4xl font-bold tracking-tight text-white">
            Subscription Plans
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage your subscription tiers and pricing
          </p>
        </div>
        <Button className="btn-hover" data-testid="create-plan-btn" onClick={handleCreateNew}>
          <Plus className="w-4 h-4 mr-2" />
          Create Plan
        </Button>
      </div>

      {/* Dialog - Moved outside of header */}
      <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
        <DialogContent className="sm:max-w-[550px] max-h-[85vh] overflow-y-auto">
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
                <Label htmlFor="discount">Discount %</Label>
                <Input
                  id="discount"
                  type="number"
                  min="0"
                  max="100"
                  value={form.discount_percentage}
                  onChange={(e) => setForm({ ...form, discount_percentage: e.target.value })}
                  placeholder="0"
                  data-testid="plan-discount-input"
                  className="bg-muted/50 border-transparent focus:border-primary"
                />
                <p className="text-xs text-muted-foreground">
                  {form.discount_percentage > 0 && form.price > 0 
                    ? `Final price: ₹${Math.round(form.price * (100 - form.discount_percentage) / 100)}`
                    : "0 = No discount"
                  }
                </p>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
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
                rows={3}
                data-testid="plan-features-input"
                className="w-full px-3 py-2 bg-muted/50 border-transparent focus:border-primary rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="channel_id" className="text-primary font-semibold">Channel / Group (for access after payment)</Label>
              {channels.length > 0 || groups.length > 0 ? (
                <Select
                  value={form.channel_id || "__none__"}
                  onValueChange={(val) => setForm({ ...form, channel_id: val === "__none__" ? "" : val })}
                >
                  <SelectTrigger data-testid="plan-channel-select" className="bg-muted/50 border-primary/30">
                    <SelectValue placeholder="Select channel for this plan..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">-- No Channel (use default) --</SelectItem>
                    {channels.filter(ch => (ch.telegram_channel_id || ch.channel_id)).map((ch) => (
                      <SelectItem key={ch.id || ch.channel_id} value={ch.telegram_channel_id || ch.channel_id || ch.id}>
                        {ch.channel_name || ch.name || "Channel"} ({ch.telegram_channel_id || ch.channel_id})
                      </SelectItem>
                    ))}
                    {groups.filter(g => g.group_id && g.group_id !== "0").map((g) => (
                      <SelectItem key={g.id || g.group_id} value={g.group_id}>
                        {g.group_name || g.name || "Group"} ({g.group_id})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Input
                  id="channel_id"
                  value={form.channel_id}
                  onChange={(e) => setForm({ ...form, channel_id: e.target.value })}
                  placeholder="-1001234567890 (Telegram channel/group ID)"
                  data-testid="plan-channel-input"
                  className="bg-muted/50 border-primary/30 focus:border-primary font-mono text-sm"
                />
              )}
              <div className="space-y-1 mt-1">
                <Label className="text-xs text-muted-foreground">Or enter Channel ID manually:</Label>
                <Input
                  value={form.channel_id}
                  onChange={(e) => setForm({ ...form, channel_id: e.target.value })}
                  placeholder="-1001234567890"
                  data-testid="plan-channel-manual-input"
                  className="bg-muted/50 border-transparent focus:border-primary font-mono text-sm"
                />
              </div>
              {!form.channel_id && (
                <div className="p-2 bg-amber-500/10 border border-amber-500/30 rounded-md">
                  <p className="text-xs text-amber-400 font-medium">
                    Warning: No channel set! Set a channel ID for this plan.
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="group_id">Group ID (Manual)</Label>
              <Input
                id="group_id"
                value={form.group_id}
                onChange={(e) => setForm({ ...form, group_id: e.target.value })}
                placeholder="-1001234567890"
                disabled={form.auto_assign_group}
                data-testid="plan-group-input"
                className="bg-muted/50 border-transparent focus:border-primary font-mono text-sm disabled:opacity-50"
              />
              <p className="text-xs text-muted-foreground">
                Specific group for this plan. Disabled if Auto Groups is enabled.
              </p>
            </div>

            <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg border border-blue-200">
              <div className="space-y-0.5">
                <Label htmlFor="auto_group" className="text-blue-800 font-medium">Auto Groups</Label>
                <p className="text-xs text-blue-600">
                  Automatically assign available group from Groups pool to customer on purchase
                </p>
              </div>
              <Switch
                id="auto_group"
                checked={form.auto_assign_group}
                onCheckedChange={(checked) => setForm({ ...form, auto_assign_group: checked, group_id: checked ? "" : form.group_id })}
                data-testid="plan-auto-group-switch"
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
                  <IndianRupee className="w-6 h-6 text-white" />
                  <span className="font-heading text-4xl font-bold tracking-tight text-white">
                    {plan.price.toLocaleString("en-IN")}
                  </span>
                  {plan.discount_percentage > 0 && (
                    <Badge className="ml-2 bg-red-100 text-red-700">
                      {plan.discount_percentage}% OFF
                    </Badge>
                  )}
                </div>
                
                {plan.discount_percentage > 0 && (
                  <div className="text-sm text-green-600 font-medium">
                    Discounted: ₹{Math.round(plan.price * (100 - plan.discount_percentage) / 100).toLocaleString("en-IN")}
                  </div>
                )}

                <div className="flex items-center gap-2 text-muted-foreground">
                  <Clock className="w-4 h-4" />
                  <span className="text-sm">{plan.duration_days} days</span>
                </div>

                {!plan.channel_id && (
                  <div className="flex items-center gap-1.5 px-2 py-1 bg-amber-500/10 border border-amber-500/30 rounded-md">
                    <span className="text-xs text-amber-400 font-medium">No channel set - using default</span>
                  </div>
                )}

                {plan.channel_id && (
                  <div className="flex items-center gap-1.5 px-2 py-1 bg-emerald-500/10 border border-emerald-500/30 rounded-md">
                    <span className="text-xs text-emerald-400 font-mono">{plan.channel_id}</span>
                  </div>
                )}

                {plan.features && plan.features.length > 0 && (
                  <ul className="space-y-2 pt-2 border-t border-border">
                    {plan.features.map((feature, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                )}

                <div className="flex gap-2 pt-4 relative z-10">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      setPromotePlan(plan);
                      setPromoteDialogOpen(true);
                    }}
                    data-testid={`promote-plan-${plan.id}`}
                    className="flex-1 border-yellow-600 text-yellow-500 hover:bg-yellow-900/30"
                  >
                    <Megaphone className="w-4 h-4 mr-2" />
                    Promote
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleEdit(plan);
                    }}
                    data-testid={`edit-plan-${plan.id}`}
                    className="flex-1"
                  >
                    <Pencil className="w-4 h-4 mr-2" />
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleDelete(plan.id);
                    }}
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
            <Button onClick={handleCreateNew} data-testid="empty-create-plan-btn">
              <Plus className="w-4 h-4 mr-2" />
              Create Plan
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Promote Plan Dialog */}
      <Dialog open={promoteDialogOpen} onOpenChange={(open) => {
        setPromoteDialogOpen(open);
        if (!open) { setPromotePlan(null); setSelectedGroup(""); }
      }}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="font-heading text-xl font-bold flex items-center gap-2">
              <Megaphone className="w-5 h-5 text-yellow-500" />
              Promote Plan to Group
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            {promotePlan && (
              <div className="bg-muted/50 rounded-lg p-3">
                <p className="font-medium">{promotePlan.name}</p>
                <p className="text-sm text-muted-foreground">₹{promotePlan.price} - {promotePlan.duration_days} days</p>
              </div>
            )}
            <div className="space-y-2">
              <Label>Select Group</Label>
              <Select value={selectedGroup} onValueChange={setSelectedGroup}>
                <SelectTrigger data-testid="promote-group-select" className="bg-muted/50 border-transparent">
                  <SelectValue placeholder="Select a group to promote in" />
                </SelectTrigger>
                <SelectContent>
                  {groups.map((group) => (
                    <SelectItem key={group.group_id} value={group.group_id}>
                      {group.group_name || group.group_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={handlePromote} className="w-full btn-hover" data-testid="confirm-promote-btn">
              <Megaphone className="w-4 h-4 mr-2" />
              Send Promotion
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
