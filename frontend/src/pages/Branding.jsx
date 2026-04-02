import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Palette, Save, RotateCcw, Eye } from "lucide-react";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

const defaultBranding = {
  brand_name: "TGSubsBot",
  tagline: "Premium Subscriptions",
  primary_color: "#e11d48",
  secondary_color: "#1a1a2e",
  logo_url: "",
  favicon_url: "",
  footer_text: "Powered by TGSubsBot",
};

export default function Branding() {
  const [branding, setBranding] = useState(defaultBranding);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBranding();
  }, []);

  const fetchBranding = async () => {
    try {
      const res = await axios.get(`${API}/branding`, getAuthHeaders());
      setBranding({ ...defaultBranding, ...res.data });
    } catch {
      // Use defaults
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/branding`, branding, getAuthHeaders());
      toast.success("Branding updated! Reloading...");
      // Reload page to apply branding changes across the dashboard
      setTimeout(() => window.location.reload(), 800);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setBranding(defaultBranding);
    toast.info("Reset to defaults (save to apply)");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="branding-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-serif font-bold text-white">White-Label Branding</h1>
          <p className="text-muted-foreground mt-1">Customize your dashboard look and feel</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleReset} data-testid="branding-reset-btn">
            <RotateCcw className="w-4 h-4 mr-2" /> Reset
          </Button>
          <Button onClick={handleSave} disabled={saving} data-testid="branding-save-btn">
            <Save className="w-4 h-4 mr-2" /> {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Brand Identity */}
        <Card className="p-6 border border-border/50">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <Palette className="w-5 h-5 text-primary" /> Brand Identity
          </h2>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-white">Brand Name</label>
              <Input
                value={branding.brand_name}
                onChange={(e) => setBranding({ ...branding, brand_name: e.target.value })}
                placeholder="Your Brand Name"
                data-testid="branding-name-input"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-white">Tagline</label>
              <Input
                value={branding.tagline}
                onChange={(e) => setBranding({ ...branding, tagline: e.target.value })}
                placeholder="Your tagline"
                data-testid="branding-tagline-input"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-white">Footer Text</label>
              <Input
                value={branding.footer_text}
                onChange={(e) => setBranding({ ...branding, footer_text: e.target.value })}
                placeholder="Powered by..."
                data-testid="branding-footer-input"
              />
            </div>
          </div>
        </Card>

        {/* Colors */}
        <Card className="p-6 border border-border/50">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <Eye className="w-5 h-5 text-primary" /> Colors
          </h2>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-white">Primary Color</label>
              <div className="flex items-center gap-3 mt-1">
                <input
                  type="color"
                  value={branding.primary_color}
                  onChange={(e) => setBranding({ ...branding, primary_color: e.target.value })}
                  className="w-12 h-10 rounded cursor-pointer border-0"
                  data-testid="branding-primary-color"
                />
                <Input
                  value={branding.primary_color}
                  onChange={(e) => setBranding({ ...branding, primary_color: e.target.value })}
                  className="font-mono"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-white">Secondary Color</label>
              <div className="flex items-center gap-3 mt-1">
                <input
                  type="color"
                  value={branding.secondary_color}
                  onChange={(e) => setBranding({ ...branding, secondary_color: e.target.value })}
                  className="w-12 h-10 rounded cursor-pointer border-0"
                  data-testid="branding-secondary-color"
                />
                <Input
                  value={branding.secondary_color}
                  onChange={(e) => setBranding({ ...branding, secondary_color: e.target.value })}
                  className="font-mono"
                />
              </div>
            </div>
          </div>
        </Card>

        {/* Logo & Favicon */}
        <Card className="p-6 border border-border/50">
          <h2 className="text-lg font-semibold text-foreground mb-4">Logo & Favicon</h2>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-white">Logo URL</label>
              <Input
                value={branding.logo_url}
                onChange={(e) => setBranding({ ...branding, logo_url: e.target.value })}
                placeholder="https://example.com/logo.png"
                data-testid="branding-logo-input"
              />
              {branding.logo_url && (
                <div className="mt-2 p-3 bg-background rounded-lg border">
                  <img src={branding.logo_url} alt="Logo preview" className="h-12 object-contain" />
                </div>
              )}
            </div>
            <div>
              <label className="text-sm font-medium text-white">Favicon URL</label>
              <Input
                value={branding.favicon_url}
                onChange={(e) => setBranding({ ...branding, favicon_url: e.target.value })}
                placeholder="https://example.com/favicon.ico"
                data-testid="branding-favicon-input"
              />
            </div>
          </div>
        </Card>

        {/* Preview */}
        <Card className="p-6 border border-border/50">
          <h2 className="text-lg font-semibold text-foreground mb-4">Preview</h2>
          <div
            className="rounded-xl p-6 text-white"
            style={{ background: branding.secondary_color }}
          >
            <div className="flex items-center gap-3 mb-4">
              {branding.logo_url ? (
                <img src={branding.logo_url} alt="Logo" className="h-8 w-8 rounded" />
              ) : (
                <div className="h-8 w-8 rounded" style={{ background: branding.primary_color }} />
              )}
              <div>
                <p className="font-bold">{branding.brand_name}</p>
                <p className="text-xs opacity-70">{branding.tagline}</p>
              </div>
            </div>
            <div
              className="rounded-lg px-4 py-2 text-sm font-medium text-center text-white"
              style={{ background: branding.primary_color }}
            >
              Sample Button
            </div>
            <p className="text-xs opacity-50 mt-4 text-center">{branding.footer_text}</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
