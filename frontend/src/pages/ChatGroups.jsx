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
import {
  Plus,
  Trash2,
  Users,
  Clock,
  RefreshCw,
  MessageCircle,
  User,
  Timer,
  Radio,
  Hash,
  Lock,
  Globe,
  Megaphone,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function ChatGroups() {
  const [groups, setGroups] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [channelDialogOpen, setChannelDialogOpen] = useState(false);
  const [groupId, setGroupId] = useState("");
  const [groupName, setGroupName] = useState("");
  const [activeTab, setActiveTab] = useState("groups");
  const [channelForm, setChannelForm] = useState({
    channel_id: "",
    channel_name: "",
    channel_type: "private",
    description: "",
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [groupsRes, sessionsRes, channelsRes] = await Promise.all([
        axios.get(`${API}/chat-groups`, getAuthHeaders()),
        axios.get(`${API}/chat-sessions`, getAuthHeaders()),
        axios.get(`${API}/channels`, getAuthHeaders()),
      ]);
      setGroups(groupsRes.data);
      setSessions(sessionsRes.data);
      setChannels(channelsRes.data);
    } catch (error) {
      toast.error("Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  const handleAddGroup = async (e) => {
    e.preventDefault();
    if (!groupId.trim()) {
      toast.error("Group ID is required");
      return;
    }
    try {
      await axios.post(
        `${API}/chat-groups`,
        { group_id: groupId.trim(), group_name: groupName.trim() },
        getAuthHeaders()
      );
      toast.success("Group added to pool!");
      setDialogOpen(false);
      setGroupId("");
      setGroupName("");
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to add group");
    }
  };

  const handleAddChannel = async (e) => {
    e.preventDefault();
    if (!channelForm.channel_id.trim()) {
      toast.error("Channel ID is required");
      return;
    }
    try {
      await axios.post(`${API}/channels`, channelForm, getAuthHeaders());
      toast.success("Channel added!");
      setChannelDialogOpen(false);
      setChannelForm({ channel_id: "", channel_name: "", channel_type: "private", description: "" });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to add channel");
    }
  };

  const handleDeleteGroup = async (gid) => {
    if (!window.confirm("Remove this group from pool?")) return;
    try {
      await axios.delete(`${API}/chat-groups/${gid}`, getAuthHeaders());
      toast.success("Group removed");
      fetchData();
    } catch (error) {
      toast.error("Failed to remove group");
    }
  };

  const handleDeleteChannel = async (cid) => {
    if (!window.confirm("Remove this channel?")) return;
    try {
      await axios.delete(`${API}/channels/${cid}`, getAuthHeaders());
      toast.success("Channel removed");
      fetchData();
    } catch (error) {
      toast.error("Failed to remove channel");
    }
  };

  const handleReleaseGroup = async (gid) => {
    if (!window.confirm("Force release this group? User will be kicked.")) return;
    try {
      await axios.post(`${API}/chat-groups/${gid}/release`, {}, getAuthHeaders());
      toast.success("Group released");
      fetchData();
    } catch (error) {
      toast.error("Failed to release group");
    }
  };

  const handleRefreshChannel = async (cid) => {
    try {
      const res = await axios.post(`${API}/channels/${cid}/refresh`, {}, getAuthHeaders());
      toast.success(`Updated: ${res.data.channel_name} (${res.data.member_count} members)`);
      fetchData();
    } catch (error) {
      toast.error("Failed to refresh channel info");
    }
  };

  const getStatusBadge = (status) => {
    const variants = {
      available: "bg-green-500/20 text-green-400 border-green-500/30",
      in_use: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      needs_cleanup: "bg-red-500/20 text-red-400 border-red-500/30",
      active: "bg-green-500/20 text-green-400 border-green-500/30",
      inactive: "bg-red-500/20 text-red-400 border-red-500/30",
    };
    const labels = {
      available: "Available",
      in_use: "In Use",
      active: "Active",
      inactive: "Inactive",
    };
    return (
      <Badge className={`${variants[status] || variants.active} border`}>
        {labels[status] || status}
      </Badge>
    );
  };

  const getSessionStatusBadge = (status) => {
    const variants = {
      active: "bg-green-500/20 text-green-400 border-green-500/30",
      expired: "bg-red-500/20 text-red-400 border-red-500/30",
      renewed: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    };
    return (
      <Badge className={`${variants[status] || variants.expired} border`}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  const formatTime = (dateStr) => {
    if (!dateStr) return "-";
    const date = new Date(dateStr);
    return date.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const availableCount = groups.filter((g) => g.status === "available").length;
  const inUseCount = groups.filter((g) => g.status === "in_use").length;
  const activeSessionsCount = sessions.filter((s) => s.status === "active").length;
  const totalMembers = channels.reduce((acc, c) => acc + (c.member_count || 0), 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="chat-groups-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Groups & Channels</h1>
          <p className="text-muted-foreground mt-1">
            Manage Telegram groups for chat sessions and channels for subscriptions
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={fetchData} data-testid="refresh-btn">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          {activeTab === "channels" ? (
            <Button onClick={() => setChannelDialogOpen(true)} data-testid="add-channel-btn">
              <Plus className="w-4 h-4 mr-2" />
              Add Channel
            </Button>
          ) : activeTab === "groups" ? (
            <Button onClick={() => setDialogOpen(true)} data-testid="add-group-btn">
              <Plus className="w-4 h-4 mr-2" />
              Add Group
            </Button>
          ) : null}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-5">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-primary/10">
                <Users className="w-6 h-6 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Groups</p>
                <p className="text-2xl font-bold">{groups.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-green-500/10">
                <MessageCircle className="w-6 h-6 text-green-500" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Available</p>
                <p className="text-2xl font-bold text-green-500">{availableCount}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-yellow-500/10">
                <Clock className="w-6 h-6 text-yellow-500" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">In Use</p>
                <p className="text-2xl font-bold text-yellow-500">{inUseCount}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-purple-500/10">
                <Megaphone className="w-6 h-6 text-purple-500" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Channels</p>
                <p className="text-2xl font-bold text-purple-500">{channels.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-blue-500/10">
                <Timer className="w-6 h-6 text-blue-500" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Active Sessions</p>
                <p className="text-2xl font-bold text-blue-500">{activeSessionsCount}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab("groups")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === "groups"
              ? "text-primary border-b-2 border-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
          data-testid="tab-groups"
        >
          Groups Pool ({groups.length})
        </button>
        <button
          onClick={() => setActiveTab("channels")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === "channels"
              ? "text-primary border-b-2 border-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
          data-testid="tab-channels"
        >
          Channels ({channels.length})
        </button>
        <button
          onClick={() => setActiveTab("sessions")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === "sessions"
              ? "text-primary border-b-2 border-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
          data-testid="tab-sessions"
        >
          Chat Sessions ({sessions.length})
        </button>
      </div>

      {/* ==================== GROUPS TAB ==================== */}
      {activeTab === "groups" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5" />
              Groups Pool
            </CardTitle>
          </CardHeader>
          <CardContent>
            {groups.length === 0 ? (
              <div className="text-center py-12">
                <Users className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">No groups in pool yet</p>
                <Button onClick={() => setDialogOpen(true)}>
                  <Plus className="w-4 h-4 mr-2" />
                  Add First Group
                </Button>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Group Name</TableHead>
                    <TableHead>Group ID</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Assigned To</TableHead>
                    <TableHead>Session End</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {groups.map((group) => (
                    <TableRow key={group.id}>
                      <TableCell className="font-medium">
                        {group.group_name || "Unnamed Group"}
                      </TableCell>
                      <TableCell>
                        <code className="text-xs bg-muted px-2 py-1 rounded">
                          {group.group_id}
                        </code>
                      </TableCell>
                      <TableCell>{getStatusBadge(group.status)}</TableCell>
                      <TableCell>
                        {group.assigned_to_username ? (
                          <span className="flex items-center gap-1">
                            <User className="w-4 h-4" />
                            @{group.assigned_to_username}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {group.session_end ? formatTime(group.session_end) : "-"}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          {group.status === "in_use" && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleReleaseGroup(group.group_id)}
                            >
                              <RefreshCw className="w-4 h-4 mr-1" />
                              Release
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteGroup(group.group_id)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* ==================== CHANNELS TAB ==================== */}
      {activeTab === "channels" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Megaphone className="w-5 h-5" />
              Telegram Channels
            </CardTitle>
          </CardHeader>
          <CardContent>
            {channels.length === 0 ? (
              <div className="text-center py-12">
                <Megaphone className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">No channels added yet</p>
                <p className="text-sm text-muted-foreground mb-4">
                  Add your Telegram channels to manage subscriptions and members
                </p>
                <Button onClick={() => setChannelDialogOpen(true)}>
                  <Plus className="w-4 h-4 mr-2" />
                  Add First Channel
                </Button>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Channel Name</TableHead>
                    <TableHead>Channel ID</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Members</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {channels.map((channel) => (
                    <TableRow key={channel.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          {channel.channel_type === "private" ? (
                            <Lock className="w-4 h-4 text-yellow-500" />
                          ) : (
                            <Globe className="w-4 h-4 text-blue-500" />
                          )}
                          {channel.channel_name || "Unnamed Channel"}
                        </div>
                      </TableCell>
                      <TableCell>
                        <code className="text-xs bg-muted px-2 py-1 rounded">
                          {channel.channel_id}
                        </code>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={
                            channel.channel_type === "private"
                              ? "border-yellow-500/30 text-yellow-400"
                              : "border-blue-500/30 text-blue-400"
                          }
                        >
                          {channel.channel_type === "private" ? "Private" : "Public"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="flex items-center gap-1">
                          <Users className="w-4 h-4 text-muted-foreground" />
                          {channel.member_count || 0}
                        </span>
                      </TableCell>
                      <TableCell>{getStatusBadge(channel.status)}</TableCell>
                      <TableCell>
                        <span className="text-sm text-muted-foreground truncate max-w-[150px] block">
                          {channel.description || "-"}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleRefreshChannel(channel.channel_id)}
                            data-testid={`refresh-channel-${channel.channel_id}`}
                          >
                            <RefreshCw className="w-4 h-4 mr-1" />
                            Sync
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteChannel(channel.channel_id)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* ==================== SESSIONS TAB ==================== */}
      {activeTab === "sessions" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Timer className="w-5 h-5" />
              Chat Sessions History
            </CardTitle>
          </CardHeader>
          <CardContent>
            {sessions.length === 0 ? (
              <div className="text-center py-12">
                <Timer className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground">No chat sessions yet</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Plan Type</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Start Time</TableHead>
                    <TableHead>End Time</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sessions.map((session) => (
                    <TableRow key={session.id}>
                      <TableCell>
                        <span className="flex items-center gap-1">
                          <User className="w-4 h-4" />
                          @{session.username || session.user_id}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {session.plan_type === "5min" ? "5 Min" : "30 Min"}
                        </Badge>
                      </TableCell>
                      <TableCell>{session.duration_minutes} min</TableCell>
                      <TableCell>{formatTime(session.start_time)}</TableCell>
                      <TableCell>{formatTime(session.end_time)}</TableCell>
                      <TableCell>{getSessionStatusBadge(session.status)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* How to Use */}
      {activeTab === "groups" && (
        <Card className="border-dashed">
          <CardHeader>
            <CardTitle className="text-lg">How to Add Groups</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-muted-foreground">
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-medium text-foreground mb-2">Step 1: Create Group</h4>
                <ol className="list-decimal list-inside space-y-1">
                  <li>Create a new Telegram group</li>
                  <li>Convert to Supergroup (Group Settings)</li>
                  <li>Name it like "Chat Room 1", "Chat Room 2"</li>
                </ol>
              </div>
              <div>
                <h4 className="font-medium text-foreground mb-2">Step 2: Add Bot as Admin</h4>
                <ol className="list-decimal list-inside space-y-1">
                  <li>Add your bot to the group</li>
                  <li>Make bot an administrator</li>
                  <li>Enable all permissions for bot</li>
                </ol>
              </div>
              <div>
                <h4 className="font-medium text-foreground mb-2">Step 3: Get Group ID</h4>
                <ol className="list-decimal list-inside space-y-1">
                  <li>Add @RawDataBot to group</li>
                  <li>Copy the Group ID (like -100123456789)</li>
                </ol>
              </div>
              <div>
                <h4 className="font-medium text-foreground mb-2">Step 4: Add to Pool</h4>
                <ol className="list-decimal list-inside space-y-1">
                  <li>Click "Add Group" button</li>
                  <li>Paste the Group ID</li>
                  <li>Give it a name (optional)</li>
                </ol>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "channels" && (
        <Card className="border-dashed">
          <CardHeader>
            <CardTitle className="text-lg">How to Add Channels</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-muted-foreground">
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-medium text-foreground mb-2">Step 1: Create Channel</h4>
                <ol className="list-decimal list-inside space-y-1">
                  <li>Create a private/public Telegram channel</li>
                  <li>This is where subscribers get access</li>
                </ol>
              </div>
              <div>
                <h4 className="font-medium text-foreground mb-2">Step 2: Add Bot as Admin</h4>
                <ol className="list-decimal list-inside space-y-1">
                  <li>Add your bot to the channel</li>
                  <li>Make bot an administrator</li>
                  <li>Enable "Invite Users via Link" permission</li>
                </ol>
              </div>
              <div>
                <h4 className="font-medium text-foreground mb-2">Step 3: Get Channel ID</h4>
                <ol className="list-decimal list-inside space-y-1">
                  <li>Forward any message from channel to @RawDataBot</li>
                  <li>Copy the Channel ID (starts with -100)</li>
                </ol>
              </div>
              <div>
                <h4 className="font-medium text-foreground mb-2">Step 4: Add Here</h4>
                <ol className="list-decimal list-inside space-y-1">
                  <li>Click "Add Channel" button</li>
                  <li>Paste Channel ID, set type and name</li>
                  <li>Click "Sync" to fetch member count</li>
                </ol>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Add Group Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Chat Group to Pool</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleAddGroup} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="groupId">Group ID *</Label>
              <Input
                id="groupId"
                placeholder="-100123456789"
                value={groupId}
                onChange={(e) => setGroupId(e.target.value)}
                data-testid="input-group-id"
              />
              <p className="text-xs text-muted-foreground">
                Get this from @RawDataBot in the group
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="groupName">Group Name (Optional)</Label>
              <Input
                id="groupName"
                placeholder="Chat Room 1"
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                data-testid="input-group-name"
              />
            </div>
            <div className="flex justify-end gap-3 pt-4">
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" data-testid="submit-add-group">
                Add Group
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Add Channel Dialog */}
      <Dialog open={channelDialogOpen} onOpenChange={setChannelDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Telegram Channel</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleAddChannel} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="channelId">Channel ID *</Label>
              <Input
                id="channelId"
                placeholder="-100123456789"
                value={channelForm.channel_id}
                onChange={(e) => setChannelForm({ ...channelForm, channel_id: e.target.value })}
                data-testid="input-channel-id"
              />
              <p className="text-xs text-muted-foreground">
                Forward a message from your channel to @RawDataBot to get the ID
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="channelName">Channel Name</Label>
              <Input
                id="channelName"
                placeholder="Premium Members"
                value={channelForm.channel_name}
                onChange={(e) => setChannelForm({ ...channelForm, channel_name: e.target.value })}
                data-testid="input-channel-name"
              />
            </div>
            <div className="space-y-2">
              <Label>Channel Type</Label>
              <Select
                value={channelForm.channel_type}
                onValueChange={(val) => setChannelForm({ ...channelForm, channel_type: val })}
              >
                <SelectTrigger data-testid="select-channel-type">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="private">Private Channel</SelectItem>
                  <SelectItem value="public">Public Channel</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="channelDesc">Description (Optional)</Label>
              <Input
                id="channelDesc"
                placeholder="Premium content for subscribers"
                value={channelForm.description}
                onChange={(e) => setChannelForm({ ...channelForm, description: e.target.value })}
                data-testid="input-channel-desc"
              />
            </div>
            <div className="flex justify-end gap-3 pt-4">
              <Button type="button" variant="outline" onClick={() => setChannelDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" data-testid="submit-add-channel">
                Add Channel
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
