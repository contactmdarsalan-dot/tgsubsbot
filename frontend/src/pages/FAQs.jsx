import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Switch } from "../components/ui/switch";
import { Badge } from "../components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import { toast } from "sonner";
import {
  HelpCircle,
  Plus,
  Pencil,
  Trash2,
  MessageCircle,
  Bot,
  RefreshCw,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function FAQs() {
  const [faqs, setFaqs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingFaq, setEditingFaq] = useState(null);
  const [form, setForm] = useState({
    keywords: "",
    response: "",
    is_active: true,
  });

  useEffect(() => {
    fetchFaqs();
  }, []);

  const fetchFaqs = async () => {
    try {
      const response = await axios.get(`${API}/faqs`, getAuthHeaders());
      setFaqs(response.data);
    } catch (error) {
      toast.error("Failed to fetch FAQs");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingFaq) {
        await axios.put(`${API}/faqs/${editingFaq.id}`, form, getAuthHeaders());
        toast.success("FAQ updated successfully");
      } else {
        await axios.post(`${API}/faqs`, form, getAuthHeaders());
        toast.success("FAQ created successfully");
      }

      setDialogOpen(false);
      resetForm();
      fetchFaqs();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to save FAQ");
    }
  };

  const handleEdit = (faq) => {
    setEditingFaq(faq);
    setForm({
      keywords: faq.keywords?.join(", ") || "",
      response: faq.response,
      is_active: faq.is_active,
    });
    setDialogOpen(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this FAQ?")) return;
    try {
      await axios.delete(`${API}/faqs/${id}`, getAuthHeaders());
      toast.success("FAQ deleted");
      fetchFaqs();
    } catch (error) {
      toast.error("Failed to delete FAQ");
    }
  };

  const resetForm = () => {
    setEditingFaq(null);
    setForm({
      keywords: "",
      response: "",
      is_active: true,
    });
  };

  const totalUsage = faqs.reduce((sum, f) => sum + (f.usage_count || 0), 0);
  const activeFaqs = faqs.filter(f => f.is_active);

  return (
    <div className="space-y-8" data-testid="faqs-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">FAQs & Auto-Reply</h1>
          <p className="text-muted-foreground mt-1">
            Set up automatic responses for common questions in your bot
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchFaqs}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={() => { resetForm(); setDialogOpen(true); }} data-testid="add-faq-btn">
            <Plus className="w-4 h-4 mr-2" />
            Add FAQ
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-primary/10 rounded-lg">
              <HelpCircle className="w-6 h-6 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold">{faqs.length}</p>
              <p className="text-sm text-muted-foreground">Total FAQs</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-green-100 rounded-lg">
              <Bot className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{activeFaqs.length}</p>
              <p className="text-sm text-muted-foreground">Active Auto-Replies</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-blue-100 rounded-lg">
              <MessageCircle className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{totalUsage}</p>
              <p className="text-sm text-muted-foreground">Auto-Replies Sent</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Info Box */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <h4 className="font-medium text-blue-800 mb-1">How it works</h4>
        <p className="text-sm text-blue-700">
          When a user sends a message containing any of the keywords, the bot will automatically 
          reply with your configured response. Keywords are case-insensitive.
        </p>
      </div>

      {/* FAQs List */}
      <Card>
        <CardHeader>
          <CardTitle>All FAQs</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">Loading...</div>
          ) : faqs.length === 0 ? (
            <div className="text-center py-12">
              <HelpCircle className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No FAQs created yet</p>
              <p className="text-sm text-muted-foreground mt-2">
                Add FAQs to help users get instant answers to common questions
              </p>
              <Button onClick={() => setDialogOpen(true)} className="mt-4">
                <Plus className="w-4 h-4 mr-2" />
                Add First FAQ
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {faqs.map((faq) => (
                <div
                  key={faq.id}
                  className="p-4 bg-muted/30 rounded-lg border"
                  data-testid={`faq-${faq.id}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap mb-2">
                        {faq.keywords?.map((keyword, i) => (
                          <Badge key={i} variant="secondary" className="font-mono">
                            {keyword}
                          </Badge>
                        ))}
                        <Badge variant={faq.is_active ? "default" : "outline"}>
                          {faq.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                        {faq.response}
                      </p>
                      <p className="text-xs text-muted-foreground mt-2">
                        Used {faq.usage_count || 0} times
                      </p>
                    </div>
                    <div className="flex gap-2 ml-4">
                      <Button variant="ghost" size="icon" onClick={() => handleEdit(faq)}>
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(faq.id)}>
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editingFaq ? "Edit FAQ" : "Add New FAQ"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="keywords">Keywords (comma-separated)</Label>
              <Input
                id="keywords"
                value={form.keywords}
                onChange={(e) => setForm({ ...form, keywords: e.target.value })}
                placeholder="price, cost, kitna, rate"
                required
                data-testid="faq-keywords-input"
              />
              <p className="text-xs text-muted-foreground">
                Enter keywords separated by commas. Bot will reply when user's message contains any of these.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="response">Auto-Reply Message</Label>
              <Textarea
                id="response"
                value={form.response}
                onChange={(e) => setForm({ ...form, response: e.target.value })}
                placeholder="Our plans start from ₹99/month. Use /plans to see all available options."
                rows={4}
                required
                data-testid="faq-response-input"
              />
              <p className="text-xs text-muted-foreground">
                Use HTML tags like &lt;b&gt;bold&lt;/b&gt; for formatting.
              </p>
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="is_active">Active</Label>
              <Switch
                id="is_active"
                checked={form.is_active}
                onCheckedChange={(checked) => setForm({ ...form, is_active: checked })}
                data-testid="faq-active-switch"
              />
            </div>

            <Button type="submit" className="w-full" data-testid="save-faq-btn">
              {editingFaq ? "Update FAQ" : "Create FAQ"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
