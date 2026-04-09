import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { BarChart3, Plus, Trash2, Send, X } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function Polls() {
  const [polls, setPolls] = useState([]);
  const [channels, setChannels] = useState([]);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({
    question: "",
    options: ["", ""],
    channel_id: "",
    is_anonymous: true,
    allows_multiple: false,
  });
  const [sending, setSending] = useState(false);

  useEffect(() => {
    fetchPolls();
    fetchChannels();
    fetchGroups();
  }, []);

  const fetchPolls = async () => {
    try {
      const res = await axios.get(`${API}/polls`, getAuthHeaders());
      setPolls(res.data);
    } catch {
      toast.error("Failed to load polls");
    } finally {
      setLoading(false);
    }
  };

  const fetchChannels = async () => {
    try {
      const res = await axios.get(`${API}/channels`, getAuthHeaders());
      setChannels(res.data || []);
    } catch {}
  };

  const fetchGroups = async () => {
    try {
      const res = await axios.get(`${API}/chat-groups`, getAuthHeaders());
      setGroups(res.data || []);
    } catch {}
  };

  const addOption = () => {
    if (form.options.length < 10) {
      setForm({ ...form, options: [...form.options, ""] });
    }
  };

  const removeOption = (idx) => {
    if (form.options.length > 2) {
      setForm({ ...form, options: form.options.filter((_, i) => i !== idx) });
    }
  };

  const updateOption = (idx, val) => {
    const newOpts = [...form.options];
    newOpts[idx] = val;
    setForm({ ...form, options: newOpts });
  };

  const handleSend = async () => {
    if (!form.question.trim()) return toast.error("Question zaruri hai");
    const validOpts = form.options.filter((o) => o.trim());
    if (validOpts.length < 2) return toast.error("Kam se kam 2 options do");
    if (!form.channel_id) return toast.error("Channel select karo");

    setSending(true);
    try {
      await axios.post(`${API}/polls`, {
        ...form,
        options: validOpts,
      }, getAuthHeaders());
      toast.success("Poll sent to channel!");
      setDialogOpen(false);
      setForm({ question: "", options: ["", ""], channel_id: "", is_anonymous: true, allows_multiple: false });
      fetchPolls();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to send poll");
    } finally {
      setSending(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await axios.delete(`${API}/polls/${id}`, getAuthHeaders());
      toast.success("Poll deleted");
      fetchPolls();
    } catch {
      toast.error("Failed to delete");
    }
  };

  const allTargets = [
    ...channels.map((c) => ({ id: c.telegram_channel_id || c.channel_id, name: c.channel_name || c.name || "Channel", type: "Channel" })),
    ...groups.filter((g) => g.group_id && g.group_id !== "0").map((g) => ({ id: g.group_id, name: g.group_name || g.name || "Group", type: "Group" })),
  ];

  return (
    <div className="space-y-6" data-testid="polls-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="polls-title">Polls</h1>
          <p className="text-muted-foreground">Create and manage channel polls</p>
        </div>
        <Button onClick={() => setDialogOpen(true)} data-testid="create-poll-btn">
          <Plus className="w-4 h-4 mr-2" /> Create Poll
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{polls.length}</p>
              <p className="text-xs text-muted-foreground">Total Polls</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <Send className="w-8 h-8 text-green-500" />
            <div>
              <p className="text-2xl font-bold">{polls.filter((p) => p.status === "sent").length}</p>
              <p className="text-xs text-muted-foreground">Sent</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Poll List */}
      <div className="space-y-3">
        {loading ? (
          <p className="text-muted-foreground text-center py-8">Loading...</p>
        ) : polls.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <BarChart3 className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-muted-foreground">No polls yet. Create your first poll!</p>
            </CardContent>
          </Card>
        ) : (
          polls.map((poll) => (
            <Card key={poll.id} data-testid={`poll-${poll.id}`}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant={poll.status === "sent" ? "default" : poll.status === "failed" ? "destructive" : "secondary"}>
                        {poll.status}
                      </Badge>
                      {poll.is_anonymous && <Badge variant="outline">Anonymous</Badge>}
                      {poll.allows_multiple && <Badge variant="outline">Multi-Select</Badge>}
                    </div>
                    <h3 className="font-semibold text-lg mb-2">{poll.question}</h3>
                    <div className="flex flex-wrap gap-2">
                      {poll.options.map((opt, i) => (
                        <span key={i} className="text-sm bg-muted px-3 py-1 rounded-full">
                          {opt}
                        </span>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      {new Date(poll.created_at).toLocaleString()}
                    </p>
                  </div>
                  <Button size="sm" variant="outline" className="text-red-500" onClick={() => handleDelete(poll.id)}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Create Poll Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create New Poll</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Question</Label>
              <Input
                value={form.question}
                onChange={(e) => setForm({ ...form, question: e.target.value })}
                placeholder="Kya aapko yeh plan pasand aaya?"
                data-testid="poll-question-input"
              />
            </div>

            <div>
              <Label>Options (min 2, max 10)</Label>
              <div className="space-y-2 mt-2">
                {form.options.map((opt, idx) => (
                  <div key={idx} className="flex gap-2">
                    <Input
                      value={opt}
                      onChange={(e) => updateOption(idx, e.target.value)}
                      placeholder={`Option ${idx + 1}`}
                      data-testid={`poll-option-${idx}`}
                    />
                    {form.options.length > 2 && (
                      <Button size="sm" variant="ghost" onClick={() => removeOption(idx)}>
                        <X className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
              {form.options.length < 10 && (
                <Button size="sm" variant="outline" className="mt-2" onClick={addOption}>
                  <Plus className="w-4 h-4 mr-1" /> Add Option
                </Button>
              )}
            </div>

            <div>
              <Label>Send to Channel/Group</Label>
              <Select value={form.channel_id} onValueChange={(v) => setForm({ ...form, channel_id: v })}>
                <SelectTrigger data-testid="poll-channel-select">
                  <SelectValue placeholder="Select channel..." />
                </SelectTrigger>
                <SelectContent>
                  {allTargets.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name} ({t.type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="mt-2">
                <Label className="text-xs text-muted-foreground">Or enter Channel ID manually:</Label>
                <Input
                  value={form.channel_id}
                  onChange={(e) => setForm({ ...form, channel_id: e.target.value })}
                  placeholder="-1001234567890"
                  className="mt-1 font-mono text-sm"
                  data-testid="poll-channel-manual"
                />
              </div>
            </div>

            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_anonymous}
                  onChange={(e) => setForm({ ...form, is_anonymous: e.target.checked })}
                  className="rounded"
                />
                <span className="text-sm">Anonymous</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.allows_multiple}
                  onChange={(e) => setForm({ ...form, allows_multiple: e.target.checked })}
                  className="rounded"
                />
                <span className="text-sm">Multi-select</span>
              </label>
            </div>

            <Button className="w-full" onClick={handleSend} disabled={sending} data-testid="send-poll-btn">
              {sending ? "Sending..." : "Send Poll to Channel"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
