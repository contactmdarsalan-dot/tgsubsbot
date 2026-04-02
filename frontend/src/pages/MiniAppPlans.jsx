import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Package, IndianRupee, Clock, Video, Smartphone, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Switch } from "../components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}`, "Content-Type": "application/json" });

export default function MiniAppPlans() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);
  const [form, setForm] = useState({ name: "", description: "", price: "", duration_days: "30", duration_minutes: "0", plan_type: "subscription", is_active: true });

  useEffect(() => { fetchPlans(); }, []);

  const fetchPlans = async () => {
    try {
      const res = await fetch(`${API}/miniapp-manage/plans`, { headers: headers() });
      if (res.ok) setPlans(await res.json());
    } catch (e) { toast.error("Failed to fetch plans"); }
    finally { setLoading(false); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form, price: parseFloat(form.price), duration_days: parseInt(form.duration_days), duration_minutes: parseInt(form.duration_minutes || "0") };
      const url = editingPlan ? `${API}/miniapp-manage/plans/${editingPlan.id}` : `${API}/miniapp-manage/plans`;
      const method = editingPlan ? "PUT" : "POST";
      const res = await fetch(url, { method, headers: headers(), body: JSON.stringify(payload) });
      if (res.ok) {
        toast.success(editingPlan ? "Plan updated" : "Plan created");
        setDialogOpen(false);
        resetForm();
        fetchPlans();
      } else { toast.error("Failed to save plan"); }
    } catch (e) { toast.error("Error saving plan"); }
  };

  const handleEdit = (plan) => {
    setEditingPlan(plan);
    setForm({ name: plan.name, description: plan.description || "", price: String(plan.price), duration_days: String(plan.duration_days || 30), duration_minutes: String(plan.duration_minutes || 0), plan_type: plan.plan_type || "subscription", is_active: plan.is_active !== false });
    setDialogOpen(true);
  };

  const handleDelete = async (planId) => {
    if (!window.confirm("Delete this plan?")) return;
    try {
      const res = await fetch(`${API}/miniapp-manage/plans/${planId}`, { method: "DELETE", headers: headers() });
      if (res.ok) { toast.success("Plan deleted"); fetchPlans(); }
    } catch (e) { toast.error("Delete failed"); }
  };

  const resetForm = () => { setEditingPlan(null); setForm({ name: "", description: "", price: "", duration_days: "30", duration_minutes: "0", plan_type: "subscription", is_active: true }); };

  const typeIcons = { subscription: <Package className="w-4 h-4" />, video_call: <Video className="w-4 h-4" />, one_time: <IndianRupee className="w-4 h-4" /> };

  return (
    <div className="space-y-6" data-testid="miniapp-plans">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2"><Smartphone className="w-6 h-6 text-emerald-400" /> Mini App Plans</h1>
          <p className="text-zinc-400 text-sm mt-1">Manage plans sold through your Mini App (separate from Bot plans)</p>
        </div>
        <Button onClick={() => { resetForm(); setDialogOpen(true); }} className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="create-miniapp-plan-btn">
          <Plus className="w-4 h-4 mr-2" /> Create Plan
        </Button>
      </div>

      {loading ? (
        <div className="text-center py-16"><Loader2 className="w-6 h-6 animate-spin text-emerald-400 mx-auto" /></div>
      ) : plans.length === 0 ? (
        <div className="text-center py-16 bg-zinc-900/30 border border-white/5 rounded-xl">
          <Package className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-400">No Mini App plans yet</p>
          <p className="text-zinc-600 text-sm mt-1">Create your first plan to start selling on the Mini App</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {plans.map(plan => (
            <div key={plan.id} className="bg-zinc-900/50 border border-white/5 rounded-xl p-5 hover:border-emerald-500/20 transition-colors" data-testid={`miniapp-plan-${plan.id}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  {typeIcons[plan.plan_type] || typeIcons.subscription}
                  <h3 className="text-lg font-semibold text-white">{plan.name}</h3>
                </div>
                <Badge variant={plan.is_active ? "default" : "secondary"} className={plan.is_active ? "bg-emerald-500/15 text-emerald-400 border-0" : "bg-zinc-700 text-zinc-400 border-0"}>
                  {plan.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
              {plan.description && <p className="text-zinc-400 text-sm mb-3">{plan.description}</p>}
              <div className="flex items-center gap-4 text-sm text-zinc-400 mb-4">
                <span className="flex items-center gap-1"><IndianRupee className="w-3.5 h-3.5" /> {plan.price}</span>
                <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {plan.duration_days}d</span>
                {plan.plan_type === "video_call" && plan.duration_minutes > 0 && <span className="flex items-center gap-1"><Video className="w-3.5 h-3.5" /> {plan.duration_minutes}min</span>}
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => handleEdit(plan)} className="flex-1 border-white/10 text-zinc-300 hover:text-white hover:bg-white/5" data-testid={`edit-plan-${plan.id}`}>
                  <Pencil className="w-3 h-3 mr-1" /> Edit
                </Button>
                <Button size="sm" variant="outline" onClick={() => handleDelete(plan.id)} className="border-rose-500/20 text-rose-400 hover:bg-rose-500/10" data-testid={`delete-plan-${plan.id}`}>
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-zinc-900 border-white/10 text-white max-w-md">
          <DialogHeader><DialogTitle>{editingPlan ? "Edit Plan" : "Create Mini App Plan"}</DialogTitle></DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div><Label className="text-zinc-400">Plan Name</Label><Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Premium Access" className="bg-zinc-800 border-white/10 text-white mt-1" required data-testid="plan-name-input" /></div>
            <div><Label className="text-zinc-400">Description</Label><Input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Brief description" className="bg-zinc-800 border-white/10 text-white mt-1" data-testid="plan-desc-input" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-zinc-400">Price (INR)</Label><Input type="number" value={form.price} onChange={e => setForm({ ...form, price: e.target.value })} placeholder="299" className="bg-zinc-800 border-white/10 text-white mt-1" required data-testid="plan-price-input" /></div>
              <div><Label className="text-zinc-400">Duration (days)</Label><Input type="number" value={form.duration_days} onChange={e => setForm({ ...form, duration_days: e.target.value })} className="bg-zinc-800 border-white/10 text-white mt-1" required data-testid="plan-duration-input" /></div>
            </div>
            <div>
              <Label className="text-zinc-400">Plan Type</Label>
              <Select value={form.plan_type} onValueChange={v => setForm({ ...form, plan_type: v })}>
                <SelectTrigger className="bg-zinc-800 border-white/10 text-white mt-1" data-testid="plan-type-select"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-zinc-800 border-white/10 text-white">
                  <SelectItem value="subscription">Subscription</SelectItem>
                  <SelectItem value="video_call">Video Call</SelectItem>
                  <SelectItem value="one_time">One Time</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.plan_type === "video_call" && (
              <div><Label className="text-zinc-400">Call Duration (minutes)</Label><Input type="number" value={form.duration_minutes} onChange={e => setForm({ ...form, duration_minutes: e.target.value })} placeholder="10" className="bg-zinc-800 border-white/10 text-white mt-1" data-testid="plan-call-duration-input" /></div>
            )}
            <div className="flex items-center justify-between">
              <Label className="text-zinc-400">Active</Label>
              <Switch checked={form.is_active} onCheckedChange={v => setForm({ ...form, is_active: v })} data-testid="plan-active-switch" />
            </div>
            <Button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="save-plan-btn">
              {editingPlan ? "Update Plan" : "Create Plan"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
