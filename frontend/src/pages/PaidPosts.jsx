import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import {
  Lock,
  Unlock,
  Image,
  Video,
  Users,
  Clock,
  CheckCircle,
  XCircle,
  Eye,
  Trash2,
  Edit,
  RefreshCcw,
  IndianRupee,
  ShieldCheck,
  Layers,
  SlidersHorizontal,
  Plus,
  Upload,
  Calendar,
  Send,
} from "lucide-react";
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

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function PaidPosts() {
  const [paidPosts, setPaidPosts] = useState([]);
  const [unlockRequests, setUnlockRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingPost, setEditingPost] = useState(null);
  const [reblurring, setReblurring] = useState(null);
  const [activeTab, setActiveTab] = useState("posts"); // posts, requests, unlocked, create, scheduled
  
  // Create post form
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    channel_id: "",
    price: 99,
    blur_level: 25,
    caption: "",
    scheduled_at: "",
    isScheduled: false,
  });
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [blurPreview, setBlurPreview] = useState(null);
  const [creating, setCreating] = useState(false);
  const [channels, setChannels] = useState([]);
  const [groups, setGroups] = useState([]);
  const [scheduledPosts, setScheduledPosts] = useState([]);

  useEffect(() => {
    fetchData();
    fetchChannels();
    fetchScheduled();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [postsRes, requestsRes] = await Promise.all([
        axios.get(`${API}/paid-posts`, getAuthHeaders()),
        axios.get(`${API}/unlock-requests`, getAuthHeaders()),
      ]);
      setPaidPosts(postsRes.data);
      setUnlockRequests(requestsRes.data);
    } catch (error) {
      console.error("Failed to fetch data:", error);
      toast.error("Failed to load paid posts data");
    } finally {
      setLoading(false);
    }
  };

  const fetchChannels = async () => {
    try {
      const [chRes, grRes] = await Promise.all([
        axios.get(`${API}/channels`, getAuthHeaders()),
        axios.get(`${API}/chat-groups`, getAuthHeaders()),
      ]);
      setChannels(chRes.data || []);
      setGroups(grRes.data || []);
    } catch {}
  };

  const fetchScheduled = async () => {
    try {
      const res = await axios.get(`${API}/scheduled-posts`, getAuthHeaders());
      setScheduledPosts(res.data || []);
    } catch {}
  };

  const handlePreviewBlur = async () => {
    if (!selectedFiles.length) return;
    const firstPhoto = selectedFiles.find(f => f.type.startsWith("image/"));
    if (!firstPhoto) return toast.error("Photo chahiye preview ke liye");
    
    const formData = new FormData();
    formData.append("file", firstPhoto);
    formData.append("blur_level", createForm.blur_level);
    
    try {
      const res = await axios.post(`${API}/paid-posts/preview-blur`, formData, {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}`, "Content-Type": "multipart/form-data" },
      });
      setBlurPreview(res.data.preview_url);
    } catch (err) {
      toast.error("Preview failed");
    }
  };

  const handleCreatePost = async () => {
    if (!createForm.channel_id) return toast.error("Channel select karo");
    if (!selectedFiles.length) return toast.error("Files upload karo");
    
    setCreating(true);
    const formData = new FormData();
    formData.append("channel_id", createForm.channel_id);
    formData.append("price", createForm.price);
    formData.append("blur_level", createForm.blur_level);
    formData.append("caption", createForm.caption);
    if (createForm.isScheduled && createForm.scheduled_at) {
      formData.append("scheduled_at", new Date(createForm.scheduled_at).toISOString());
    }
    selectedFiles.forEach((f) => formData.append("files", f));
    
    try {
      const res = await axios.post(`${API}/paid-posts/create`, formData, {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}`, "Content-Type": "multipart/form-data" },
      });
      toast.success(createForm.isScheduled ? "Post scheduled!" : "Paid post created!");
      setCreateOpen(false);
      setSelectedFiles([]);
      setBlurPreview(null);
      setCreateForm({ channel_id: "", price: 99, blur_level: 25, caption: "", scheduled_at: "", isScheduled: false });
      fetchData();
      fetchScheduled();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create post");
    } finally {
      setCreating(false);
    }
  };

  const handleCancelScheduled = async (id) => {
    try {
      await axios.delete(`${API}/scheduled-posts/${id}`, getAuthHeaders());
      toast.success("Scheduled post cancelled");
      fetchScheduled();
    } catch {
      toast.error("Failed to cancel");
    }
  };

  const handleUpdatePost = async (postId, data) => {
    try {
      await axios.put(`${API}/paid-posts/${postId}`, data, getAuthHeaders());
      toast.success("Post updated successfully");
      setEditingPost(null);
      fetchData();
    } catch (error) {
      toast.error("Failed to update post");
    }
  };

  const handleDeletePost = async (postId) => {
    if (!window.confirm("Are you sure you want to deactivate this post?")) return;
    
    try {
      await axios.delete(`${API}/paid-posts/${postId}`, getAuthHeaders());
      toast.success("Post deactivated");
      fetchData();
    } catch (error) {
      toast.error("Failed to deactivate post");
    }
  };

  const handleReblur = async (postId, blurLevel) => {
    setReblurring(postId);
    try {
      await axios.post(`${API}/paid-posts/${postId}/reblur`, { blur_level: blurLevel }, getAuthHeaders());
      toast.success(`Re-blurred with level ${blurLevel}!`);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to re-blur");
    } finally {
      setReblurring(null);
    }
  };

  const handleApproveUnlock = async (requestId) => {
    try {
      await axios.post(`${API}/unlock-requests/${requestId}/approve`, {}, getAuthHeaders());
      toast.success("Unlock approved! Content sent to user.");
      fetchData();
    } catch (error) {
      toast.error("Failed to approve unlock");
    }
  };

  const handleRejectUnlock = async (requestId) => {
    if (!window.confirm("Reject this unlock request?")) return;
    
    try {
      await axios.post(`${API}/unlock-requests/${requestId}/reject`, {}, getAuthHeaders());
      toast.success("Unlock request rejected");
      fetchData();
    } catch (error) {
      toast.error("Failed to reject unlock");
    }
  };

  const handleDeleteUnlockRequest = async (requestId) => {
    if (!window.confirm("Delete this unlock request?")) return;
    try {
      await axios.delete(`${API}/unlock-requests/${requestId}`, getAuthHeaders());
      toast.success("Unlock request deleted");
      fetchData();
    } catch (error) {
      toast.error("Failed to delete unlock request");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  const pendingRequests = unlockRequests.filter(r => r.status === "pending_admin");
  const approvedRequests = unlockRequests.filter(r => r.status === "approved" || r.status === "verified" || r.status === "unlocked");
  const rejectedRequests = unlockRequests.filter(r => r.status === "rejected");
  const totalUnlocks = paidPosts.reduce((sum, p) => sum + (p.unlock_count || 0), 0);
  const activePostsCount = paidPosts.filter(p => p.is_active).length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-4xl font-bold tracking-tight text-white">Paid Posts</h1>
          <p className="text-muted-foreground mt-1">
            Manage paid content and unlock requests
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setCreateOpen(true)} data-testid="create-paid-post-btn">
            <Plus className="w-4 h-4 mr-2" />
            Create Post
          </Button>
          <Button onClick={fetchData} variant="outline" data-testid="refresh-btn">
            <RefreshCcw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="border" data-testid="stat-total-posts">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                <Lock className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{paidPosts.length}</p>
                <p className="text-sm text-muted-foreground">Total Posts</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border" data-testid="stat-active-posts">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{activePostsCount}</p>
                <p className="text-sm text-muted-foreground">Active Posts</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border" data-testid="stat-total-unlocks">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                <Unlock className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{totalUnlocks}</p>
                <p className="text-sm text-muted-foreground">Total Unlocks</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border" data-testid="stat-pending-requests">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-orange-100 flex items-center justify-center">
                <Clock className="w-5 h-5 text-orange-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{pendingRequests.length}</p>
                <p className="text-sm text-muted-foreground">Pending Requests</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border" data-testid="stat-unlocked-success">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
                <ShieldCheck className="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-emerald-600">{approvedRequests.length}</p>
                <p className="text-sm text-muted-foreground">Unlocked Success</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        <button
          onClick={() => setActiveTab("posts")}
          data-testid="tab-posts"
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "posts"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-white"
          }`}
        >
          Paid Posts ({paidPosts.length})
        </button>
        <button
          onClick={() => setActiveTab("requests")}
          data-testid="tab-requests"
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "requests"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-white"
          }`}
        >
          Unlock Requests 
          {pendingRequests.length > 0 && (
            <Badge variant="destructive" className="ml-2">{pendingRequests.length}</Badge>
          )}
        </button>
        <button
          onClick={() => setActiveTab("unlocked")}
          data-testid="tab-unlocked"
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "unlocked"
              ? "border-emerald-500 text-emerald-500"
              : "border-transparent text-muted-foreground hover:text-white"
          }`}
        >
          Unlocked Success
          {approvedRequests.length > 0 && (
            <Badge className="ml-2 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">{approvedRequests.length}</Badge>
          )}
        </button>
        <button
          onClick={() => setActiveTab("scheduled")}
          data-testid="tab-scheduled"
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "scheduled"
              ? "border-amber-500 text-amber-500"
              : "border-transparent text-muted-foreground hover:text-white"
          }`}
        >
          Scheduled
          {scheduledPosts.filter(s => s.status === "scheduled").length > 0 && (
            <Badge className="ml-2 bg-amber-500/20 text-amber-400 border border-amber-500/30">
              {scheduledPosts.filter(s => s.status === "scheduled").length}
            </Badge>
          )}
        </button>
      </div>

      {/* Paid Posts Tab */}
      {activeTab === "posts" && (
        <div className="space-y-4">
          {paidPosts.length === 0 ? (
            <Card className="border">
              <CardContent className="p-8 text-center">
                <Lock className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium mb-2">No Paid Posts Yet</h3>
                <p className="text-muted-foreground">
                  To create a paid post, send a photo/video to your channel with <code className="bg-muted px-1 rounded">/paid</code> in the caption.
                </p>
                <p className="text-sm text-muted-foreground mt-2">
                  Example: <code className="bg-muted px-1 rounded">/paid 99</code> for ₹99 unlock price
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {paidPosts.map((post) => (
                <Card key={post.id} className={`border ${!post.is_active ? 'opacity-60' : ''}`} data-testid={`paid-post-${post.id}`}>
                  <CardContent className="p-4">
                    <div className="flex items-start gap-4">
                      {/* Content Type Icon */}
                      <div className="w-16 h-16 rounded-lg bg-muted flex items-center justify-center relative">
                        {post.content_type === "video" ? (
                          <Video className="w-8 h-8 text-muted-foreground" />
                        ) : post.content_type === "media_group" ? (
                          <Layers className="w-8 h-8 text-muted-foreground" />
                        ) : (
                          <Image className="w-8 h-8 text-muted-foreground" />
                        )}
                        {(post.media_count || 0) > 1 && (
                          <span className="absolute -top-1 -right-1 bg-primary text-primary-foreground text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                            {post.media_count}
                          </span>
                        )}
                      </div>

                      {/* Post Details */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <Badge variant={post.is_active ? "default" : "secondary"}>
                            {post.is_active ? "Active" : "Inactive"}
                          </Badge>
                          <Badge variant="outline">
                            {post.content_type === "media_group" ? `${post.media_count} items` : post.content_type}
                          </Badge>
                          {post.price > 0 && (
                            <Badge variant="secondary" className="flex items-center gap-1">
                              <IndianRupee className="w-3 h-3" />
                              {post.price}
                            </Badge>
                          )}
                          <Badge variant="outline" className="text-xs flex items-center gap-1">
                            <SlidersHorizontal className="w-3 h-3" />
                            Blur: {post.blur_level || 25}
                          </Badge>
                        </div>
                        
                        <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                          {post.caption || "No caption"}
                        </p>

                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Users className="w-3 h-3" />
                            {post.unlock_count || 0} unlocks
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(post.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex gap-2 flex-wrap justify-end">
                        {editingPost === post.id ? (
                          <div className="flex flex-col gap-2 min-w-[240px]">
                            <div>
                              <Label className="text-xs">Price (₹)</Label>
                              <Input
                                type="number"
                                defaultValue={post.price}
                                id={`price-${post.id}`}
                                className="h-8 text-sm"
                              />
                            </div>
                            <div>
                              <Label className="text-xs flex items-center gap-1">
                                <SlidersHorizontal className="w-3 h-3" />
                                Blur Level: <span id={`blur-val-${post.id}`}>{post.blur_level || 25}</span>
                              </Label>
                              <input
                                type="range"
                                min="1"
                                max="100"
                                defaultValue={post.blur_level || 25}
                                id={`blur-${post.id}`}
                                className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                                onChange={(e) => {
                                  const el = document.getElementById(`blur-val-${post.id}`);
                                  if (el) el.textContent = e.target.value;
                                }}
                              />
                              <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
                                <span>Low</span><span>Medium</span><span>High</span><span>Max</span>
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                onClick={() => {
                                  const price = document.getElementById(`price-${post.id}`).value;
                                  const blur = document.getElementById(`blur-${post.id}`).value;
                                  handleUpdatePost(post.id, { 
                                    price: parseFloat(price) || 0, 
                                    blur_level: parseInt(blur) || 25 
                                  });
                                }}
                              >
                                Save
                              </Button>
                              <Button
                                size="sm"
                                variant="secondary"
                                disabled={reblurring === post.id}
                                onClick={() => {
                                  const blur = document.getElementById(`blur-${post.id}`).value;
                                  handleReblur(post.id, parseInt(blur) || 25);
                                }}
                                data-testid={`reblur-${post.id}`}
                              >
                                {reblurring === post.id ? "Blurring..." : "Re-Blur"}
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setEditingPost(null)}
                              >
                                Cancel
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setEditingPost(post.id)}
                              data-testid={`edit-post-${post.id}`}
                            >
                              <Edit className="w-4 h-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="text-red-500 hover:text-red-600"
                              onClick={() => handleDeletePost(post.id)}
                              data-testid={`delete-post-${post.id}`}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Unlock Requests Tab */}
      {activeTab === "requests" && (
        <div className="space-y-4">
          {unlockRequests.length === 0 ? (
            <Card className="border">
              <CardContent className="p-8 text-center">
                <CheckCircle className="w-12 h-12 mx-auto text-green-500 mb-4" />
                <h3 className="text-lg font-medium mb-2">No Requests Yet</h3>
                <p className="text-muted-foreground">
                  No unlock requests received.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {unlockRequests.map((request) => {
                const isApproved = request.status === "approved" || request.status === "verified" || request.status === "unlocked";
                const isRejected = request.status === "rejected";
                const isPending = request.status === "pending_admin";
                return (
                <Card key={request.id} className={`border ${isApproved ? 'border-emerald-500/30' : isRejected ? 'border-red-500/30 opacity-60' : ''}`} data-testid={`unlock-request-${request.id}`}>
                  <CardContent className="p-4">
                    <div className="flex items-start gap-4">
                      {/* Screenshot Preview */}
                      {request.screenshot_file_id ? (
                        <div className="w-32 h-32 rounded-lg overflow-hidden bg-muted flex-shrink-0">
                          <img
                            src={`${API}/telegram/file/${request.screenshot_file_id}`}
                            alt="Payment Screenshot"
                            className="w-full h-full object-cover cursor-pointer hover:opacity-80 transition-opacity"
                            onClick={() => window.open(`${API}/telegram/file/${request.screenshot_file_id}`, '_blank')}
                            onError={(e) => {
                              e.target.style.display = 'none';
                              e.target.parentElement.innerHTML = '<div class="w-full h-full flex items-center justify-center text-muted-foreground text-xs">No preview</div>';
                            }}
                          />
                        </div>
                      ) : (
                        <div className="w-32 h-32 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
                          <Image className="w-8 h-8 text-muted-foreground" />
                        </div>
                      )}

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="font-medium">
                            @{request.telegram_username || request.telegram_user_id}
                          </p>
                          {isApproved && (
                            <Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Approved</Badge>
                          )}
                          {isRejected && (
                            <Badge className="bg-red-500/20 text-red-400 border border-red-500/30">Rejected</Badge>
                          )}
                          {isPending && request.ai_result?.is_valid_payment && request.ai_result?.confidence_score >= 85 ? (
                            <Badge className="bg-green-500/20 text-green-400 border border-green-500/30">AI Verified</Badge>
                          ) : isPending ? (
                            <Badge variant="outline" className="text-amber-500 border-amber-500/30">Pending</Badge>
                          ) : null}
                        </div>
                        
                        <p className="text-sm text-muted-foreground mb-2">
                          Requested unlock for post - Expected: Rs.{request.expected_amount || "N/A"}
                        </p>

                        {request.ai_result && (
                          <div className="text-xs text-muted-foreground mb-2">
                            <span className="font-medium">AI Confidence:</span> {request.ai_result.confidence_score || 0}%
                            {request.ai_result.is_valid_payment && 
                              <Badge variant="secondary" className="ml-2 text-xs">Valid Payment</Badge>
                            }
                          </div>
                        )}

                        <div className="text-xs text-muted-foreground">
                          <Clock className="w-3 h-3 inline mr-1" />
                          {new Date(request.created_at).toLocaleString()}
                        </div>
                      </div>

                      <div className="flex flex-col gap-2">
                        {request.screenshot_file_id && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => window.open(`${API}/telegram/file/${request.screenshot_file_id}`, '_blank')}
                            data-testid={`view-screenshot-${request.id}`}
                          >
                            <Eye className="w-4 h-4 mr-1" />
                            View
                          </Button>
                        )}
                        {isPending ? (
                          <>
                            <Button
                              size="sm"
                              onClick={() => handleApproveUnlock(request.id)}
                              data-testid={`approve-unlock-${request.id}`}
                            >
                              <CheckCircle className="w-4 h-4 mr-1" />
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="text-red-500"
                              onClick={() => handleRejectUnlock(request.id)}
                              data-testid={`reject-unlock-${request.id}`}
                            >
                              <XCircle className="w-4 h-4 mr-1" />
                              Reject
                            </Button>
                          </>
                        ) : isApproved ? (
                          <Button size="sm" variant="outline" disabled className="text-emerald-500 border-emerald-500/30 cursor-default" data-testid={`status-approved-${request.id}`}>
                            <ShieldCheck className="w-4 h-4 mr-1" />
                            Verified
                          </Button>
                        ) : isRejected ? (
                          <Button size="sm" variant="outline" disabled className="text-red-400 border-red-500/30 cursor-default" data-testid={`status-rejected-${request.id}`}>
                            <XCircle className="w-4 h-4 mr-1" />
                            Rejected
                          </Button>
                        ) : null}
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-red-500 hover:text-red-600 hover:bg-red-500/10"
                          onClick={() => handleDeleteUnlockRequest(request.id)}
                          data-testid={`delete-unlock-${request.id}`}
                        >
                          <Trash2 className="w-4 h-4 mr-1" />
                          Delete
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
              })}
            </div>
          )}
        </div>
      )}

      {/* Unlocked Success Tab */}
      {activeTab === "unlocked" && (
        <div className="space-y-4">
          {approvedRequests.length === 0 ? (
            <Card className="border">
              <CardContent className="p-8 text-center">
                <Unlock className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
                <h3 className="text-lg font-medium mb-2">No Unlocked Posts Yet</h3>
                <p className="text-muted-foreground">
                  Approved unlock requests will appear here.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {approvedRequests.map((request) => (
                <Card key={request.id} className="border border-emerald-500/20 bg-emerald-500/5" data-testid={`unlocked-success-${request.id}`}>
                  <CardContent className="p-4">
                    <div className="flex items-start gap-4">
                      {request.screenshot_file_id ? (
                        <div className="w-20 h-20 rounded-lg overflow-hidden bg-muted flex-shrink-0">
                          <img
                            src={`${API}/telegram/file/${request.screenshot_file_id}`}
                            alt="Payment"
                            className="w-full h-full object-cover cursor-pointer hover:opacity-80 transition-opacity"
                            onClick={() => window.open(`${API}/telegram/file/${request.screenshot_file_id}`, '_blank')}
                            onError={(e) => {
                              e.target.style.display = 'none';
                              e.target.parentElement.innerHTML = '<div class="w-full h-full flex items-center justify-center text-muted-foreground text-xs">No img</div>';
                            }}
                          />
                        </div>
                      ) : (
                        <div className="w-20 h-20 rounded-lg bg-emerald-500/10 flex items-center justify-center flex-shrink-0">
                          <ShieldCheck className="w-8 h-8 text-emerald-500" />
                        </div>
                      )}

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="font-medium">
                            @{request.telegram_username || request.telegram_user_id}
                          </p>
                          <Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                            <ShieldCheck className="w-3 h-3 mr-1" />
                            Unlocked
                          </Badge>
                        </div>
                        
                        <p className="text-sm text-muted-foreground">
                          Paid Rs.{request.expected_amount || "N/A"} - Content delivered
                        </p>

                        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                          <span>
                            <Clock className="w-3 h-3 inline mr-1" />
                            {new Date(request.created_at).toLocaleString()}
                          </span>
                          {request.ai_result?.confidence_score && (
                            <span>AI: {request.ai_result.confidence_score}%</span>
                          )}
                        </div>
                      </div>

                      <div className="flex-shrink-0">
                        <div className="px-3 py-1.5 rounded-full bg-emerald-500/10 text-emerald-400 text-sm font-medium">
                          Rs.{request.expected_amount || "0"}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Help Section */}
      <Card className="border bg-muted/30">
        <CardHeader>
          <CardTitle className="text-lg">How Paid Posts Work</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <div className="flex gap-3">
            <div className="w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">1</div>
            <p>Post a photo/video in your channel with <code className="bg-background px-1 rounded">/paid</code> in the caption</p>
          </div>
          <div className="flex gap-3">
            <div className="w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">2</div>
            <p>Bot automatically blurs the content and adds an "Unlock" button</p>
          </div>
          <div className="flex gap-3">
            <div className="w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">3</div>
            <p>Users click unlock, pay via Razorpay or QR, and content is delivered</p>
          </div>
          <div className="mt-4 p-3 bg-primary/10 border border-primary/20 rounded-lg space-y-2">
            <p className="text-primary/80">
              <strong>Price:</strong> <code className="bg-primary/10 px-1 rounded">/paid 99</code> for Rs.99 unlock
            </p>
            <p className="text-primary/80">
              <strong>Blur Control:</strong> <code className="bg-primary/10 px-1 rounded">/paid 99 blur:high</code> — options: low, medium, high, extreme, max or 1-100
            </p>
            <p className="text-primary/80">
              <strong>Multiple Media:</strong> Select multiple photos/videos together as album, add <code className="bg-primary/10 px-1 rounded">/paid 99</code> in caption
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Scheduled Posts Tab */}
      {activeTab === "scheduled" && (
        <div className="space-y-3">
          {scheduledPosts.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Calendar className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-muted-foreground">No scheduled posts. Create one with the "Create Post" button!</p>
              </CardContent>
            </Card>
          ) : (
            scheduledPosts.map((sp) => (
              <Card key={sp.id} data-testid={`scheduled-${sp.id}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant={sp.status === "scheduled" ? "default" : sp.status === "published" ? "secondary" : "destructive"}>
                          {sp.status}
                        </Badge>
                        <Badge variant="outline" className="flex items-center gap-1">
                          <IndianRupee className="w-3 h-3" />
                          {sp.price}
                        </Badge>
                        <Badge variant="outline">
                          {sp.saved_files?.length || 0} file(s)
                        </Badge>
                      </div>
                      <p className="text-sm mb-1">{sp.caption || "No caption"}</p>
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        Scheduled: {new Date(sp.scheduled_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex gap-2 items-start">
                      {sp.blurred_preview_path && (
                        <img
                          src={`${process.env.REACT_APP_BACKEND_URL?.replace(/\/api\/?$/, "")}${sp.blurred_preview_path}`}
                          alt="Preview"
                          className="w-16 h-16 rounded-lg object-cover border"
                        />
                      )}
                      {sp.status === "scheduled" && (
                        <Button size="sm" variant="outline" className="text-red-500" onClick={() => handleCancelScheduled(sp.id)}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}

      {/* Create Post Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create Paid Post</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {/* File Upload */}
            <div>
              <Label>Upload Photos / Videos</Label>
              <div className="border-2 border-dashed border-primary/30 rounded-lg p-6 text-center mt-2 cursor-pointer hover:border-primary/60 transition-colors"
                onClick={() => document.getElementById("file-upload-input").click()}>
                <Upload className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">Click to upload photos/videos</p>
                <p className="text-xs text-muted-foreground mt-1">Multiple files allowed</p>
              </div>
              <input
                id="file-upload-input"
                type="file"
                multiple
                accept="image/*,video/*"
                className="hidden"
                onChange={(e) => {
                  setSelectedFiles(Array.from(e.target.files));
                  setBlurPreview(null);
                }}
              />
              {selectedFiles.length > 0 && (
                <div className="mt-2 space-y-1">
                  {selectedFiles.map((f, i) => (
                    <div key={i} className="text-xs flex items-center gap-2 bg-muted p-2 rounded">
                      {f.type.startsWith("video/") ? <Video className="w-3 h-3" /> : <Image className="w-3 h-3" />}
                      <span className="truncate flex-1">{f.name}</span>
                      <span className="text-muted-foreground">{(f.size / 1024 / 1024).toFixed(1)}MB</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Channel ID */}
            <div>
              <Label>Channel / Group ID</Label>
              <Input
                value={createForm.channel_id}
                onChange={(e) => setCreateForm({ ...createForm, channel_id: e.target.value })}
                placeholder="-1001234567890"
                className="font-mono text-sm"
                data-testid="create-channel-input"
              />
            </div>

            {/* Price */}
            <div>
              <Label>Price (₹)</Label>
              <Input
                type="number"
                value={createForm.price}
                onChange={(e) => setCreateForm({ ...createForm, price: parseFloat(e.target.value) || 0 })}
                data-testid="create-price-input"
              />
            </div>

            {/* Blur Level */}
            <div>
              <Label className="flex items-center gap-1">
                <SlidersHorizontal className="w-3 h-3" />
                Blur Level: {createForm.blur_level}
              </Label>
              <input
                type="range"
                min="1"
                max="100"
                value={createForm.blur_level}
                onChange={(e) => { setCreateForm({ ...createForm, blur_level: parseInt(e.target.value) }); setBlurPreview(null); }}
                className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary mt-2"
                data-testid="create-blur-slider"
              />
              <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
                <span>Low</span><span>Medium</span><span>High</span><span>Max</span>
              </div>
              {selectedFiles.some(f => f.type.startsWith("image/")) && (
                <Button size="sm" variant="outline" className="mt-2" onClick={handlePreviewBlur} data-testid="preview-blur-btn">
                  <Eye className="w-3 h-3 mr-1" /> Preview Blur
                </Button>
              )}
              {blurPreview && (
                <div className="mt-2 border rounded-lg overflow-hidden">
                  <img
                    src={`${process.env.REACT_APP_BACKEND_URL?.replace(/\/api\/?$/, "")}${blurPreview}`}
                    alt="Blur Preview"
                    className="w-full h-48 object-cover"
                    data-testid="blur-preview-image"
                  />
                  <p className="text-xs text-center text-muted-foreground p-1">Blur preview (Level: {createForm.blur_level})</p>
                </div>
              )}
            </div>

            {/* Caption */}
            <div>
              <Label>Caption (optional)</Label>
              <Input
                value={createForm.caption}
                onChange={(e) => setCreateForm({ ...createForm, caption: e.target.value })}
                placeholder="Exclusive content..."
                data-testid="create-caption-input"
              />
            </div>

            {/* Schedule Toggle */}
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={createForm.isScheduled}
                  onChange={(e) => setCreateForm({ ...createForm, isScheduled: e.target.checked })}
                  className="rounded"
                />
                <Calendar className="w-4 h-4" />
                <span className="text-sm">Schedule for later</span>
              </label>
              {createForm.isScheduled && (
                <Input
                  type="datetime-local"
                  value={createForm.scheduled_at}
                  onChange={(e) => setCreateForm({ ...createForm, scheduled_at: e.target.value })}
                  data-testid="schedule-datetime-input"
                  className="text-sm"
                />
              )}
            </div>

            <Button className="w-full" onClick={handleCreatePost} disabled={creating} data-testid="submit-create-post-btn">
              {creating ? "Creating..." : createForm.isScheduled ? "Schedule Post" : "Create & Post Now"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
