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
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function PaidPosts() {
  const [paidPosts, setPaidPosts] = useState([]);
  const [unlockRequests, setUnlockRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingPost, setEditingPost] = useState(null);
  const [activeTab, setActiveTab] = useState("posts"); // posts, requests

  useEffect(() => {
    fetchData();
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  const pendingRequests = unlockRequests.filter(r => r.status === "pending_admin");
  const totalUnlocks = paidPosts.reduce((sum, p) => sum + (p.unlock_count || 0), 0);
  const activePostsCount = paidPosts.filter(p => p.is_active).length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-4xl font-bold tracking-tight">Paid Posts</h1>
          <p className="text-muted-foreground mt-1">
            Manage paid content and unlock requests
          </p>
        </div>
        <Button onClick={fetchData} variant="outline" data-testid="refresh-btn">
          <RefreshCcw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        <button
          onClick={() => setActiveTab("posts")}
          data-testid="tab-posts"
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "posts"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
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
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Unlock Requests 
          {pendingRequests.length > 0 && (
            <Badge variant="destructive" className="ml-2">{pendingRequests.length}</Badge>
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
                      <div className="w-16 h-16 rounded-lg bg-muted flex items-center justify-center">
                        {post.content_type === "video" ? (
                          <Video className="w-8 h-8 text-muted-foreground" />
                        ) : (
                          <Image className="w-8 h-8 text-muted-foreground" />
                        )}
                      </div>

                      {/* Post Details */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant={post.is_active ? "default" : "secondary"}>
                            {post.is_active ? "Active" : "Inactive"}
                          </Badge>
                          <Badge variant="outline">{post.content_type}</Badge>
                          {post.price > 0 && (
                            <Badge variant="secondary" className="flex items-center gap-1">
                              <IndianRupee className="w-3 h-3" />
                              {post.price}
                            </Badge>
                          )}
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
                      <div className="flex gap-2">
                        {editingPost === post.id ? (
                          <div className="flex flex-col gap-2 min-w-[200px]">
                            <div>
                              <Label className="text-xs">Price (₹)</Label>
                              <Input
                                type="number"
                                defaultValue={post.price}
                                id={`price-${post.id}`}
                                className="h-8 text-sm"
                              />
                            </div>
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                onClick={() => {
                                  const price = document.getElementById(`price-${post.id}`).value;
                                  handleUpdatePost(post.id, { price: parseFloat(price) || 0 });
                                }}
                              >
                                Save
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
          {pendingRequests.length === 0 ? (
            <Card className="border">
              <CardContent className="p-8 text-center">
                <CheckCircle className="w-12 h-12 mx-auto text-green-500 mb-4" />
                <h3 className="text-lg font-medium mb-2">All Caught Up!</h3>
                <p className="text-muted-foreground">
                  No pending unlock requests to review.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {pendingRequests.map((request) => (
                <Card key={request.id} className="border" data-testid={`unlock-request-${request.id}`}>
                  <CardContent className="p-4">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-full bg-orange-100 flex items-center justify-center">
                        <Clock className="w-6 h-6 text-orange-600" />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="font-medium">
                            @{request.telegram_username || request.telegram_user_id}
                          </p>
                          <Badge variant="outline">Pending</Badge>
                        </div>
                        
                        <p className="text-sm text-muted-foreground mb-2">
                          Requested unlock for post • Expected: ₹{request.expected_amount || "N/A"}
                        </p>

                        {request.ai_result && (
                          <div className="text-xs text-muted-foreground mb-2">
                            AI Confidence: {request.ai_result.confidence_score || 0}%
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

                      <div className="flex gap-2">
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
            <p>Users click unlock, pay via QR, send screenshot</p>
          </div>
          <div className="flex gap-3">
            <div className="w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">4</div>
            <p>Payment verified → Original content sent to user's DM</p>
          </div>
          <div className="mt-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
            <p className="text-purple-800">
              💡 <strong>Tip:</strong> Add price in caption like <code className="bg-purple-100 px-1 rounded">/paid 99</code> for ₹99 unlock. 
              Active subscribers can unlock for free!
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
