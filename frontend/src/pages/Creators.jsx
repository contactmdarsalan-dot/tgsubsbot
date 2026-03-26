import React, { useState, useEffect } from "react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { toast } from "sonner";
import { 
  Plus, 
  Edit2, 
  Trash2, 
  Link2, 
  User, 
  Radio, 
  MessageSquare, 
  DollarSign,
  CheckCircle,
  XCircle,
  Search,
  Sparkles
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function Creators() {
  const [creators, setCreators] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [selectedCreator, setSelectedCreator] = useState(null);
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    telegram_username: "",
    revenue_share: 0,
    permissions: ["live_manage", "superchat_view"]
  });
  const [linkData, setLinkData] = useState({
    telegram_username: "",
    telegram_user_id: ""
  });

  useEffect(() => {
    fetchCreators();
  }, []);

  const fetchCreators = async () => {
    try {
      const res = await fetch(`${API}/creators`, getAuthHeaders());
      const data = await res.json();
      setCreators(data);
    } catch (err) {
      toast.error("Failed to load creators");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      if (selectedCreator) {
        await fetch(`${API}/creators/${selectedCreator.id}`, {
          method: "PUT",
          ...getAuthHeaders(),
          headers: { ...getAuthHeaders().headers, "Content-Type": "application/json" },
          body: JSON.stringify(formData)
        });
        toast.success("Creator updated!");
      } else {
        await fetch(`${API}/creators`, {
          method: "POST",
          ...getAuthHeaders(),
          headers: { ...getAuthHeaders().headers, "Content-Type": "application/json" },
          body: JSON.stringify(formData)
        });
        toast.success("Creator added!");
      }
      setDialogOpen(false);
      fetchCreators();
    } catch (err) {
      toast.error("Failed to save creator");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this creator?")) return;
    try {
      await fetch(`${API}/creators/${id}`, {
        method: "DELETE",
        ...getAuthHeaders()
      });
      toast.success("Creator deleted");
      fetchCreators();
    } catch (err) {
      toast.error("Failed to delete");
    }
  };

  const handleLinkTelegram = async () => {
    try {
      await fetch(`${API}/creators/link-telegram`, {
        method: "POST",
        ...getAuthHeaders(),
        headers: { ...getAuthHeaders().headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          creator_id: selectedCreator.id,
          ...linkData
        })
      });
      toast.success("Telegram linked!");
      setLinkDialogOpen(false);
      fetchCreators();
    } catch (err) {
      toast.error("Failed to link Telegram");
    }
  };

  const openEditDialog = (creator = null) => {
    if (creator) {
      setSelectedCreator(creator);
      setFormData({
        name: creator.name,
        email: creator.email || "",
        telegram_username: creator.telegram_username || "",
        revenue_share: creator.revenue_share || 0,
        permissions: creator.permissions || ["live_manage", "superchat_view"]
      });
    } else {
      setSelectedCreator(null);
      setFormData({
        name: "",
        email: "",
        telegram_username: "",
        revenue_share: 0,
        permissions: ["live_manage", "superchat_view"]
      });
    }
    setDialogOpen(true);
  };

  const openLinkDialog = (creator) => {
    setSelectedCreator(creator);
    setLinkData({
      telegram_username: creator.telegram_username || "",
      telegram_user_id: creator.telegram_user_id || ""
    });
    setLinkDialogOpen(true);
  };

  const filteredCreators = creators.filter(c => 
    c.name?.toLowerCase().includes(search.toLowerCase()) ||
    c.telegram_username?.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-purple-400" />
            Creators
          </h1>
          <p className="text-zinc-400 text-sm mt-1">
            Manage creators who can run live streams
          </p>
        </div>
        <Button 
          onClick={() => openEditDialog()} 
          className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Creator
        </Button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
        <Input
          placeholder="Search creators..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 bg-zinc-900/50 border-zinc-800"
        />
      </div>

      {/* Creators Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredCreators.map((creator) => (
          <Card key={creator.id} className="bg-zinc-900/50 border-zinc-800 hover:border-purple-500/50 transition-all">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold text-lg">
                    {creator.name?.charAt(0)?.toUpperCase() || "C"}
                  </div>
                  <div>
                    <CardTitle className="text-white text-lg">{creator.name}</CardTitle>
                    <CardDescription className="text-zinc-500">
                      {creator.telegram_username ? `@${creator.telegram_username}` : "No Telegram linked"}
                    </CardDescription>
                  </div>
                </div>
                <Badge variant={creator.is_active ? "default" : "destructive"} className={creator.is_active ? "bg-green-500/20 text-green-400" : ""}>
                  {creator.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Stats */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-zinc-800/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                    <Radio className="w-3 h-3" />
                    Live Access
                  </div>
                  <div className="text-white font-medium">
                    {creator.permissions?.includes("live_manage") ? (
                      <span className="text-green-400 flex items-center gap-1">
                        <CheckCircle className="w-4 h-4" /> Yes
                      </span>
                    ) : (
                      <span className="text-red-400 flex items-center gap-1">
                        <XCircle className="w-4 h-4" /> No
                      </span>
                    )}
                  </div>
                </div>
                <div className="bg-zinc-800/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                    <DollarSign className="w-3 h-3" />
                    Revenue Share
                  </div>
                  <div className="text-white font-medium">{creator.revenue_share || 0}%</div>
                </div>
              </div>

              {/* Telegram Link Status */}
              <div className="bg-zinc-800/30 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <User className="w-4 h-4 text-blue-400" />
                    <span className="text-sm text-zinc-400">Telegram</span>
                  </div>
                  {creator.telegram_user_id ? (
                    <Badge className="bg-blue-500/20 text-blue-400">Linked</Badge>
                  ) : (
                    <Badge variant="outline" className="text-yellow-400 border-yellow-400/50">Not Linked</Badge>
                  )}
                </div>
                {creator.telegram_user_id && (
                  <p className="text-xs text-zinc-500 mt-2">ID: {creator.telegram_user_id}</p>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="flex-1 border-zinc-700"
                  onClick={() => openLinkDialog(creator)}
                >
                  <Link2 className="w-4 h-4 mr-1" />
                  Link TG
                </Button>
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="flex-1 border-zinc-700"
                  onClick={() => openEditDialog(creator)}
                >
                  <Edit2 className="w-4 h-4 mr-1" />
                  Edit
                </Button>
                <Button 
                  size="sm" 
                  variant="destructive" 
                  className="px-3"
                  onClick={() => handleDelete(creator.id)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}

        {filteredCreators.length === 0 && (
          <div className="col-span-full text-center py-12">
            <Sparkles className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-zinc-400">No creators yet</h3>
            <p className="text-zinc-500 text-sm mt-1">Add your first creator to get started</p>
          </div>
        )}
      </div>

      {/* Add/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-white">
              {selectedCreator ? "Edit Creator" : "Add Creator"}
            </DialogTitle>
            <DialogDescription>
              Creators can manage live streams and superchats
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Name</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Creator name"
                className="bg-zinc-800 border-zinc-700"
              />
            </div>
            <div>
              <Label>Email (optional)</Label>
              <Input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="creator@example.com"
                className="bg-zinc-800 border-zinc-700"
              />
            </div>
            <div>
              <Label>Telegram Username</Label>
              <Input
                value={formData.telegram_username}
                onChange={(e) => setFormData({ ...formData, telegram_username: e.target.value.replace("@", "") })}
                placeholder="username (without @)"
                className="bg-zinc-800 border-zinc-700"
              />
            </div>
            <div>
              <Label>Revenue Share (%)</Label>
              <Input
                type="number"
                value={formData.revenue_share}
                onChange={(e) => setFormData({ ...formData, revenue_share: parseFloat(e.target.value) || 0 })}
                placeholder="0"
                min="0"
                max="100"
                className="bg-zinc-800 border-zinc-700"
              />
            </div>
            <div className="space-y-2">
              <Label>Permissions</Label>
              <div className="flex items-center justify-between bg-zinc-800 p-3 rounded-lg">
                <span className="text-sm">Live Stream Management</span>
                <Switch
                  checked={formData.permissions.includes("live_manage")}
                  onCheckedChange={(checked) => {
                    const perms = checked 
                      ? [...formData.permissions, "live_manage"]
                      : formData.permissions.filter(p => p !== "live_manage");
                    setFormData({ ...formData, permissions: perms });
                  }}
                />
              </div>
              <div className="flex items-center justify-between bg-zinc-800 p-3 rounded-lg">
                <span className="text-sm">View Superchats</span>
                <Switch
                  checked={formData.permissions.includes("superchat_view")}
                  onCheckedChange={(checked) => {
                    const perms = checked 
                      ? [...formData.permissions, "superchat_view"]
                      : formData.permissions.filter(p => p !== "superchat_view");
                    setFormData({ ...formData, permissions: perms });
                  }}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} className="bg-purple-600 hover:bg-purple-700">
              {selectedCreator ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Link Telegram Dialog */}
      <Dialog open={linkDialogOpen} onOpenChange={setLinkDialogOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-white">Link Telegram Account</DialogTitle>
            <DialogDescription>
              Connect the creator's Telegram account for live stream access
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Telegram Username</Label>
              <Input
                value={linkData.telegram_username}
                onChange={(e) => setLinkData({ ...linkData, telegram_username: e.target.value.replace("@", "") })}
                placeholder="username (without @)"
                className="bg-zinc-800 border-zinc-700"
              />
            </div>
            <div>
              <Label>Telegram User ID (optional)</Label>
              <Input
                value={linkData.telegram_user_id}
                onChange={(e) => setLinkData({ ...linkData, telegram_user_id: e.target.value })}
                placeholder="123456789"
                className="bg-zinc-800 border-zinc-700"
              />
              <p className="text-xs text-zinc-500 mt-1">
                User ID is found when creator messages the bot
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLinkDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleLinkTelegram} className="bg-blue-600 hover:bg-blue-700">
              Link Account
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
