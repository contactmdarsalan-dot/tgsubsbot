import { useState, useEffect } from "react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent } from "../components/ui/card";
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
import { toast } from "sonner";
import {
  ShieldCheck,
  UserPlus,
  Trash2,
  Bot,
  Send,
  Crown,
  Radio,
  CreditCard,
  Megaphone,
  MessageSquare,
  Users,
  ToggleLeft,
  ToggleRight,
  AlertCircle,
  Pencil,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

const ALL_PERMISSIONS = [
  { key: "manage_bot", label: "Manage Bot", icon: Bot, desc: "Full bot control" },
  { key: "verify_payments", label: "Verify Payments", icon: CreditCard, desc: "Approve/reject payments" },
  { key: "broadcast", label: "Broadcast", icon: Megaphone, desc: "Send messages to all users" },
  { key: "live_manage", label: "Live Streams", icon: Radio, desc: "Create & manage live sessions" },
  { key: "superchat_view", label: "Super Chats", icon: MessageSquare, desc: "View super chat messages" },
  { key: "add_subscribers", label: "Add Subscribers", icon: Users, desc: "Manually add subscribers" },
];

export default function TelegramAdmins() {
  const [admins, setAdmins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingAdmin, setEditingAdmin] = useState(null);
  const [form, setForm] = useState({
    name: "",
    telegram_user_id: "",
    telegram_username: "",
    role: "admin",
    permissions: ["manage_bot", "verify_payments", "broadcast", "live_manage"],
  });

  useEffect(() => {
    fetchAdmins();
  }, []);

  const fetchAdmins = async () => {
    try {
      const response = await axios.get(`${API}/telegram-admins`, getAuthHeaders());
      setAdmins(response.data);
    } catch (error) {
      console.error("Failed to fetch admins:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!form.telegram_user_id && !form.telegram_username) {
      toast.error("Telegram User ID ya Username daalo!");
      return;
    }
    try {
      if (editingAdmin) {
        await axios.put(`${API}/telegram-admins/${editingAdmin.id}`, form, getAuthHeaders());
        toast.success("Admin updated successfully!");
      } else {
        await axios.post(`${API}/telegram-admins`, form, getAuthHeaders());
        toast.success("Telegram Admin created! Notification sent.");
      }
      setDialogOpen(false);
      setEditingAdmin(null);
      setForm({
        name: "",
        telegram_user_id: "",
        telegram_username: "",
        role: "admin",
        permissions: ["manage_bot", "verify_payments", "broadcast", "live_manage"],
      });
      fetchAdmins();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to save admin");
    }
  };

  const handleEdit = (admin) => {
    setEditingAdmin(admin);
    setForm({
      name: admin.name || "",
      telegram_user_id: admin.telegram_user_id || "",
      telegram_username: admin.telegram_username || "",
      role: admin.role || "admin",
      permissions: admin.permissions || [],
    });
    setDialogOpen(true);
  };

  const handleDialogClose = (open) => {
    setDialogOpen(open);
    if (!open) {
      setEditingAdmin(null);
      setForm({
        name: "",
        telegram_user_id: "",
        telegram_username: "",
        role: "admin",
        permissions: ["manage_bot", "verify_payments", "broadcast", "live_manage"],
      });
    }
  };

  const handleToggleActive = async (admin) => {
    try {
      await axios.put(`${API}/telegram-admins/${admin.id}`, {
        is_active: !admin.is_active,
      }, getAuthHeaders());
      toast.success(admin.is_active ? "Admin deactivated" : "Admin activated");
      fetchAdmins();
    } catch (error) {
      toast.error("Failed to update admin");
    }
  };

  const handleDelete = async (admin) => {
    if (!window.confirm(`Remove ${admin.name || admin.telegram_username || admin.telegram_user_id} as admin?`)) return;
    try {
      await axios.delete(`${API}/telegram-admins/${admin.id}`, getAuthHeaders());
      toast.success("Admin removed & notified on Telegram");
      fetchAdmins();
    } catch (error) {
      toast.error("Failed to remove admin");
    }
  };

  const togglePermission = (perm) => {
    setForm((prev) => ({
      ...prev,
      permissions: prev.permissions.includes(perm)
        ? prev.permissions.filter((p) => p !== perm)
        : [...prev.permissions, perm],
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="telegram-admins-page">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col md:flex-row md:items-center justify-between gap-4"
      >
        <div>
          <h1 className="font-serif text-4xl font-semibold tracking-tight">Telegram Admins</h1>
          <p className="text-muted-foreground mt-1">
            Manage who can control your bot directly from Telegram
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
          <DialogTrigger asChild>
            <Button className="btn-hover gap-2" data-testid="add-tg-admin-btn">
              <UserPlus className="w-4 h-4" />
              Add Telegram Admin
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle className="font-serif text-xl font-bold flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-primary" />
                {editingAdmin ? "Edit Telegram Admin" : "Add Telegram Admin"}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input
                  placeholder="Admin name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  data-testid="tg-admin-name"
                  className="bg-muted/50 border-transparent"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>Telegram User ID *</Label>
                  <Input
                    placeholder="e.g. 6323042985"
                    value={form.telegram_user_id}
                    onChange={(e) => setForm({ ...form, telegram_user_id: e.target.value })}
                    data-testid="tg-admin-userid"
                    className="bg-muted/50 border-transparent font-mono"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Username (optional)</Label>
                  <Input
                    placeholder="@username"
                    value={form.telegram_username}
                    onChange={(e) => setForm({ ...form, telegram_username: e.target.value })}
                    data-testid="tg-admin-username"
                    className="bg-muted/50 border-transparent"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Role</Label>
                <div className="flex gap-2">
                  {["admin", "moderator"].map((role) => (
                    <Button
                      key={role}
                      type="button"
                      variant={form.role === role ? "default" : "outline"}
                      size="sm"
                      onClick={() => setForm({ ...form, role })}
                      className="capitalize"
                    >
                      {role === "admin" ? <Crown className="w-3.5 h-3.5 mr-1.5" /> : <ShieldCheck className="w-3.5 h-3.5 mr-1.5" />}
                      {role}
                    </Button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <Label>Permissions</Label>
                <div className="grid grid-cols-2 gap-2">
                  {ALL_PERMISSIONS.map((perm) => {
                    const isActive = form.permissions.includes(perm.key);
                    const Icon = perm.icon;
                    return (
                      <button
                        key={perm.key}
                        type="button"
                        onClick={() => togglePermission(perm.key)}
                        className={`flex items-center gap-2 p-2.5 rounded-lg border text-left transition-all text-sm ${
                          isActive
                            ? "border-primary/50 bg-primary/10 text-primary"
                            : "border-border/50 bg-muted/30 text-muted-foreground hover:border-border"
                        }`}
                        data-testid={`perm-${perm.key}`}
                      >
                        <Icon className="w-4 h-4 flex-shrink-0" />
                        <div>
                          <p className="font-medium text-xs">{perm.label}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="bg-muted/30 rounded-lg p-3 flex items-start gap-2">
                <Send className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                <p className="text-xs text-muted-foreground">
                  A notification will be sent to this user on Telegram with their admin permissions.
                </p>
              </div>
              <Button onClick={handleCreate} className="w-full btn-hover" data-testid="confirm-add-tg-admin">
                <ShieldCheck className="w-4 h-4 mr-2" />
                {editingAdmin ? "Save Changes" : "Add Admin"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="rounded-xl bg-card border border-border/50 p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-emerald-500" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Total Admins</p>
            <p className="font-serif text-2xl font-bold">{admins.length}</p>
          </div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
          className="rounded-xl bg-card border border-border/50 p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <Crown className="w-5 h-5 text-primary" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Active</p>
            <p className="font-serif text-2xl font-bold text-emerald-500">{admins.filter(a => a.is_active).length}</p>
          </div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          className="rounded-xl bg-card border border-border/50 p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
            <AlertCircle className="w-5 h-5 text-amber-500" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Inactive</p>
            <p className="font-serif text-2xl font-bold text-amber-500">{admins.filter(a => !a.is_active).length}</p>
          </div>
        </motion.div>
      </div>

      {/* Admins List */}
      <div className="space-y-4">
        <AnimatePresence>
          {admins.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="rounded-2xl border border-dashed border-border/50 p-12 text-center"
            >
              <ShieldCheck className="w-12 h-12 text-muted-foreground/50 mx-auto mb-4" />
              <p className="text-muted-foreground">No Telegram admins yet</p>
              <p className="text-sm text-muted-foreground/70 mt-1">Add admins to let them manage the bot from Telegram</p>
            </motion.div>
          ) : (
            admins.map((admin, i) => (
              <motion.div
                key={admin.id}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -15 }}
                transition={{ delay: i * 0.05 }}
                data-testid={`tg-admin-card-${admin.id}`}
                className={`rounded-xl bg-card border p-5 transition-all ${
                  admin.is_active ? "border-border/50 hover:border-primary/30" : "border-border/30 opacity-60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-lg ${
                      admin.is_active ? "bg-gradient-to-br from-rose-500 to-red-600" : "bg-muted"
                    }`}>
                      {(admin.name || admin.telegram_username || "A").charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium">{admin.name || "Unnamed Admin"}</h3>
                        <Badge variant={admin.role === "admin" ? "default" : "secondary"} className="text-xs capitalize">
                          {admin.role}
                        </Badge>
                        {!admin.is_active && <Badge variant="outline" className="text-xs text-amber-500 border-amber-500/30">Inactive</Badge>}
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                        {admin.telegram_user_id && (
                          <span className="font-mono text-xs">ID: {admin.telegram_user_id}</span>
                        )}
                        {admin.telegram_username && (
                          <span>@{admin.telegram_username}</span>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {(admin.permissions || []).map((perm) => {
                          const permInfo = ALL_PERMISSIONS.find(p => p.key === perm);
                          return (
                            <span key={perm} className="text-[10px] px-2 py-0.5 rounded-full bg-muted/50 text-muted-foreground">
                              {permInfo?.label || perm}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEdit(admin)}
                      data-testid={`edit-admin-${admin.id}`}
                      className="text-blue-400 hover:text-blue-300"
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleToggleActive(admin)}
                      data-testid={`toggle-admin-${admin.id}`}
                      className={admin.is_active ? "text-emerald-500 hover:text-emerald-400" : "text-amber-500 hover:text-amber-400"}
                    >
                      {admin.is_active ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(admin)}
                      data-testid={`delete-admin-${admin.id}`}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
