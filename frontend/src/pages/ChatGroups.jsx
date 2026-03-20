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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { toast } from "sonner";
import { Plus, Trash2, Users, Clock, RefreshCw, MessageCircle, User, Timer } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function ChatGroups() {
  const [groups, setGroups] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [groupId, setGroupId] = useState("");
  const [groupName, setGroupName] = useState("");
  const [activeTab, setActiveTab] = useState("groups"); // groups or sessions

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [groupsRes, sessionsRes] = await Promise.all([
        axios.get(`${API}/chat-groups`, getAuthHeaders()),
        axios.get(`${API}/chat-sessions`, getAuthHeaders()),
      ]);
      setGroups(groupsRes.data);
      setSessions(sessionsRes.data);
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

  const getStatusBadge = (status) => {
    const variants = {
      available: "bg-green-500/20 text-green-400 border-green-500/30",
      in_use: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      needs_cleanup: "bg-red-500/20 text-red-400 border-red-500/30",
    };
    return (
      <Badge className={`${variants[status] || variants.available} border`}>
        {status === "in_use" ? "In Use" : status === "available" ? "Available" : status}
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
          <h1 className="text-3xl font-bold tracking-tight">Chat Groups Pool</h1>
          <p className="text-muted-foreground mt-1">
            Manage groups for time-limited chat sessions (5 min / 30 min plans)
          </p>
        </div>
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={fetchData}
            data-testid="refresh-btn"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={() => setDialogOpen(true)} data-testid="add-group-btn">
            <Plus className="w-4 h-4 mr-2" />
            Add Group
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
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

      {/* Groups Table */}
      {activeTab === "groups" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5" />
              Chat Groups Pool
            </CardTitle>
          </CardHeader>
          <CardContent>
            {groups.length === 0 ? (
              <div className="text-center py-12">
                <Users className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">No groups in pool yet</p>
                <p className="text-sm text-muted-foreground mb-4">
                  Add Telegram groups to enable time-limited chat feature
                </p>
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
                              data-testid={`release-${group.group_id}`}
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
                            data-testid={`delete-${group.group_id}`}
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

      {/* Sessions Table */}
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
                <p className="text-sm text-muted-foreground">
                  Sessions will appear here when users buy chat plans
                </p>
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

      {/* How to Use Section */}
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
                <li>Convert to Supergroup (Group Settings → Upgrade)</li>
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
                <li>Add @RawDataBot or @userinfobot to group</li>
                <li>It will show the Group ID (like -100123456789)</li>
                <li>Copy the full ID including the minus sign</li>
              </ol>
            </div>
            <div>
              <h4 className="font-medium text-foreground mb-2">Step 4: Add to Pool</h4>
              <ol className="list-decimal list-inside space-y-1">
                <li>Click "Add Group" button above</li>
                <li>Paste the Group ID</li>
                <li>Give it a name (optional)</li>
              </ol>
            </div>
          </div>
        </CardContent>
      </Card>

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
                Get this from @RawDataBot or @userinfobot in the group
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
              <Button
                type="button"
                variant="outline"
                onClick={() => setDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" data-testid="submit-add-group">
                Add Group
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
