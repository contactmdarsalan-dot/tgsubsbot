import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Languages, Save, MessageCircle } from "lucide-react";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

const languageLabels = {
  english: "English",
  hindi: "Hindi",
  hinglish: "Hinglish",
};

const messageLabels = {
  welcome: "Welcome Message",
  payment_verified: "Payment Verified",
  payment_rejected: "Payment Rejected",
  expired: "Subscription Expired",
  choose_plan: "Choose Plan Title",
  back_to_plans: "Back to Plans Button",
  check_status: "Check Status Button",
  send_screenshot: "Send Screenshot Prompt",
  screenshot_received: "Screenshot Received",
  cancel: "Cancel Message",
};

export default function BotLanguage() {
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeLang, setActiveLang] = useState("hinglish");

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const res = await axios.get(`${API}/bot-language`, getAuthHeaders());
      const data = res.data;
      // Ensure available_languages always exists
      if (!data.available_languages) {
        data.available_languages = ["english", "hindi", "hinglish"];
      }
      if (!data.messages) {
        data.messages = {};
      }
      setSettings(data);
      setActiveLang(data.default_language || "hinglish");
    } catch {
      toast.error("Failed to load language settings");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/bot-language`, {
        default_language: activeLang,
        messages: settings.messages,
      }, getAuthHeaders());
      toast.success("Language settings saved!");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const updateMessage = (lang, key, value) => {
    setSettings((prev) => ({
      ...prev,
      messages: {
        ...prev.messages,
        [lang]: {
          ...prev.messages[lang],
          [key]: value,
        },
      },
    }));
  };

  if (loading || !settings) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="bot-language-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif font-bold text-foreground">Bot Language</h1>
          <p className="text-muted-foreground mt-1">Customize bot messages in multiple languages</p>
        </div>
        <Button onClick={handleSave} disabled={saving} data-testid="language-save-btn">
          <Save className="w-4 h-4 mr-2" /> {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>

      {/* Default Language Selector */}
      <Card className="p-6 border border-border/50">
        <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
          <Languages className="w-5 h-5 text-primary" /> Default Bot Language
        </h2>
        <div className="flex gap-3">
          {settings.available_languages.map((lang) => (
            <button
              key={lang}
              onClick={() => setActiveLang(lang)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeLang === lang
                  ? "bg-primary text-white"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
              data-testid={`lang-btn-${lang}`}
            >
              {languageLabels[lang] || lang}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          Bot will use <strong>{languageLabels[activeLang]}</strong> as the default language for all messages.
        </p>
      </Card>

      {/* Language Tabs */}
      <div className="flex gap-2 border-b border-border/30 pb-2">
        {settings.available_languages.map((lang) => (
          <button
            key={lang}
            onClick={() => setActiveLang(lang)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-all ${
              activeLang === lang
                ? "bg-card text-primary border-b-2 border-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {languageLabels[lang] || lang}
          </button>
        ))}
      </div>

      {/* Message Editor */}
      <Card className="p-6 border border-border/50">
        <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
          <MessageCircle className="w-5 h-5 text-primary" />
          {languageLabels[activeLang]} Messages
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(messageLabels).map(([key, label]) => (
            <div key={key}>
              <label className="text-sm font-medium text-foreground">{label}</label>
              <Input
                value={settings.messages?.[activeLang]?.[key] || ""}
                onChange={(e) => updateMessage(activeLang, key, e.target.value)}
                placeholder={label}
                data-testid={`msg-${activeLang}-${key}`}
              />
            </div>
          ))}
        </div>
      </Card>

      {/* Preview */}
      <Card className="p-6 border border-border/50">
        <h2 className="text-lg font-semibold text-foreground mb-4">Bot Message Preview</h2>
        <div className="bg-[#0e1621] rounded-xl p-4 space-y-3 max-w-md">
          <div className="bg-[#182533] rounded-lg p-3 text-sm text-white/90">
            {settings.messages?.[activeLang]?.welcome || "Welcome message not set"}
          </div>
          <div className="bg-[#1d6a3a] rounded-lg p-3 text-sm text-white/90">
            {settings.messages?.[activeLang]?.payment_verified || "Payment verified message not set"}
          </div>
          <div className="bg-[#6a1d1d] rounded-lg p-3 text-sm text-white/90">
            {settings.messages?.[activeLang]?.payment_rejected || "Payment rejected message not set"}
          </div>
        </div>
      </Card>
    </div>
  );
}
