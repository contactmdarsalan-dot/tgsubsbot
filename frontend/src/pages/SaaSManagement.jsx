import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "../components/ui/table";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "../components/ui/dialog";
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from "../components/ui/tabs";
import { toast } from "sonner";
import {
  Package, Users, Shield, Plus, Trash2, Edit, UserPlus,
  IndianRupee, Eye, EyeOff, Crown, CheckCircle, XCircle,
  ArrowRightLeft, Loader2,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuth = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

// Feature options for bot plans
const FEATURE_OPTIONS = [
  "AI Payment Verification",
  "Auto QR Code Generation",
  "Live Stream Tickets",
  "Paid Posts with Blur",
  "Broadcast Messages",
  "Referral System",
  "Support Chat Bot",
  "Revenue Analytics",
  "Custom Branding",
  "Priority Support",
  "Razorpay Integration",
  "Multi-Admin Access",
  "Webhook Notifications",
  "Export Data (CSV)",
];

export default function SaaSManagement() {
  const [tab, setTab] = useState("plans");
  const [plans, setPlans] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);

  // Plan dialog
  const [planDialog, setPlanDialog] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);
  const [planForm, setPlanForm] = useState({
    name: "", price: 0, duration_days: 30, features: [],
    max_subscribers: 500, max_broadcasts: 10,
    ai_verify_enabled: true, live_stream_enabled: true,
    paid_posts_enabled: true, is_popular: false,
  });

  // Tenant dialog
  const [tenantDialog, setTenantDialog] = useState(false);
  const [editingTenant, setEditingTenant] = useState(null);
  const [tenantForm, setTenantForm] = useState({
    name: "", email: "", owner_telegram_id: "", bot_token: "",
    bot_username: "", upi_id: "", channel_id: "", razorpay_key_id: "",
  });

  // Admin assignment
  const [adminDialog, setAdminDialog] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState(null);
  const [tenantAdmins, setTenantAdmins] = useState([]);
  const [newAdmin, setNewAdmin] = useState({ telegram_user_id: "", name: "", email: "", role: "admin" });

  const fetchPlans = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/saas/bot-plans`, getAuth());
      setPlans(data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchTenants = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/saas/tenants`, getAuth());
      setTenants(data);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    Promise.all([fetchPlans(), fetchTenants()]).finally(() => setLoading(false));
  }, [fetchPlans, fetchTenants]);

  // ======= PLAN CRUD =======
  const openPlanDialog = (plan = null) => {
    if (plan) {
      setEditingPlan(plan);
      setPlanForm({ ...plan });
    } else {
      setEditingPlan(null);
      setPlanForm({
        name: "", price: 0, duration_days: 30, features: [],
        max_subscribers: 500, max_broadcasts: 10,
        ai_verify_enabled: true, live_stream_enabled: true,
        paid_posts_enabled: true, is_popular: false,
      });
    }
    setPlanDialog(true);
  };

  const savePlan = async () => {
    try {
      if (editingPlan) {
        await axios.put(`${API}/saas/bot-plans/${editingPlan.id}`, planForm, getAuth());
        toast.success("Plan updated");
      } else {
        await axios.post(`${API}/saas/bot-plans`, planForm, getAuth());
        toast.success("Plan created");
      }
      fetchPlans();
      setPlanDialog(false);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const deletePlan = async (id) => {
    if (!window.confirm("Delete this plan?")) return;
    try {
      await axios.delete(`${API}/saas/bot-plans/${id}`, getAuth());
      toast.success("Plan deleted");
      fetchPlans();
    } catch (e) { toast.error("Failed"); }
  };

  const toggleFeature = (feature) => {
    setPlanForm(prev => ({
      ...prev,
      features: prev.features.includes(feature)
        ? prev.features.filter(f => f !== feature)
        : [...prev.features, feature],
    }));
  };

  // ======= TENANT CRUD =======
  const openTenantDialog = (tenant = null) => {
    if (tenant) {
      setEditingTenant(tenant);
      setTenantForm({
        name: tenant.name || "", email: tenant.email || "",
        owner_telegram_id: tenant.owner_telegram_id || "",
        bot_token: tenant.bot_token || "", bot_username: tenant.bot_username || "",
        upi_id: tenant.upi_id || "", channel_id: tenant.channel_id || "",
        razorpay_key_id: tenant.razorpay_key_id || "",
      });
    } else {
      setEditingTenant(null);
      setTenantForm({ name: "", email: "", owner_telegram_id: "", bot_token: "", bot_username: "", upi_id: "", channel_id: "", razorpay_key_id: "" });
    }
    setTenantDialog(true);
  };

  const saveTenant = async () => {
    try {
      if (editingTenant) {
        await axios.put(`${API}/saas/tenants/${editingTenant.tenant_id}`, tenantForm, getAuth());
        toast.success("Tenant updated");
      } else {
        await axios.post(`${API}/saas/tenants`, tenantForm, getAuth());
        toast.success("Tenant created");
      }
      fetchTenants();
      setTenantDialog(false);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const deactivateTenant = async (tenantId) => {
    if (!window.confirm("Deactivate this tenant?")) return;
    try {
      await axios.delete(`${API}/saas/tenants/${tenantId}`, getAuth());
      toast.success("Tenant deactivated");
      fetchTenants();
    } catch (e) { toast.error("Failed"); }
  };

  // ======= ADMIN ASSIGNMENT =======
  const openAdminDialog = async (tenant) => {
    setSelectedTenant(tenant);
    setNewAdmin({ telegram_user_id: "", name: "", email: "", role: "admin" });
    try {
      const { data } = await axios.get(`${API}/saas/tenants/${tenant.tenant_id}/admins`, getAuth());
      setTenantAdmins(data);
    } catch (e) { setTenantAdmins(tenant.admins || []); }
    setAdminDialog(true);
  };

  const assignAdmin = async () => {
    if (!newAdmin.telegram_user_id.trim()) return;
    try {
      await axios.post(
        `${API}/saas/tenants/${selectedTenant.tenant_id}/admins`,
        newAdmin, getAuth()
      );
      toast.success("Admin assigned");
      const { data } = await axios.get(`${API}/saas/tenants/${selectedTenant.tenant_id}/admins`, getAuth());
      setTenantAdmins(data);
      setNewAdmin({ telegram_user_id: "", name: "", email: "", role: "admin" });
      fetchTenants();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const removeAdmin = async (adminId) => {
    if (!window.confirm("Remove this admin?")) return;
    try {
      await axios.delete(`${API}/saas/tenants/${selectedTenant.tenant_id}/admins/${adminId}`, getAuth());
      toast.success("Admin removed");
      const { data } = await axios.get(`${API}/saas/tenants/${selectedTenant.tenant_id}/admins`, getAuth());
      setTenantAdmins(data);
      fetchTenants();
    } catch (e) { toast.error("Failed"); }
  };

  // ======= MIGRATE DATA =======
  const [migrating, setMigrating] = useState(false);

  const migrateData = async (tenant) => {
    if (!window.confirm(`Migrate ALL unmapped data (default/empty tenant) to "${tenant.name}"?\n\nThis will move subscribers, payments, plans, posts etc. to this tenant.`)) return;
    setMigrating(true);
    try {
      const { data } = await axios.post(`${API}/saas/migrate-to-tenant`, {
        target_tenant_id: tenant.tenant_id,
        target_tenant_name: tenant.name,
      }, getAuth());
      toast.success(`${data.total_migrated} documents migrated to ${tenant.name}!`);
      fetchTenants();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Migration failed");
    } finally {
      setMigrating(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" /></div>;

  return (
    <div className="space-y-6" data-testid="saas-management">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" data-testid="saas-title">SaaS Management</h1>
          <p className="text-muted-foreground text-sm">Manage bot subscription plans and tenants</p>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList data-testid="saas-tabs">
          <TabsTrigger value="plans" data-testid="saas-tab-plans"><Package className="w-4 h-4 mr-1" /> Bot Plans</TabsTrigger>
          <TabsTrigger value="tenants" data-testid="saas-tab-tenants"><Users className="w-4 h-4 mr-1" /> Tenants</TabsTrigger>
        </TabsList>

        {/* ===== BOT PLANS TAB ===== */}
        <TabsContent value="plans" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Bot Subscription Plans</h2>
            <Button onClick={() => openPlanDialog()} data-testid="create-bot-plan-btn"><Plus className="w-4 h-4 mr-1" /> New Plan</Button>
          </div>

          {plans.length === 0 ? (
            <Card><CardContent className="p-12 text-center text-muted-foreground">No plans yet. Create your first bot subscription plan.</CardContent></Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {plans.map(plan => (
                <Card key={plan.id} className={`relative ${!plan.is_active ? "opacity-60" : ""}`} data-testid={`bot-plan-${plan.id}`}>
                  {plan.is_popular && <Badge className="absolute top-3 right-3 bg-amber-500">Popular</Badge>}
                  {!plan.is_active && <Badge variant="destructive" className="absolute top-3 right-3">Inactive</Badge>}
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2">
                      <Crown className="w-5 h-5 text-amber-500" />
                      {plan.name}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-baseline gap-1">
                      <span className="text-3xl font-bold">{plan.price > 0 ? `\u20B9${plan.price.toLocaleString()}` : "Free"}</span>
                      <span className="text-sm text-muted-foreground">/ {plan.duration_days} days</span>
                    </div>
                    <div className="text-xs text-muted-foreground space-y-1">
                      <p>Max Subscribers: {plan.max_subscribers}</p>
                      <p>Max Broadcasts: {plan.max_broadcasts}/day</p>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {plan.ai_verify_enabled && <Badge variant="outline" className="text-xs">AI Verify</Badge>}
                      {plan.live_stream_enabled && <Badge variant="outline" className="text-xs">Live</Badge>}
                      {plan.paid_posts_enabled && <Badge variant="outline" className="text-xs">Paid Posts</Badge>}
                    </div>
                    {plan.features?.length > 0 && (
                      <div className="border-t pt-2">
                        <p className="text-xs font-semibold mb-1">Features:</p>
                        <ul className="text-xs text-muted-foreground space-y-0.5">
                          {plan.features.map((f, i) => (
                            <li key={i} className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-green-500" />{f}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <div className="flex gap-2 pt-2">
                      <Button variant="outline" size="sm" onClick={() => openPlanDialog(plan)} data-testid={`edit-plan-${plan.id}`}><Edit className="w-3 h-3 mr-1" /> Edit</Button>
                      <Button variant="destructive" size="sm" onClick={() => deletePlan(plan.id)} data-testid={`delete-plan-${plan.id}`}><Trash2 className="w-3 h-3 mr-1" /> Delete</Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* ===== TENANTS TAB ===== */}
        <TabsContent value="tenants" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Tenants ({tenants.length})</h2>
            <Button onClick={() => openTenantDialog()} data-testid="create-tenant-btn"><Plus className="w-4 h-4 mr-1" /> New Tenant</Button>
          </div>

          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tenant</TableHead>
                  <TableHead>Bot</TableHead>
                  <TableHead>Users</TableHead>
                  <TableHead>Active Subs</TableHead>
                  <TableHead>Revenue</TableHead>
                  <TableHead>Admins</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tenants.map(t => (
                  <TableRow key={t.tenant_id} data-testid={`tenant-row-${t.tenant_id}`}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{t.name || t.tenant_id}</p>
                        <p className="text-xs text-muted-foreground">{t.email}</p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-xs">{t.bot_username ? `@${t.bot_username}` : "-"}</span>
                    </TableCell>
                    <TableCell>{t.stats?.total_users || 0}</TableCell>
                    <TableCell>{t.stats?.active_subs || 0}</TableCell>
                    <TableCell className="font-semibold">{`\u20B9${(t.stats?.revenue || 0).toLocaleString()}`}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm" onClick={() => openAdminDialog(t)} data-testid={`manage-admins-${t.tenant_id}`}>
                        <Shield className="w-3 h-3 mr-1" /> {t.admins?.length || 0}
                      </Button>
                    </TableCell>
                    <TableCell>
                      <Badge variant={t.status === "active" ? "default" : "destructive"}>
                        {t.status || "active"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon" onClick={() => openTenantDialog(t)} data-testid={`edit-tenant-${t.tenant_id}`} title="Edit"><Edit className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => migrateData(t)} disabled={migrating} data-testid={`migrate-${t.tenant_id}`} title="Migrate data to this tenant">
                          {migrating ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRightLeft className="w-4 h-4 text-amber-500" />}
                        </Button>
                        {t.status !== "inactive" && (
                          <Button variant="ghost" size="icon" onClick={() => deactivateTenant(t.tenant_id)} data-testid={`deactivate-${t.tenant_id}`} title="Deactivate"><XCircle className="w-4 h-4 text-destructive" /></Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ===== PLAN DIALOG ===== */}
      <Dialog open={planDialog} onOpenChange={setPlanDialog}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="plan-dialog">
          <DialogHeader>
            <DialogTitle>{editingPlan ? "Edit Plan" : "New Bot Plan"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div><Label>Plan Name</Label><Input value={planForm.name} onChange={e => setPlanForm(p => ({ ...p, name: e.target.value }))} placeholder="e.g. Pro Plan" data-testid="plan-name-input" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Price (INR)</Label><Input type="number" value={planForm.price} onChange={e => setPlanForm(p => ({ ...p, price: parseInt(e.target.value) || 0 }))} data-testid="plan-price-input" /></div>
              <div><Label>Duration (days)</Label><Input type="number" value={planForm.duration_days} onChange={e => setPlanForm(p => ({ ...p, duration_days: parseInt(e.target.value) || 30 }))} data-testid="plan-duration-input" /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Max Subscribers</Label><Input type="number" value={planForm.max_subscribers} onChange={e => setPlanForm(p => ({ ...p, max_subscribers: parseInt(e.target.value) || 0 }))} /></div>
              <div><Label>Max Broadcasts/day</Label><Input type="number" value={planForm.max_broadcasts} onChange={e => setPlanForm(p => ({ ...p, max_broadcasts: parseInt(e.target.value) || 0 }))} /></div>
            </div>
            <div className="space-y-2">
              <Label>Access Controls</Label>
              <div className="flex items-center justify-between"><span className="text-sm">AI Payment Verification</span><Switch checked={planForm.ai_verify_enabled} onCheckedChange={v => setPlanForm(p => ({ ...p, ai_verify_enabled: v }))} /></div>
              <div className="flex items-center justify-between"><span className="text-sm">Live Streaming</span><Switch checked={planForm.live_stream_enabled} onCheckedChange={v => setPlanForm(p => ({ ...p, live_stream_enabled: v }))} /></div>
              <div className="flex items-center justify-between"><span className="text-sm">Paid Posts</span><Switch checked={planForm.paid_posts_enabled} onCheckedChange={v => setPlanForm(p => ({ ...p, paid_posts_enabled: v }))} /></div>
              <div className="flex items-center justify-between"><span className="text-sm">Mark as Popular</span><Switch checked={planForm.is_popular} onCheckedChange={v => setPlanForm(p => ({ ...p, is_popular: v }))} /></div>
            </div>
            <div className="space-y-2">
              <Label>Feature List</Label>
              <div className="flex flex-wrap gap-2" data-testid="feature-list">
                {FEATURE_OPTIONS.map(f => (
                  <Badge key={f} variant={planForm.features.includes(f) ? "default" : "outline"}
                    className="cursor-pointer select-none" onClick={() => toggleFeature(f)} data-testid={`feature-${f.replace(/\s+/g, "-").toLowerCase()}`}>
                    {planForm.features.includes(f) && <CheckCircle className="w-3 h-3 mr-1" />}
                    {f}
                  </Badge>
                ))}
              </div>
            </div>
            <Button className="w-full" onClick={savePlan} disabled={!planForm.name.trim()} data-testid="save-plan-btn">
              {editingPlan ? "Update Plan" : "Create Plan"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== TENANT DIALOG ===== */}
      <Dialog open={tenantDialog} onOpenChange={setTenantDialog}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="tenant-dialog">
          <DialogHeader>
            <DialogTitle>{editingTenant ? "Edit Tenant" : "New Tenant"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div><Label>Creator Name</Label><Input value={tenantForm.name} onChange={e => setTenantForm(p => ({ ...p, name: e.target.value }))} placeholder="Creator name" data-testid="tenant-name-input" /></div>
            <div><Label>Email</Label><Input value={tenantForm.email} onChange={e => setTenantForm(p => ({ ...p, email: e.target.value }))} placeholder="creator@email.com" data-testid="tenant-email-input" /></div>
            <div><Label>Owner Telegram ID</Label><Input value={tenantForm.owner_telegram_id} onChange={e => setTenantForm(p => ({ ...p, owner_telegram_id: e.target.value }))} placeholder="123456789" data-testid="tenant-tg-input" /></div>
            <div><Label>Bot Token</Label><Input value={tenantForm.bot_token} onChange={e => setTenantForm(p => ({ ...p, bot_token: e.target.value }))} placeholder="Bot token from @BotFather" data-testid="tenant-token-input" /></div>
            <div><Label>Bot Username</Label><Input value={tenantForm.bot_username} onChange={e => setTenantForm(p => ({ ...p, bot_username: e.target.value }))} placeholder="@botusername" data-testid="tenant-botname-input" /></div>
            <div><Label>UPI ID</Label><Input value={tenantForm.upi_id} onChange={e => setTenantForm(p => ({ ...p, upi_id: e.target.value }))} placeholder="name@paytm" data-testid="tenant-upi-input" /></div>
            <div><Label>Channel ID</Label><Input value={tenantForm.channel_id} onChange={e => setTenantForm(p => ({ ...p, channel_id: e.target.value }))} placeholder="-1001234567890" /></div>
            <div><Label>Razorpay Key ID (optional)</Label><Input value={tenantForm.razorpay_key_id} onChange={e => setTenantForm(p => ({ ...p, razorpay_key_id: e.target.value }))} placeholder="rzp_live_..." /></div>
            <Button className="w-full" onClick={saveTenant} disabled={!tenantForm.name.trim()} data-testid="save-tenant-btn">
              {editingTenant ? "Update Tenant" : "Create Tenant"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== ADMIN ASSIGNMENT DIALOG ===== */}
      <Dialog open={adminDialog} onOpenChange={setAdminDialog}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="admin-dialog">
          <DialogHeader>
            <DialogTitle>Manage Admins - {selectedTenant?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {/* Current admins */}
            <div>
              <Label className="mb-2 block">Current Admins ({tenantAdmins.length})</Label>
              {tenantAdmins.length === 0 ? (
                <p className="text-sm text-muted-foreground">No admins assigned</p>
              ) : (
                <div className="space-y-2">
                  {tenantAdmins.map(a => (
                    <div key={a.id} className="flex items-center justify-between border rounded-lg p-3" data-testid={`admin-entry-${a.id}`}>
                      <div>
                        <p className="text-sm font-medium">{a.name || "Admin"}</p>
                        <p className="text-xs text-muted-foreground">TG: {a.telegram_user_id} &middot; {a.role}</p>
                        {a.email && <p className="text-xs text-muted-foreground">{a.email}</p>}
                      </div>
                      <Button variant="ghost" size="icon" onClick={() => removeAdmin(a.id)} data-testid={`remove-admin-${a.id}`}>
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Add new admin */}
            <div className="border-t pt-4">
              <Label className="mb-2 block">Assign New Admin</Label>
              <div className="space-y-2">
                <Input placeholder="Telegram User ID *" value={newAdmin.telegram_user_id} onChange={e => setNewAdmin(p => ({ ...p, telegram_user_id: e.target.value }))} data-testid="new-admin-tg-input" />
                <Input placeholder="Name" value={newAdmin.name} onChange={e => setNewAdmin(p => ({ ...p, name: e.target.value }))} data-testid="new-admin-name-input" />
                <Input placeholder="Email (optional)" value={newAdmin.email} onChange={e => setNewAdmin(p => ({ ...p, email: e.target.value }))} />
                <Button onClick={assignAdmin} disabled={!newAdmin.telegram_user_id.trim()} className="w-full" data-testid="assign-admin-btn">
                  <UserPlus className="w-4 h-4 mr-1" /> Assign Admin
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
