import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { Switch } from "../components/ui/switch";
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
import { Send, Users, History, CheckCircle, XCircle, Clock, Radio } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function Broadcast() {
  const [broadcasts, setBroadcasts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [form, setForm] = useState({
    message: "",
    target: "all",
    include_button: false,
    button_text: "Subscribe Now",
    button_url: "",
  });

  useEffect(() => {
    fetchBroadcasts();
  }, []);

  const fetchBroadcasts = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/broadcasts`, getAuthHeaders());
      setBroadcasts(response.data);
    } catch (error) {
      console.error("Failed to fetch broadcasts");
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!form.message.trim()) {
      toast.error("Please enter a message");
      return;
    }

    setSending(true);
    try {
      const response = await axios.post(`${API}/broadcast`, form, getAuthHeaders());
      toast.success(`Broadcast started! Sending to ${response.data.total_users} users`);
      setForm({
        message: "",
        target: "all",
        include_button: false,
        button_text: "Subscribe Now",
        button_url: "",
      });
      fetchBroadcasts();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to send broadcast");
    } finally {
      setSending(false);
    }
  };

  const getStatusBadge = (status) => {
    const variants = {
      completed: "bg-green-500/20 text-green-400 border-green-500/30",
      in_progress: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      failed: "bg-red-500/20 text-red-400 border-red-500/30",
    };
    const icons = {
      completed: <CheckCircle className="w-3 h-3 mr-1" />,
      in_progress: <Clock className="w-3 h-3 mr-1 animate-spin" />,
      failed: <XCircle className="w-3 h-3 mr-1" />,
    };
    return (
      <Badge className={`${variants[status] || variants.completed} border flex items-center`}>
        {icons[status]}
        {status === "in_progress" ? "Sending..." : status}
      </Badge>
    );
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="space-y-8" data-testid="broadcast-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white">Broadcast Messages</h1>
        <p className="text-muted-foreground mt-1">
          Send messages to all your subscribers and users
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Send Broadcast Form */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Send className="w-5 h-5" />
              Send New Broadcast
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSend} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="message">Message *</Label>
                <Textarea
                  id="message"
                  placeholder="Enter your broadcast message...&#10;&#10;You can use HTML formatting:&#10;<b>Bold</b>, <i>Italic</i>, <code>Code</code>"
                  value={form.message}
                  onChange={(e) => setForm({ ...form, message: e.target.value })}
                  rows={6}
                  data-testid="broadcast-message"
                />
                <p className="text-xs text-muted-foreground">
                  Supports HTML: &lt;b&gt;bold&lt;/b&gt;, &lt;i&gt;italic&lt;/i&gt;, &lt;a href=""&gt;link&lt;/a&gt;
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="target">Send To</Label>
                <Select
                  value={form.target}
                  onValueChange={(value) => setForm({ ...form, target: value })}
                >
                  <SelectTrigger data-testid="broadcast-target">
                    <SelectValue placeholder="Select target" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Users</SelectItem>
                    <SelectItem value="subscribers">Active Subscribers Only</SelectItem>
                    <SelectItem value="channel_members">Channel Members</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                <div>
                  <Label htmlFor="include_button">Add Button</Label>
                  <p className="text-xs text-muted-foreground">
                    Add a clickable button to your message
                  </p>
                </div>
                <Switch
                  id="include_button"
                  checked={form.include_button}
                  onCheckedChange={(checked) =>
                    setForm({ ...form, include_button: checked })
                  }
                />
              </div>

              {form.include_button && (
                <div className="space-y-3 p-3 rounded-lg border border-dashed">
                  <div className="space-y-2">
                    <Label htmlFor="button_text">Button Text</Label>
                    <Input
                      id="button_text"
                      placeholder="Subscribe Now"
                      value={form.button_text}
                      onChange={(e) =>
                        setForm({ ...form, button_text: e.target.value })
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="button_url">Button URL (optional)</Label>
                    <Input
                      id="button_url"
                      placeholder="https://... (leave empty for bot link)"
                      value={form.button_url}
                      onChange={(e) =>
                        setForm({ ...form, button_url: e.target.value })
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      Leave empty to link to your bot's /start
                    </p>
                  </div>
                </div>
              )}

              <Button
                type="submit"
                className="w-full"
                disabled={sending || !form.message.trim()}
                data-testid="send-broadcast-btn"
              >
                {sending ? (
                  <>
                    <Radio className="w-4 h-4 mr-2 animate-pulse" />
                    Sending...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4 mr-2" />
                    Send Broadcast
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Quick Stats */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="w-5 h-5" />
                Target Audience
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
                <span className="text-sm">All Users</span>
                <span className="font-mono font-bold">Everyone who interacted</span>
              </div>
              <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
                <span className="text-sm">Subscribers</span>
                <span className="font-mono font-bold">Active paid members</span>
              </div>
              <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
                <span className="text-sm">Channel Members</span>
                <span className="font-mono font-bold">Users from payments</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Tips</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-2">
              <p>• Messages are sent with rate limiting to avoid Telegram blocks</p>
              <p>• Large broadcasts may take a few minutes</p>
              <p>• Users who blocked the bot won't receive messages</p>
              <p>• Use HTML formatting for better looking messages</p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Broadcast History */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="w-5 h-5" />
            Broadcast History
          </CardTitle>
        </CardHeader>
        <CardContent>
          {broadcasts.length === 0 ? (
            <div className="text-center py-8">
              <History className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No broadcasts sent yet</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Message</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Sent</TableHead>
                  <TableHead>Failed</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {broadcasts.map((broadcast) => (
                  <TableRow key={broadcast.id}>
                    <TableCell className="max-w-xs truncate">
                      {broadcast.message.substring(0, 50)}...
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{broadcast.target}</Badge>
                    </TableCell>
                    <TableCell className="text-green-500 font-mono">
                      {broadcast.sent_count || 0}
                    </TableCell>
                    <TableCell className="text-red-500 font-mono">
                      {broadcast.failed_count || 0}
                    </TableCell>
                    <TableCell>{getStatusBadge(broadcast.status)}</TableCell>
                    <TableCell className="text-sm">
                      {formatDate(broadcast.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
