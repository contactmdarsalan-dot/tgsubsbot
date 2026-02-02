import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Badge } from "../components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { toast } from "sonner";
import {
  Bell,
  Clock,
  MessageSquare,
  Plus,
  Pencil,
  Trash2,
  Calendar,
  Send,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

const MESSAGE_TYPES = [
  { value: "welcome", label: "Welcome Message", icon: MessageSquare },
  { value: "reminder", label: "Renewal Reminder", icon: Bell },
  { value: "followup", label: "Follow-up Message", icon: Send },
  { value: "expiry", label: "Expiry Notice", icon: Clock },
];

export default function Automation() {
  const [settings, setSettings] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [form, setForm] = useState({
    type: "welcome",
    message: "",
    is_active: true,
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [settingsResponse, templatesResponse] = await Promise.all([
        axios.get(`${API}/settings`, getAuthHeaders()),
        axios.get(`${API}/templates`, getAuthHeaders()),
      ]);
      setSettings(settingsResponse.data);
      setTemplates(templatesResponse.data);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSettingsUpdate = async (field, value) => {
    const updatedSettings = { ...settings, [field]: value };
    setSettings(updatedSettings);
    try {
      await axios.put(`${API}/settings`, updatedSettings, getAuthHeaders());
      toast.success("Settings updated");
    } catch (error) {
      toast.error("Failed to update settings");
    }
  };

  const handleTemplateSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingTemplate) {
        await axios.put(`${API}/templates/${editingTemplate.id}`, form, getAuthHeaders());
        toast.success("Template updated");
      } else {
        await axios.post(`${API}/templates`, form, getAuthHeaders());
        toast.success("Template created");
      }
      setDialogOpen(false);
      resetForm();
      fetchData();
    } catch (error) {
      toast.error("Failed to save template");
    }
  };

  const handleDeleteTemplate = async (templateId) => {
    if (!window.confirm("Delete this template?")) return;
    try {
      await axios.delete(`${API}/templates/${templateId}`, getAuthHeaders());
      toast.success("Template deleted");
      fetchData();
    } catch (error) {
      toast.error("Failed to delete template");
    }
  };

  const handleEdit = (template) => {
    setEditingTemplate(template);
    setForm({
      type: template.type,
      message: template.message,
      is_active: template.is_active,
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setEditingTemplate(null);
    setForm({
      type: "welcome",
      message: "",
      is_active: true,
    });
  };

  const getTypeInfo = (type) => {
    return MESSAGE_TYPES.find((t) => t.value === type) || MESSAGE_TYPES[0];
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-heading text-4xl font-bold tracking-tight">Automation</h1>
        <p className="text-muted-foreground mt-1">
          Configure automatic messages and reminders
        </p>
      </div>

      {/* Automation Settings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Reminder Settings */}
        <Card className="border card-hover" data-testid="reminder-settings">
          <CardHeader>
            <CardTitle className="font-heading text-lg font-bold flex items-center gap-2">
              <Bell className="w-5 h-5" />
              Renewal Reminders
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="reminder_days">Days Before Expiry</Label>
              <div className="flex items-center gap-4">
                <Input
                  id="reminder_days"
                  type="number"
                  value={settings?.reminder_days_before || 3}
                  onChange={(e) =>
                    handleSettingsUpdate("reminder_days_before", parseInt(e.target.value))
                  }
                  min={1}
                  max={30}
                  data-testid="reminder-days-input"
                  className="w-24 bg-muted/50 border-transparent focus:border-primary"
                />
                <span className="text-sm text-muted-foreground">
                  days before subscription ends
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Users will receive a reminder message this many days before their subscription expires
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="grace_days">Grace Period</Label>
              <div className="flex items-center gap-4">
                <Input
                  id="grace_days"
                  type="number"
                  value={settings?.grace_period_days || 2}
                  onChange={(e) =>
                    handleSettingsUpdate("grace_period_days", parseInt(e.target.value))
                  }
                  min={0}
                  max={14}
                  data-testid="grace-days-input"
                  className="w-24 bg-muted/50 border-transparent focus:border-primary"
                />
                <span className="text-sm text-muted-foreground">
                  extra days after expiry
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Users will have this many extra days to renew before being removed from the channel
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Follow-up Settings */}
        <Card className="border card-hover" data-testid="followup-settings">
          <CardHeader>
            <CardTitle className="font-heading text-lg font-bold flex items-center gap-2">
              <Send className="w-5 h-5" />
              Follow-up Messages
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <Label>Enable Follow-ups</Label>
                <p className="text-xs text-muted-foreground mt-1">
                  Send promotional messages twice a week (Mon & Thu)
                </p>
              </div>
              <Switch
                checked={settings?.followup_enabled || false}
                onCheckedChange={(checked) =>
                  handleSettingsUpdate("followup_enabled", checked)
                }
                data-testid="followup-enabled-switch"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="followup_message">Follow-up Message</Label>
              <textarea
                id="followup_message"
                value={settings?.followup_message || ""}
                onChange={(e) =>
                  handleSettingsUpdate("followup_message", e.target.value)
                }
                placeholder="Check out our premium services!"
                rows={4}
                data-testid="followup-message-input"
                className="w-full px-3 py-2 bg-muted/50 border-transparent focus:border-primary rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <p className="text-xs text-muted-foreground">
                This message is sent to all active subscribers. Website link is appended automatically.
              </p>
            </div>

            <div className="p-4 bg-muted/50 rounded-lg">
              <div className="flex items-center gap-2 text-sm">
                <Calendar className="w-4 h-4 text-muted-foreground" />
                <span className="text-muted-foreground">
                  Schedule: Monday & Thursday at 10:00 AM
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Message Templates */}
      <Card className="border" data-testid="message-templates">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="font-heading text-lg font-bold flex items-center gap-2">
            <MessageSquare className="w-5 h-5" />
            Message Templates
          </CardTitle>
          <Dialog open={dialogOpen} onOpenChange={(open) => {
            setDialogOpen(open);
            if (!open) resetForm();
          }}>
            <DialogTrigger asChild>
              <Button size="sm" data-testid="create-template-btn">
                <Plus className="w-4 h-4 mr-2" />
                Add Template
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
              <DialogHeader>
                <DialogTitle className="font-heading text-xl font-bold">
                  {editingTemplate ? "Edit Template" : "Create Template"}
                </DialogTitle>
              </DialogHeader>
              <form onSubmit={handleTemplateSubmit} className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label>Message Type</Label>
                  <Select
                    value={form.type}
                    onValueChange={(value) => setForm({ ...form, type: value })}
                  >
                    <SelectTrigger data-testid="template-type-select" className="bg-muted/50 border-transparent">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {MESSAGE_TYPES.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          {type.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="message">Message Content</Label>
                  <textarea
                    id="message"
                    value={form.message}
                    onChange={(e) => setForm({ ...form, message: e.target.value })}
                    placeholder="Enter your message..."
                    rows={6}
                    required
                    data-testid="template-message-input"
                    className="w-full px-3 py-2 bg-muted/50 border-transparent focus:border-primary rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                  <p className="text-xs text-muted-foreground">
                    Supports HTML formatting: &lt;b&gt;bold&lt;/b&gt;, &lt;i&gt;italic&lt;/i&gt;
                  </p>
                </div>

                <div className="flex items-center justify-between">
                  <Label htmlFor="active">Active</Label>
                  <Switch
                    id="active"
                    checked={form.is_active}
                    onCheckedChange={(checked) => setForm({ ...form, is_active: checked })}
                    data-testid="template-active-switch"
                  />
                </div>

                <Button type="submit" className="w-full btn-hover" data-testid="template-submit-btn">
                  {editingTemplate ? "Update Template" : "Create Template"}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent>
          {templates.length > 0 ? (
            <div className="space-y-4">
              {templates.map((template) => {
                const typeInfo = getTypeInfo(template.type);
                const Icon = typeInfo.icon;
                return (
                  <div
                    key={template.id}
                    className="p-4 border border-border rounded-lg hover:border-primary/50 transition-colors"
                    data-testid={`template-card-${template.id}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                          <Icon className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="font-medium">{typeInfo.label}</h4>
                            <Badge
                              className={
                                template.is_active
                                  ? "bg-green-100 text-green-700"
                                  : "bg-gray-100 text-gray-700"
                              }
                            >
                              {template.is_active ? "Active" : "Inactive"}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground mt-1 whitespace-pre-wrap line-clamp-2">
                            {template.message}
                          </p>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleEdit(template)}
                          data-testid={`edit-template-${template.id}`}
                        >
                          <Pencil className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteTemplate(template.id)}
                          data-testid={`delete-template-${template.id}`}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12">
              <MessageSquare className="w-12 h-12 text-muted-foreground mb-4" />
              <h3 className="font-heading text-xl font-bold mb-2">No Templates Yet</h3>
              <p className="text-muted-foreground text-center mb-4">
                Create message templates for automated communications
              </p>
              <Button onClick={() => setDialogOpen(true)} data-testid="empty-create-template-btn">
                <Plus className="w-4 h-4 mr-2" />
                Create Template
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Automation Summary */}
      <Card className="border bg-muted/30" data-testid="automation-summary">
        <CardContent className="p-6">
          <h3 className="font-heading text-lg font-bold mb-4">How Automation Works</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-2">
              <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center text-primary font-bold">
                1
              </div>
              <h4 className="font-medium">New Subscription</h4>
              <p className="text-sm text-muted-foreground">
                User is added to channel + receives welcome message with website link
              </p>
            </div>
            <div className="space-y-2">
              <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center text-primary font-bold">
                2
              </div>
              <h4 className="font-medium">Renewal Reminder</h4>
              <p className="text-sm text-muted-foreground">
                {settings?.reminder_days_before || 3} days before expiry, user gets renewal reminder
              </p>
            </div>
            <div className="space-y-2">
              <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center text-primary font-bold">
                3
              </div>
              <h4 className="font-medium">Grace Period</h4>
              <p className="text-sm text-muted-foreground">
                {settings?.grace_period_days || 2} extra days given after expiry to renew
              </p>
            </div>
            <div className="space-y-2">
              <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center text-primary font-bold">
                4
              </div>
              <h4 className="font-medium">Auto Removal</h4>
              <p className="text-sm text-muted-foreground">
                If not renewed, user is automatically removed from channel
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
