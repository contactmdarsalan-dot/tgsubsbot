import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Users, Plus, Trash2, KeyRound, Loader2, Eye, EyeOff, Shield, Mail } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });

export default function TeamManagement() {
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addDialog, setAddDialog] = useState(false);
  const [resetDialog, setResetDialog] = useState(false);
  const [resetMember, setResetMember] = useState(null);
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [resetPwd, setResetPwd] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [showResetPwd, setShowResetPwd] = useState(false);
  const [saving, setSaving] = useState(false);
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  useEffect(() => { fetchTeam(); }, []);

  const fetchTeam = async () => {
    try {
      const res = await axios.get(`${API}/tenant/team`, getAuth());
      setMembers(res.data || []);
    } catch (e) {
      console.error("Team fetch error:", e);
    } finally {
      setLoading(false);
    }
  };

  const addMember = async () => {
    if (!form.email || !form.password) { toast.error("Email and password required"); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/tenant/team`, form, getAuth());
      toast.success("Team member added!");
      setAddDialog(false);
      setForm({ name: "", email: "", password: "" });
      fetchTeam();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to add member");
    } finally {
      setSaving(false);
    }
  };

  const deleteMember = async (id, name) => {
    if (!window.confirm(`Remove ${name}?`)) return;
    try {
      await axios.delete(`${API}/tenant/team/${id}`, getAuth());
      toast.success("Member removed");
      fetchTeam();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const resetPassword = async () => {
    if (resetPwd.length < 6) { toast.error("Min 6 characters"); return; }
    setSaving(true);
    try {
      await axios.put(`${API}/tenant/team/${resetMember.id}/reset-password`, { password: resetPwd }, getAuth());
      toast.success("Password reset!");
      setResetDialog(false);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (d) => d ? new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "-";

  return (
    <div className="space-y-6" data-testid="team-management">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2" data-testid="team-title">
            <Users className="w-6 h-6 text-lime-400" /> Team Members
          </h1>
          <p className="text-sm text-zinc-500 mt-1">Manage dashboard access for your team</p>
        </div>
        <Button onClick={() => { setForm({ name: "", email: "", password: "" }); setShowPwd(false); setAddDialog(true); }} data-testid="add-member-btn">
          <Plus className="w-4 h-4 mr-1" /> Add Member
        </Button>
      </motion.div>

      {/* Team Table */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
        className="rounded-2xl border border-white/6 overflow-hidden" style={{ background: "hsl(0, 0%, 4%)" }}
      >
        {loading ? (
          <div className="flex items-center justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-lime-400" /></div>
        ) : members.length === 0 ? (
          <div className="text-center py-16">
            <Users className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
            <p className="text-zinc-500">No team members yet</p>
            <p className="text-xs text-zinc-600 mt-1">Add members to give them dashboard access</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-white/6 hover:bg-transparent">
                <TableHead className="text-zinc-500 text-xs">Name</TableHead>
                <TableHead className="text-zinc-500 text-xs">Email</TableHead>
                <TableHead className="text-zinc-500 text-xs">Status</TableHead>
                <TableHead className="text-zinc-500 text-xs">Joined</TableHead>
                <TableHead className="text-zinc-500 text-xs text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((m, i) => (
                <TableRow key={m.id} className="border-white/4 hover:bg-white/3">
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-lime-500/10 flex items-center justify-center">
                        <span className="text-xs font-bold text-lime-400">{(m.name || "U").charAt(0).toUpperCase()}</span>
                      </div>
                      <div>
                        <p className="text-sm text-white font-medium">{m.name || "Unnamed"}</p>
                        {m.id === user.id && <span className="text-[10px] text-lime-400 font-bold">YOU</span>}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-zinc-400 text-sm">{m.email}</TableCell>
                  <TableCell>
                    <Badge className={`text-[10px] ${m.dashboard_subscription_status === "active" ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-500/15 text-zinc-400"}`}>
                      {m.dashboard_subscription_status || "active"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-zinc-500 text-xs">{formatDate(m.created_at)}</TableCell>
                  <TableCell className="text-right">
                    {m.id !== user.id && (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" onClick={() => { setResetMember(m); setResetPwd(""); setShowResetPwd(false); setResetDialog(true); }} title="Reset Password" data-testid={`reset-pwd-team-${i}`}>
                          <KeyRound className="w-4 h-4 text-amber-500" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => deleteMember(m.id, m.name || m.email)} title="Remove" data-testid={`delete-team-${i}`}>
                          <Trash2 className="w-4 h-4 text-destructive" />
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </motion.div>

      {/* Add Member Dialog */}
      <Dialog open={addDialog} onOpenChange={setAddDialog}>
        <DialogContent className="max-w-md" data-testid="add-member-dialog">
          <DialogHeader><DialogTitle>Add Team Member</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Name</Label>
              <Input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Member name" data-testid="team-name-input" />
            </div>
            <div>
              <Label>Email</Label>
              <Input type="email" value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} placeholder="member@email.com" data-testid="team-email-input" />
            </div>
            <div>
              <Label>Password</Label>
              <div className="relative">
                <Input type={showPwd ? "text" : "password"} value={form.password} onChange={e => setForm(p => ({ ...p, password: e.target.value }))} placeholder="Min 6 characters" className="pr-10" data-testid="team-password-input" />
                <button type="button" onClick={() => setShowPwd(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors" data-testid="toggle-team-pwd">
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <Button className="w-full" onClick={addMember} disabled={saving || !form.email || !form.password} data-testid="save-member-btn">
              {saving ? <><Loader2 className="w-4 h-4 mr-1 animate-spin" /> Adding...</> : <><Plus className="w-4 h-4 mr-1" /> Add Member</>}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Reset Password Dialog */}
      <Dialog open={resetDialog} onOpenChange={setResetDialog}>
        <DialogContent className="max-w-sm" data-testid="reset-team-pwd-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><KeyRound className="w-5 h-5 text-amber-500" /> Reset Password</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-muted/50 border">
              <p className="text-sm font-medium text-foreground">{resetMember?.name || "Member"}</p>
              <p className="text-xs text-muted-foreground">{resetMember?.email}</p>
            </div>
            <div>
              <Label>New Password</Label>
              <div className="relative">
                <Input type={showResetPwd ? "text" : "password"} value={resetPwd} onChange={e => setResetPwd(e.target.value)} placeholder="Min 6 characters" className="pr-10" data-testid="reset-team-pwd-input" />
                <button type="button" onClick={() => setShowResetPwd(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
                  {showResetPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <Button className="w-full" onClick={resetPassword} disabled={saving || resetPwd.length < 6} data-testid="confirm-reset-team-pwd">
              {saving ? <><Loader2 className="w-4 h-4 mr-1 animate-spin" /> Resetting...</> : <><KeyRound className="w-4 h-4 mr-1" /> Reset Password</>}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
