import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Slider } from "../components/ui/slider";
import { toast } from "sonner";
import {
  Settings as SettingsIcon,
  Bot,
  Link,
  QrCode,
  Save,
  ExternalLink,
  Copy,
  CheckCircle,
  Upload,
  Loader2,
  MessageSquare,
  Brain,
  AtSign,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function Settings() {
  const [settings, setSettings] = useState({
    telegram_bot_token: "",
    telegram_channel_id: "",
    promo_channel_id: "",
    website_link: "",
    qr_code_url: "",
    payment_upi_id: "",
    ai_auto_approve_threshold: 85,
    support_username: "",
    welcome_message: "",
    payment_instructions: "",
    success_message: "",
    video_call_enabled: true,
    video_call_price: 500,
    video_call_duration: 30,
    video_call_instructions: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${API}/settings`, getAuthHeaders());
      setSettings(response.data);
    } catch (error) {
      console.error("Failed to fetch settings:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/settings`, settings, getAuthHeaders());
      toast.success("Settings saved successfully");
    } catch (error) {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const copyWebhookUrl = () => {
    const webhookUrl = `${process.env.REACT_APP_BACKEND_URL}/api/telegram/webhook`;
    navigator.clipboard.writeText(webhookUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success("Webhook URL copied!");
  };

  const handleQRUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith("image/")) {
      toast.error("Please select an image file");
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast.error("File size must be less than 5MB");
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(`${API}/upload/qr-code`, formData, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("token")}`,
          "Content-Type": "multipart/form-data",
        },
      });

      // Construct full URL
      const baseUrl = process.env.REACT_APP_BACKEND_URL.replace("/api", "");
      const fullUrl = `${baseUrl}${response.data.url}`;
      
      setSettings({ ...settings, qr_code_url: fullUrl });
      toast.success("QR code uploaded! Click Save to apply.");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to upload QR code");
    } finally {
      setUploading(false);
    }
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-4xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground mt-1">
            Configure your Telegram bot and payment settings
          </p>
        </div>
        <Button onClick={handleSave} disabled={saving} className="btn-hover" data-testid="save-settings-btn">
          <Save className="w-4 h-4 mr-2" />
          {saving ? "Saving..." : "Save Settings"}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Telegram Bot Settings */}
        <Card className="border card-hover" data-testid="telegram-settings">
          <CardHeader>
            <CardTitle className="font-heading text-lg font-bold flex items-center gap-2">
              <Bot className="w-5 h-5" />
              Telegram Bot
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="bot_token">Bot Token</Label>
              <Input
                id="bot_token"
                type="password"
                value={settings.telegram_bot_token}
                onChange={(e) =>
                  setSettings({ ...settings, telegram_bot_token: e.target.value })
                }
                placeholder="Enter your bot token from @BotFather"
                data-testid="bot-token-input"
                className="bg-muted/50 border-transparent focus:border-primary font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Get this from{" "}
                <a
                  href="https://t.me/BotFather"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  @BotFather
                </a>{" "}
                on Telegram
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="channel_id">Private Channel ID (Subscribers)</Label>
              <Input
                id="channel_id"
                value={settings.telegram_channel_id}
                onChange={(e) =>
                  setSettings({ ...settings, telegram_channel_id: e.target.value })
                }
                placeholder="e.g., -1001234567890"
                data-testid="channel-id-input"
                className="bg-muted/50 border-transparent focus:border-primary font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                The private channel where paid subscribers will be added
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="promo_channel_id">Promo Channel ID (Subscribe Button)</Label>
              <Input
                id="promo_channel_id"
                value={settings.promo_channel_id}
                onChange={(e) =>
                  setSettings({ ...settings, promo_channel_id: e.target.value })
                }
                placeholder="e.g., -1001234567890"
                data-testid="promo-channel-id-input"
                className="bg-muted/50 border-transparent focus:border-primary font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Public channel where "Subscribe Now" button will appear on every post
              </p>
            </div>

            <div className="space-y-2">
              <Label>Webhook URL</Label>
              <div className="flex gap-2">
                <Input
                  value={`${process.env.REACT_APP_BACKEND_URL}/api/telegram/webhook`}
                  readOnly
                  className="bg-muted/50 border-transparent font-mono text-sm flex-1"
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={copyWebhookUrl}
                  data-testid="copy-webhook-btn"
                >
                  {copied ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Set this URL as your bot's webhook in Telegram
              </p>
            </div>

            <div className="p-4 bg-muted/50 rounded-lg space-y-2">
              <h4 className="text-sm font-medium">How to set webhook:</h4>
              <ol className="text-xs text-muted-foreground space-y-1 list-decimal list-inside">
                <li>Copy the webhook URL above</li>
                <li>
                  Open:{" "}
                  <code className="bg-background px-1 rounded">
                    https://api.telegram.org/bot{"<YOUR_TOKEN>"}/setWebhook?url={"<WEBHOOK_URL>"}
                  </code>
                </li>
                <li>Replace placeholders and visit the URL in browser</li>
              </ol>
            </div>
          </CardContent>
        </Card>

        {/* Website & Payment Settings */}
        <Card className="border card-hover" data-testid="payment-settings">
          <CardHeader>
            <CardTitle className="font-heading text-lg font-bold flex items-center gap-2">
              <Link className="w-5 h-5" />
              Website & Payments
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="website_link">Website Link</Label>
              <Input
                id="website_link"
                type="url"
                value={settings.website_link}
                onChange={(e) =>
                  setSettings({ ...settings, website_link: e.target.value })
                }
                placeholder="https://your-website.com"
                data-testid="website-link-input"
                className="bg-muted/50 border-transparent focus:border-primary"
              />
              <p className="text-xs text-muted-foreground">
                This link is sent to new subscribers and included in follow-up messages
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="qr_code">Payment QR Code</Label>
              <div className="flex gap-2">
                <Input
                  id="qr_code"
                  type="url"
                  value={settings.qr_code_url}
                  onChange={(e) =>
                    setSettings({ ...settings, qr_code_url: e.target.value })
                  }
                  placeholder="https://example.com/qr-code.png"
                  data-testid="qr-code-input"
                  className="bg-muted/50 border-transparent focus:border-primary flex-1"
                />
                <label className="cursor-pointer">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleQRUpload}
                    className="hidden"
                    data-testid="qr-upload-input"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    disabled={uploading}
                    asChild
                  >
                    <span>
                      {uploading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Upload className="w-4 h-4" />
                      )}
                    </span>
                  </Button>
                </label>
              </div>
              <p className="text-xs text-muted-foreground">
                Paste URL or click upload button to upload QR code image (max 5MB)
              </p>
            </div>

            {settings.qr_code_url && (
              <div className="border border-border rounded-lg p-4">
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                  <QrCode className="w-4 h-4" />
                  QR Code Preview
                </h4>
                <div className="flex justify-center">
                  <img
                    src={settings.qr_code_url}
                    alt="Payment QR Code"
                    className="max-w-[200px] rounded-lg"
                    onError={(e) => {
                      e.target.style.display = "none";
                    }}
                  />
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="payment_upi_id">Payment UPI ID (AI Verification)</Label>
              <Input
                id="payment_upi_id"
                value={settings.payment_upi_id}
                onChange={(e) =>
                  setSettings({ ...settings, payment_upi_id: e.target.value })
                }
                placeholder="e.g., miraclecouplee@oksbi"
                data-testid="payment-upi-input"
                className="bg-muted/50 border-transparent focus:border-primary font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Your UPI ID for receiving payments. AI will match this with payment screenshots for auto-verification.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="ai_threshold" className="flex items-center gap-2">
                <Brain className="w-4 h-4" />
                AI Auto-Approve Threshold: {settings.ai_auto_approve_threshold || 85}%
              </Label>
              <Slider
                id="ai_threshold"
                value={[settings.ai_auto_approve_threshold || 85]}
                onValueChange={(val) => setSettings({ ...settings, ai_auto_approve_threshold: val[0] })}
                min={50}
                max={100}
                step={5}
                className="py-2"
                data-testid="ai-threshold-slider"
              />
              <p className="text-xs text-muted-foreground">
                Payments with confidence score above this threshold will be auto-approved.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="support_username" className="flex items-center gap-2">
                <AtSign className="w-4 h-4" />
                Support Username
              </Label>
              <Input
                id="support_username"
                value={settings.support_username}
                onChange={(e) => setSettings({ ...settings, support_username: e.target.value })}
                placeholder="@yourusername"
                data-testid="support-username-input"
                className="bg-muted/50 border-transparent focus:border-primary"
              />
              <p className="text-xs text-muted-foreground">
                Your Telegram username for user support contact.
              </p>
            </div>

            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <h4 className="text-sm font-medium text-green-800 mb-1">🤖 AI Payment Verification</h4>
              <p className="text-xs text-green-700">
                GPT-4o Vision analyzes payment screenshots to extract amount, UPI ID, and detect fake screenshots. 
              </p>
            </div>

            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <h4 className="text-sm font-medium text-yellow-800 mb-1">Razorpay Setup</h4>
              <p className="text-xs text-yellow-700">
                To enable Razorpay payments, add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to
                your backend environment variables.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Bot Messages Card */}
        <Card className="border" data-testid="bot-messages-card">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg flex items-center gap-2">
              <MessageSquare className="w-5 h-5" />
              Bot Messages
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="welcome_message">Welcome Message</Label>
              <Textarea
                id="welcome_message"
                value={settings.welcome_message}
                onChange={(e) => setSettings({ ...settings, welcome_message: e.target.value })}
                placeholder="👋 Welcome to our subscription bot! Use /plans to see available plans."
                rows={3}
                data-testid="welcome-message-input"
                className="bg-muted/50 border-transparent focus:border-primary"
              />
              <p className="text-xs text-muted-foreground">
                First message when user starts the bot. Use HTML tags like &lt;b&gt;bold&lt;/b&gt;.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="payment_instructions">Payment Instructions</Label>
              <Textarea
                id="payment_instructions"
                value={settings.payment_instructions}
                onChange={(e) => setSettings({ ...settings, payment_instructions: e.target.value })}
                placeholder="📱 Scan the QR code above and send payment screenshot here."
                rows={3}
                data-testid="payment-instructions-input"
                className="bg-muted/50 border-transparent focus:border-primary"
              />
              <p className="text-xs text-muted-foreground">
                Shown to user after they select a plan, along with QR code.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="success_message">Success Message</Label>
              <Textarea
                id="success_message"
                value={settings.success_message}
                onChange={(e) => setSettings({ ...settings, success_message: e.target.value })}
                placeholder="🎉 Payment verified! Your subscription is now active."
                rows={3}
                data-testid="success-message-input"
                className="bg-muted/50 border-transparent focus:border-primary"
              />
              <p className="text-xs text-muted-foreground">
                Shown after payment is verified successfully.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Video Call Settings Card */}
        <Card className="border" data-testid="video-call-settings-card">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg flex items-center gap-2">
              📹 Video Call Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <Label htmlFor="video_call_enabled">Enable Video Calls</Label>
              <input
                type="checkbox"
                id="video_call_enabled"
                checked={settings.video_call_enabled}
                onChange={(e) => setSettings({ ...settings, video_call_enabled: e.target.checked })}
                className="w-5 h-5 rounded border-gray-300"
                data-testid="video-call-enabled-checkbox"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="video_call_price">Video Call Price (₹)</Label>
              <Input
                id="video_call_price"
                type="number"
                value={settings.video_call_price}
                onChange={(e) => setSettings({ ...settings, video_call_price: parseInt(e.target.value) || 0 })}
                placeholder="500"
                data-testid="video-call-price-input"
                className="bg-muted/50 border-transparent focus:border-primary"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="video_call_duration">Default Duration (minutes)</Label>
              <Input
                id="video_call_duration"
                type="number"
                value={settings.video_call_duration}
                onChange={(e) => setSettings({ ...settings, video_call_duration: parseInt(e.target.value) || 30 })}
                placeholder="30"
                data-testid="video-call-duration-input"
                className="bg-muted/50 border-transparent focus:border-primary"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="video_call_instructions">Video Call Instructions</Label>
              <Textarea
                id="video_call_instructions"
                value={settings.video_call_instructions}
                onChange={(e) => setSettings({ ...settings, video_call_instructions: e.target.value })}
                placeholder="📹 Book a 1-on-1 video call with us! Choose a date and time."
                rows={2}
                data-testid="video-call-instructions-input"
                className="bg-muted/50 border-transparent focus:border-primary"
              />
            </div>

            <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
              <h4 className="text-sm font-medium text-purple-800 mb-1">📹 Video Call Feature</h4>
              <p className="text-xs text-purple-700">
                Users can book video calls using /videocall command. You'll see bookings in the Video Calls dashboard.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Help Section */}
      <Card className="border bg-muted/30" data-testid="help-section">
        <CardContent className="p-6">
          <h3 className="font-heading text-lg font-bold mb-4">Setup Guide</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-2">
              <h4 className="font-medium flex items-center gap-2">
                <div className="w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-bold">
                  1
                </div>
                Create Bot
              </h4>
              <p className="text-sm text-muted-foreground">
                Message @BotFather on Telegram, use /newbot command, and save the token.
              </p>
              <a
                href="https://t.me/BotFather"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline inline-flex items-center gap-1"
              >
                Open BotFather <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            <div className="space-y-2">
              <h4 className="font-medium flex items-center gap-2">
                <div className="w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-bold">
                  2
                </div>
                Get Channel ID
              </h4>
              <p className="text-sm text-muted-foreground">
                Add @RawDataBot to your private channel, it will show the channel ID.
              </p>
              <a
                href="https://t.me/RawDataBot"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline inline-flex items-center gap-1"
              >
                Open RawDataBot <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            <div className="space-y-2">
              <h4 className="font-medium flex items-center gap-2">
                <div className="w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-bold">
                  3
                </div>
                Add Bot as Admin
              </h4>
              <p className="text-sm text-muted-foreground">
                Add your bot to the private channel as admin with permission to invite users.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
