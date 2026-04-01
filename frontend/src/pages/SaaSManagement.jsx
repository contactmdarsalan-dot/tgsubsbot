import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Switch } from "../components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Users, Package, Shield, Crown, Plus, Edit, Trash2, CheckCircle, XCircle, UserPlus, ArrowRightLeft, Loader2, CreditCard, Check, X } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });
const FEATURE_OPTIONS = ["Subscription Management", "Payment Verification", "Broadcasts", "Live Streaming", "Paid Posts", "Referral System", "Analytics", "Export Data"];

export default function SaaSManagement() {
  const [tab, setTab] = useState("tenants");
  const [loading, setLoading] = useState(true);

  // Data
  const [tenants, setTenants] = useState([]);
  const [plans, setPlans] = useState([]);
  const [tenantAdmins, setTenantAdmins] = useState([]);
  const [subscriptions, setSubscriptions] = useState([]);
  const [dashPlans, setDashPlans] = useState([]);

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
  const [tenantForm, setTenantForm] = useState({ name: "", email: "", owner_telegram_id: "", bot_token: "", bot_username: "", upi_id: "", channel_id: "", razorpay_key_id: "" });

  // Admin dialog
  const [adminDialog, setAdminDialog] = useState(false);
  const [editingAdmin, setEditingAdmin] = useState(null);
  const [adminForm, setAdminForm] = useState({ email: "", password: "", name: "", tenant_id: "" });

  // Assign subscription dialog
  const [assignSubDialog, setAssignSubDialog] = useState(false);
  const [assignForm, setAssignForm] = useState({ user_id: "", plan_id: "", duration_days: 30 });

  // Bot admin dialog
  const [botAdminDialog, setBotAdminDialog] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState(null);
  const [botAdmins, setBotAdmins] = useState([]);
  const [newBotAdmin, setNewBotAdmin] = useState({ telegram_user_id: "", name: "", email: "", role: "admin", permissions: ["manage_bot", "verify_payments", "broadcast", "live_streams", "paid_posts", "add_subscribers"] });

  const [migrating, setMigrating] = useState(false);

  // ===== FETCHERS =====
  const fetchTenants = useCallback(async () => { try { const { data } = await axios.get(`${API}/saas/tenants`, getAuth()); setTenants(data); } catch (e) { console.error(e); } }, []);
  const fetchPlans = useCallback(async () => { try { const { data } = await axios.get(`${API}/saas/bot-plans`, getAuth()); setPlans(data); } catch (e) { console.error(e); } }, []);
  const fetchTenantAdmins = useCallback(async () => { try { const { data } = await axios.get(`${API}/saas/tenant-admins`, getAuth()); setTenantAdmins(data); } catch (e) { console.error(e); } }, []);
  const fetchSubscriptions = useCallback(async () => { try { const { data } = await axios.get(`${API}/saas/subscriptions`, getAuth()); setSubscriptions(data); } catch (e) { console.error(e); } }, []);
  const fetchDashPlans = useCallback(async () => { try { const { data } = await axios.get(`${API}/admin/dashboard-plans`, getAuth()); setDashPlans(data); } catch (e) { console.error(e); } }, []);

  useEffect(() => {
    Promise.all([fetchTenants(), fetchPlans(), fetchTenantAdmins(), fetchSubscriptions(), fetchDashPlans()]).finally(() => setLoading(false));
  }, [fetchTenants, fetchPlans, fetchTenantAdmins, fetchSubscriptions, fetchDashPlans]);

  // ===== PLAN CRUD =====
  const openPlanDialog = (plan = null) => {
    if (plan) { setEditingPlan(plan); setPlanForm({ ...plan }); }
    else { setEditingPlan(null); setPlanForm({ name: "", price: 0, duration_days: 30, features: [], max_subscribers: 500, max_broadcasts: 10, ai_verify_enabled: true, live_stream_enabled: true, paid_posts_enabled: true, is_popular: false }); }
    setPlanDialog(true);
  };
  const savePlan = async () => { try { if (editingPlan) { await axios.put(`${API}/saas/bot-plans/${editingPlan.id}`, planForm, getAuth()); toast.success("Plan updated"); } else { await axios.post(`${API}/saas/bot-plans`, planForm, getAuth()); toast.success("Plan created"); } fetchPlans(); setPlanDialog(false); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } };
  const deletePlan = async (id) => { if (!window.confirm("Delete this plan?")) return; try { await axios.delete(`${API}/saas/bot-plans/${id}`, getAuth()); toast.success("Plan deleted"); fetchPlans(); } catch (e) { toast.error("Failed"); } };
  const toggleFeature = (f) => setPlanForm(p => ({ ...p, features: p.features.includes(f) ? p.features.filter(x => x !== f) : [...p.features, f] }));

  // ===== TENANT CRUD =====
  const openTenantDialog = (t = null) => {
    if (t) { setEditingTenant(t); setTenantForm({ name: t.name || "", email: t.email || "", owner_telegram_id: t.owner_telegram_id || "", bot_token: t.bot_token || "", bot_username: t.bot_username || "", upi_id: t.upi_id || "", channel_id: t.channel_id || "", razorpay_key_id: t.razorpay_key_id || "" }); }
    else { setEditingTenant(null); setTenantForm({ name: "", email: "", owner_telegram_id: "", bot_token: "", bot_username: "", upi_id: "", channel_id: "", razorpay_key_id: "" }); }
    setTenantDialog(true);
  };
  const saveTenant = async () => { try { if (editingTenant) { await axios.put(`${API}/saas/tenants/${editingTenant.tenant_id}`, tenantForm, getAuth()); toast.success("Tenant updated"); } else { await axios.post(`${API}/saas/tenants`, tenantForm, getAuth()); toast.success("Tenant created"); } fetchTenants(); setTenantDialog(false); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } };
  const deactivateTenant = async (id) => { if (!window.confirm("Deactivate?")) return; try { await axios.delete(`${API}/saas/tenants/${id}`, getAuth()); toast.success("Deactivated"); fetchTenants(); } catch (e) { toast.error("Failed"); } };
  const migrateData = async (t) => { if (!window.confirm(`Migrate ALL unmapped data to "${t.name}"?`)) return; setMigrating(true); try { const { data } = await axios.post(`${API}/saas/migrate-to-tenant`, { target_tenant_id: t.tenant_id, target_tenant_name: t.name }, getAuth()); toast.success(`${data.total_migrated} docs migrated`); fetchTenants(); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } finally { setMigrating(false); } };

  // ===== TENANT ADMIN CRUD =====
  const openAdminDialog = (admin = null) => {
    if (admin) { setEditingAdmin(admin); setAdminForm({ email: admin.email || "", password: "", name: admin.name || "", tenant_id: admin.tenant_id || "" }); }
    else { setEditingAdmin(null); setAdminForm({ email: "", password: "", name: "", tenant_id: "" }); }
    setAdminDialog(true);
  };
  const saveAdmin = async () => {
    try {
      if (editingAdmin) {
        const upd = { name: adminForm.name, tenant_id: adminForm.tenant_id };
        if (adminForm.email !== editingAdmin.email) upd.email = adminForm.email;
        await axios.put(`${API}/saas/tenant-admins/${editingAdmin.id}`, upd, getAuth());
        toast.success("Admin updated");
      } else {
        await axios.post(`${API}/saas/tenant-admins`, adminForm, getAuth());
        toast.success("Admin created");
      }
      fetchTenantAdmins(); setAdminDialog(false);
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const deleteAdmin = async (id) => { if (!window.confirm("Delete this admin?")) return; try { await axios.delete(`${API}/saas/tenant-admins/${id}`, getAuth()); toast.success("Admin deleted"); fetchTenantAdmins(); } catch (e) { toast.error("Failed"); } };

  // ===== SUBSCRIPTION MANAGEMENT =====
  const openAssignSubDialog = (admin = null) => {
    setAssignForm({ user_id: admin?.id || "", plan_id: "", duration_days: 30 });
    setAssignSubDialog(true);
  };
  const assignSub = async () => {
    try {
      await axios.post(`${API}/saas/assign-subscription`, assignForm, getAuth());
      toast.success("Subscription assigned!");
      fetchTenantAdmins(); fetchSubscriptions(); setAssignSubDialog(false);
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const approveSub = async (id) => { try { await axios.put(`${API}/dashboard-subscription/approve/${id}`, {}, getAuth()); toast.success("Approved"); fetchSubscriptions(); fetchTenantAdmins(); } catch (e) { toast.error("Failed"); } };
  const rejectSub = async (id) => { try { await axios.put(`${API}/admin/reject-subscription/${id}`, {}, getAuth()); toast.success("Rejected"); fetchSubscriptions(); } catch (e) { toast.error("Failed"); } };
  const deleteSub = async (id) => { if (!window.confirm("Delete?")) return; try { await axios.delete(`${API}/saas/subscriptions/${id}`, getAuth()); toast.success("Deleted"); fetchSubscriptions(); } catch (e) { toast.error("Failed"); } };

  // ===== BOT ADMIN =====
  const openBotAdminDialog = async (t) => {
    setSelectedTenant(t);
    setNewBotAdmin({ telegram_user_id: "", name: "", email: "", role: "admin", permissions: ["manage_bot", "verify_payments", "broadcast", "live_streams", "paid_posts", "add_subscribers"] });
    try { const { data } = await axios.get(`${API}/saas/tenants/${t.tenant_id}/admins`, getAuth()); setBotAdmins(data); } catch (e) { setBotAdmins(t.admins || []); }
    setBotAdminDialog(true);
  };
  const assignBotAdmin = async () => {
    try { await axios.post(`${API}/saas/tenants/${selectedTenant.tenant_id}/admins`, newBotAdmin, getAuth()); toast.success("Bot admin assigned"); const { data } = await axios.get(`${API}/saas/tenants/${selectedTenant.tenant_id}/admins`, getAuth()); setBotAdmins(data); setNewBotAdmin({ telegram_user_id: "", name: "", email: "", role: "admin", permissions: ["manage_bot", "verify_payments", "broadcast", "live_streams", "paid_posts", "add_subscribers"] }); fetchTenants(); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const removeBotAdmin = async (id) => { if (!window.confirm("Remove?")) return; try { await axios.delete(`${API}/saas/tenants/${selectedTenant.tenant_id}/admins/${id}`, getAuth()); toast.success("Removed"); const { data } = await axios.get(`${API}/saas/tenants/${selectedTenant.tenant_id}/admins`, getAuth()); setBotAdmins(data); fetchTenants(); } catch (e) { toast.error("Failed"); } };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" /></div>;

  return (
    <div className="space-y-6" data-testid="saas-management">
      <div>
        <h1 className="text-2xl font-bold text-foreground" data-testid="saas-title">Tenant Management</h1>
        <p className="text-muted-foreground text-sm">Manage tenants, admins, subscriptions & bot plans</p>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList data-testid="saas-tabs" className="grid grid-cols-4 w-full max-w-2xl">
          <TabsTrigger value="tenants" data-testid="saas-tab-tenants"><Users className="w-4 h-4 mr-1" /> Tenants</TabsTrigger>
          <TabsTrigger value="admins" data-testid="saas-tab-admins"><Shield className="w-4 h-4 mr-1" /> Admins</TabsTrigger>
          <TabsTrigger value="subscriptions" data-testid="saas-tab-subs"><CreditCard className="w-4 h-4 mr-1" /> Subscriptions</TabsTrigger>
          <TabsTrigger value="plans" data-testid="saas-tab-plans"><Package className="w-4 h-4 mr-1" /> Plans</TabsTrigger>
        </TabsList>

        {/* ===== TENANTS TAB ===== */}
        <TabsContent value="tenants" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-foreground">Tenants ({tenants.length})</h2>
            <Button onClick={() => openTenantDialog()} data-testid="create-tenant-btn"><Plus className="w-4 h-4 mr-1" /> New Tenant</Button>
          </div>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tenant</TableHead>
                  <TableHead>Bot</TableHead>
                  <TableHead>Users</TableHead>
                  <TableHead>Active</TableHead>
                  <TableHead>Revenue</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tenants.map(t => (
                  <TableRow key={t.tenant_id} data-testid={`tenant-row-${t.tenant_id}`}>
                    <TableCell>
                      <p className="font-medium text-foreground">{t.name || t.tenant_id}</p>
                      <p className="text-xs text-muted-foreground">{t.email}</p>
                    </TableCell>
                    <TableCell className="text-sm text-foreground">{t.bot_username ? `@${t.bot_username}` : "-"}</TableCell>
                    <TableCell className="text-foreground">{t.stats?.total_users || 0}</TableCell>
                    <TableCell className="text-foreground">{t.stats?.active_subs || 0}</TableCell>
                    <TableCell className="font-semibold text-foreground">{`\u20B9${(t.stats?.revenue || 0).toLocaleString()}`}</TableCell>
                    <TableCell><Badge variant={t.status === "active" ? "default" : "destructive"}>{t.status || "active"}</Badge></TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon" onClick={() => openBotAdminDialog(t)} title="Bot Admins"><UserPlus className="w-4 h-4 text-blue-400" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => openTenantDialog(t)} title="Edit"><Edit className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => migrateData(t)} disabled={migrating} title="Migrate"><ArrowRightLeft className="w-4 h-4 text-amber-500" /></Button>
                        {t.status !== "inactive" && <Button variant="ghost" size="icon" onClick={() => deactivateTenant(t.tenant_id)} title="Deactivate"><XCircle className="w-4 h-4 text-destructive" /></Button>}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        {/* ===== TENANT ADMINS TAB ===== */}
        <TabsContent value="admins" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-foreground">Tenant Admins ({tenantAdmins.length})</h2>
            <Button onClick={() => openAdminDialog()} data-testid="create-admin-btn"><Plus className="w-4 h-4 mr-1" /> New Admin</Button>
          </div>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Tenant</TableHead>
                  <TableHead>Subscription</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tenantAdmins.length === 0 ? (
                  <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-8">No tenant admins yet.</TableCell></TableRow>
                ) : tenantAdmins.map((a, i) => (
                  <TableRow key={a.id || i} data-testid={`admin-row-${i}`}>
                    <TableCell className="font-medium text-foreground">{a.name || "-"}</TableCell>
                    <TableCell className="text-foreground">{a.email}</TableCell>
                    <TableCell><Badge variant="outline">{a.tenant_name || a.tenant_id || "Unassigned"}</Badge></TableCell>
                    <TableCell>
                      <Badge variant={a.dashboard_subscription_status === "active" ? "default" : "secondary"}>
                        {a.dashboard_subscription_status || "inactive"}
                      </Badge>
                      {a.dashboard_plan && <span className="text-xs text-muted-foreground ml-1">({a.dashboard_plan})</span>}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {a.dashboard_subscription_end ? new Date(a.dashboard_subscription_end).toLocaleDateString() : "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon" onClick={() => openAssignSubDialog(a)} title="Assign Subscription" data-testid={`assign-sub-${i}`}><CreditCard className="w-4 h-4 text-emerald-500" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => openAdminDialog(a)} title="Edit" data-testid={`edit-admin-${i}`}><Edit className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => deleteAdmin(a.id)} title="Delete" data-testid={`delete-admin-${i}`}><Trash2 className="w-4 h-4 text-destructive" /></Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        {/* ===== SUBSCRIPTIONS TAB ===== */}
        <TabsContent value="subscriptions" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-foreground">Subscription Requests ({subscriptions.length})</h2>
            <Button onClick={() => { setAssignForm({ user_id: "", plan_id: "", duration_days: 30 }); setAssignSubDialog(true); }} data-testid="assign-sub-btn"><Plus className="w-4 h-4 mr-1" /> Assign Subscription</Button>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold text-foreground">{subscriptions.filter(s => s.status === "approved").length}</p><p className="text-xs text-muted-foreground">Active</p></CardContent></Card>
            <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold text-amber-500">{subscriptions.filter(s => s.status === "pending").length}</p><p className="text-xs text-muted-foreground">Pending</p></CardContent></Card>
            <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold text-destructive">{subscriptions.filter(s => s.status === "rejected").length}</p><p className="text-xs text-muted-foreground">Rejected</p></CardContent></Card>
          </div>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Plan</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Requested</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {subscriptions.length === 0 ? (
                  <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground py-8">No subscription requests yet.</TableCell></TableRow>
                ) : subscriptions.map((s, i) => (
                  <TableRow key={s.id || i} data-testid={`sub-row-${i}`}>
                    <TableCell>
                      <p className="font-medium text-foreground">{s.user_name || s.user_email || s.user_id}</p>
                      <p className="text-xs text-muted-foreground">{s.user_email}</p>
                    </TableCell>
                    <TableCell><Badge variant="outline">{s.plan_id}</Badge></TableCell>
                    <TableCell>
                      <Badge variant={s.status === "approved" ? "default" : s.status === "pending" ? "secondary" : "destructive"}>
                        {s.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{s.created_at ? new Date(s.created_at).toLocaleDateString() : "-"}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {s.status === "pending" && (
                          <>
                            <Button variant="ghost" size="icon" onClick={() => approveSub(s.id)} title="Approve" data-testid={`approve-sub-${i}`}><Check className="w-4 h-4 text-emerald-500" /></Button>
                            <Button variant="ghost" size="icon" onClick={() => rejectSub(s.id)} title="Reject" data-testid={`reject-sub-${i}`}><X className="w-4 h-4 text-destructive" /></Button>
                          </>
                        )}
                        <Button variant="ghost" size="icon" onClick={() => deleteSub(s.id)} title="Delete" data-testid={`delete-sub-${i}`}><Trash2 className="w-4 h-4 text-destructive" /></Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        {/* ===== BOT PLANS TAB ===== */}
        <TabsContent value="plans" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-foreground">Bot Subscription Plans</h2>
            <Button onClick={() => openPlanDialog()} data-testid="create-bot-plan-btn"><Plus className="w-4 h-4 mr-1" /> New Plan</Button>
          </div>
          {plans.length === 0 ? (
            <Card><CardContent className="p-12 text-center text-muted-foreground">No plans yet.</CardContent></Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {plans.map(plan => (
                <Card key={plan.id} className={`relative ${!plan.is_active ? "opacity-60" : ""}`} data-testid={`bot-plan-${plan.id}`}>
                  {plan.is_popular && <Badge className="absolute top-3 right-3 bg-amber-500">Popular</Badge>}
                  <CardHeader className="pb-2"><CardTitle className="flex items-center gap-2"><Crown className="w-5 h-5 text-amber-500" />{plan.name}</CardTitle></CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-baseline gap-1"><span className="text-3xl font-bold text-foreground">{plan.price > 0 ? `\u20B9${plan.price.toLocaleString()}` : "Free"}</span><span className="text-sm text-muted-foreground">/ {plan.duration_days} days</span></div>
                    <div className="text-xs text-muted-foreground space-y-1"><p>Max Subs: {plan.max_subscribers}</p><p>Max Broadcasts: {plan.max_broadcasts}/day</p></div>
                    <div className="flex flex-wrap gap-1">
                      {plan.ai_verify_enabled && <Badge variant="outline" className="text-xs">AI Verify</Badge>}
                      {plan.live_stream_enabled && <Badge variant="outline" className="text-xs">Live</Badge>}
                      {plan.paid_posts_enabled && <Badge variant="outline" className="text-xs">Paid Posts</Badge>}
                    </div>
                    {plan.features?.length > 0 && (<div className="border-t pt-2"><ul className="text-xs text-muted-foreground space-y-0.5">{plan.features.map((f, i) => <li key={i} className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-green-500" />{f}</li>)}</ul></div>)}
                    <div className="flex gap-2 pt-2">
                      <Button variant="outline" size="sm" onClick={() => openPlanDialog(plan)}><Edit className="w-3 h-3 mr-1" /> Edit</Button>
                      <Button variant="destructive" size="sm" onClick={() => deletePlan(plan.id)}><Trash2 className="w-3 h-3 mr-1" /> Delete</Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* ===== PLAN DIALOG ===== */}
      <Dialog open={planDialog} onOpenChange={setPlanDialog}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="plan-dialog">
          <DialogHeader><DialogTitle>{editingPlan ? "Edit Plan" : "New Bot Plan"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label>Plan Name</Label><Input value={planForm.name} onChange={e => setPlanForm(p => ({ ...p, name: e.target.value }))} placeholder="e.g. Pro Plan" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Price (INR)</Label><Input type="number" value={planForm.price} onChange={e => setPlanForm(p => ({ ...p, price: parseInt(e.target.value) || 0 }))} /></div>
              <div><Label>Duration (days)</Label><Input type="number" value={planForm.duration_days} onChange={e => setPlanForm(p => ({ ...p, duration_days: parseInt(e.target.value) || 30 }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Max Subscribers</Label><Input type="number" value={planForm.max_subscribers} onChange={e => setPlanForm(p => ({ ...p, max_subscribers: parseInt(e.target.value) || 0 }))} /></div>
              <div><Label>Max Broadcasts/day</Label><Input type="number" value={planForm.max_broadcasts} onChange={e => setPlanForm(p => ({ ...p, max_broadcasts: parseInt(e.target.value) || 0 }))} /></div>
            </div>
            <div className="space-y-2">
              <Label>Access Controls</Label>
              <div className="flex items-center justify-between"><span className="text-sm text-foreground">AI Payment Verification</span><Switch checked={planForm.ai_verify_enabled} onCheckedChange={v => setPlanForm(p => ({ ...p, ai_verify_enabled: v }))} /></div>
              <div className="flex items-center justify-between"><span className="text-sm text-foreground">Live Streaming</span><Switch checked={planForm.live_stream_enabled} onCheckedChange={v => setPlanForm(p => ({ ...p, live_stream_enabled: v }))} /></div>
              <div className="flex items-center justify-between"><span className="text-sm text-foreground">Paid Posts</span><Switch checked={planForm.paid_posts_enabled} onCheckedChange={v => setPlanForm(p => ({ ...p, paid_posts_enabled: v }))} /></div>
              <div className="flex items-center justify-between"><span className="text-sm text-foreground">Mark as Popular</span><Switch checked={planForm.is_popular} onCheckedChange={v => setPlanForm(p => ({ ...p, is_popular: v }))} /></div>
            </div>
            <div className="space-y-2">
              <Label>Features</Label>
              <div className="flex flex-wrap gap-2">{FEATURE_OPTIONS.map(f => <Badge key={f} variant={planForm.features.includes(f) ? "default" : "outline"} className="cursor-pointer" onClick={() => toggleFeature(f)}>{planForm.features.includes(f) && <CheckCircle className="w-3 h-3 mr-1" />}{f}</Badge>)}</div>
            </div>
            <Button className="w-full" onClick={savePlan} disabled={!planForm.name.trim()}>{editingPlan ? "Update Plan" : "Create Plan"}</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== TENANT DIALOG ===== */}
      <Dialog open={tenantDialog} onOpenChange={setTenantDialog}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="tenant-dialog">
          <DialogHeader><DialogTitle>{editingTenant ? "Edit Tenant" : "New Tenant"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Creator Name</Label><Input value={tenantForm.name} onChange={e => setTenantForm(p => ({ ...p, name: e.target.value }))} placeholder="Creator name" /></div>
            <div><Label>Email</Label><Input value={tenantForm.email} onChange={e => setTenantForm(p => ({ ...p, email: e.target.value }))} placeholder="creator@email.com" /></div>
            <div><Label>Owner Telegram ID</Label><Input value={tenantForm.owner_telegram_id} onChange={e => setTenantForm(p => ({ ...p, owner_telegram_id: e.target.value }))} placeholder="123456789" /></div>
            <div><Label>Bot Token</Label><Input value={tenantForm.bot_token} onChange={e => setTenantForm(p => ({ ...p, bot_token: e.target.value }))} placeholder="Bot token" /></div>
            <div><Label>Bot Username</Label><Input value={tenantForm.bot_username} onChange={e => setTenantForm(p => ({ ...p, bot_username: e.target.value }))} placeholder="@botusername" /></div>
            <div><Label>UPI ID</Label><Input value={tenantForm.upi_id} onChange={e => setTenantForm(p => ({ ...p, upi_id: e.target.value }))} placeholder="name@paytm" /></div>
            <div><Label>Channel ID</Label><Input value={tenantForm.channel_id} onChange={e => setTenantForm(p => ({ ...p, channel_id: e.target.value }))} placeholder="-1001234567890" /></div>
            <div><Label>Razorpay Key ID</Label><Input value={tenantForm.razorpay_key_id} onChange={e => setTenantForm(p => ({ ...p, razorpay_key_id: e.target.value }))} placeholder="rzp_live_..." /></div>
            <Button className="w-full" onClick={saveTenant} disabled={!tenantForm.name.trim()}>{editingTenant ? "Update Tenant" : "Create Tenant"}</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== ADMIN DIALOG (Create/Edit Tenant Admin) ===== */}
      <Dialog open={adminDialog} onOpenChange={setAdminDialog}>
        <DialogContent className="max-w-md" data-testid="admin-dialog">
          <DialogHeader><DialogTitle>{editingAdmin ? "Edit Tenant Admin" : "Create Tenant Admin"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Name</Label><Input value={adminForm.name} onChange={e => setAdminForm(p => ({ ...p, name: e.target.value }))} placeholder="Admin name" /></div>
            <div><Label>Email</Label><Input type="email" value={adminForm.email} onChange={e => setAdminForm(p => ({ ...p, email: e.target.value }))} placeholder="admin@email.com" /></div>
            {!editingAdmin && <div><Label>Password</Label><Input type="password" value={adminForm.password} onChange={e => setAdminForm(p => ({ ...p, password: e.target.value }))} placeholder="Password" /></div>}
            <div>
              <Label>Assign to Tenant</Label>
              <Select value={adminForm.tenant_id} onValueChange={v => setAdminForm(p => ({ ...p, tenant_id: v }))}>
                <SelectTrigger><SelectValue placeholder="Select tenant" /></SelectTrigger>
                <SelectContent>
                  {tenants.map(t => <SelectItem key={t.tenant_id} value={t.tenant_id}>{t.name} ({t.tenant_id})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Button className="w-full" onClick={saveAdmin} disabled={!adminForm.email.trim() || (!editingAdmin && !adminForm.password.trim())}>{editingAdmin ? "Update Admin" : "Create Admin"}</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== ASSIGN SUBSCRIPTION DIALOG ===== */}
      <Dialog open={assignSubDialog} onOpenChange={setAssignSubDialog}>
        <DialogContent className="max-w-md" data-testid="assign-sub-dialog">
          <DialogHeader><DialogTitle>Assign Subscription</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Select Admin</Label>
              <Select value={assignForm.user_id} onValueChange={v => setAssignForm(p => ({ ...p, user_id: v }))}>
                <SelectTrigger><SelectValue placeholder="Select tenant admin" /></SelectTrigger>
                <SelectContent>
                  {tenantAdmins.map(a => <SelectItem key={a.id} value={a.id}>{a.name || a.email} ({a.tenant_name || "No tenant"})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Select Plan</Label>
              <Select value={assignForm.plan_id} onValueChange={v => setAssignForm(p => ({ ...p, plan_id: v }))}>
                <SelectTrigger><SelectValue placeholder="Select plan" /></SelectTrigger>
                <SelectContent>
                  {dashPlans.map(p => <SelectItem key={p.id} value={p.id}>{p.name} - {`\u20B9${p.price}`}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div><Label>Duration (days)</Label><Input type="number" value={assignForm.duration_days} onChange={e => setAssignForm(p => ({ ...p, duration_days: parseInt(e.target.value) || 30 }))} /></div>
            <Button className="w-full" onClick={assignSub} disabled={!assignForm.user_id || !assignForm.plan_id}>
              <CreditCard className="w-4 h-4 mr-1" /> Assign Subscription
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== BOT ADMIN DIALOG ===== */}
      <Dialog open={botAdminDialog} onOpenChange={setBotAdminDialog}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="bot-admin-dialog">
          <DialogHeader><DialogTitle>Bot Admins - {selectedTenant?.name}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="mb-2 block">Current Bot Admins ({botAdmins.length})</Label>
              {botAdmins.length === 0 ? <p className="text-sm text-muted-foreground">No bot admins</p> : (
                <div className="space-y-2">{botAdmins.map(a => (
                  <div key={a.id} className="flex items-center justify-between border rounded-lg p-3">
                    <div>
                      <p className="text-sm font-medium text-foreground">{a.name || "Admin"}</p>
                      <p className="text-xs text-muted-foreground">TG: {a.telegram_user_id} - {a.role}</p>
                      <div className="flex flex-wrap gap-1 mt-1">{(a.permissions || []).map(p => <span key={p} className="text-[10px] bg-muted px-1.5 py-0.5 rounded">{p.replace(/_/g, " ")}</span>)}</div>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => removeBotAdmin(a.id)}><Trash2 className="w-4 h-4 text-destructive" /></Button>
                  </div>
                ))}</div>
              )}
            </div>
            <div className="border-t pt-4">
              <Label className="mb-2 block">Add Bot Admin</Label>
              <div className="space-y-2">
                <Input placeholder="Telegram User ID *" value={newBotAdmin.telegram_user_id} onChange={e => setNewBotAdmin(p => ({ ...p, telegram_user_id: e.target.value }))} />
                <Input placeholder="Name" value={newBotAdmin.name} onChange={e => setNewBotAdmin(p => ({ ...p, name: e.target.value }))} />
                <Input placeholder="Email (optional)" value={newBotAdmin.email} onChange={e => setNewBotAdmin(p => ({ ...p, email: e.target.value }))} />
                <div>
                  <Label className="mb-1 block text-xs text-muted-foreground">Permissions</Label>
                  <div className="flex flex-wrap gap-1.5">{["manage_bot", "verify_payments", "broadcast", "live_streams", "paid_posts", "add_subscribers", "manage_plans", "manage_users"].map(perm => (
                    <Badge key={perm} variant={newBotAdmin.permissions?.includes(perm) ? "default" : "outline"} className="cursor-pointer text-xs"
                      onClick={() => setNewBotAdmin(p => ({ ...p, permissions: p.permissions?.includes(perm) ? p.permissions.filter(x => x !== perm) : [...(p.permissions || []), perm] }))}>{perm.replace(/_/g, " ")}</Badge>
                  ))}</div>
                </div>
                <Button onClick={assignBotAdmin} disabled={!newBotAdmin.telegram_user_id.trim()} className="w-full"><UserPlus className="w-4 h-4 mr-1" /> Assign Bot Admin</Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
