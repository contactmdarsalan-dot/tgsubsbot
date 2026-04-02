import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Badge } from "../components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { toast } from "sonner";
import {
  Users,
  Gift,
  Share2,
  Copy,
  CheckCircle,
  TrendingUp,
  Save,
  RefreshCw,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function Referrals() {
  const [referrals, setReferrals] = useState([]);
  const [settings, setSettings] = useState({
    enabled: true,
    referrer_reward_type: "discount",
    referrer_reward_value: 10,
    referee_reward_type: "discount",
    referee_reward_value: 10,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [copiedCode, setCopiedCode] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [referralsRes, settingsRes] = await Promise.all([
        axios.get(`${API}/referrals`, getAuthHeaders()),
        axios.get(`${API}/referrals/settings`, getAuthHeaders()),
      ]);
      setReferrals(referralsRes.data);
      setSettings(settingsRes.data);
    } catch (error) {
      toast.error("Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/referrals/settings`, settings, getAuthHeaders());
      toast.success("Referral settings saved");
    } catch (error) {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const copyCode = (code) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    toast.success("Referral code copied!");
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const totalReferred = referrals.reduce((sum, r) => sum + (r.referred_users?.length || 0), 0);
  const totalEarnings = referrals.reduce((sum, r) => sum + (r.total_earnings || 0), 0);
  const activeReferrers = referrals.filter(r => r.is_active && r.referred_users?.length > 0).length;

  return (
    <div className="space-y-8" data-testid="referrals-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Referral Program</h1>
          <p className="text-muted-foreground mt-1">
            Manage referral rewards and track referrals
          </p>
        </div>
        <Button variant="outline" onClick={fetchData}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-primary/10 rounded-lg">
              <Users className="w-6 h-6 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold">{referrals.length}</p>
              <p className="text-sm text-muted-foreground">Total Referrers</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-green-100 rounded-lg">
              <Share2 className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{totalReferred}</p>
              <p className="text-sm text-muted-foreground">Users Referred</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-blue-100 rounded-lg">
              <TrendingUp className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{activeReferrers}</p>
              <p className="text-sm text-muted-foreground">Active Referrers</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-purple-100 rounded-lg">
              <Gift className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">₹{totalEarnings}</p>
              <p className="text-sm text-muted-foreground">Total Rewards</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Settings Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Gift className="w-5 h-5" />
            Referral Settings
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
            <div>
              <Label className="text-base font-medium">Enable Referral Program</Label>
              <p className="text-sm text-muted-foreground">
                Allow users to generate referral codes and earn rewards
              </p>
            </div>
            <Switch
              checked={settings.enabled}
              onCheckedChange={(checked) => setSettings({ ...settings, enabled: checked })}
              data-testid="referral-enabled-switch"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Referrer Rewards */}
            <div className="p-4 border rounded-lg space-y-4">
              <h3 className="font-medium">Referrer Reward (Who Refers)</h3>
              <div className="space-y-2">
                <Label>Reward Type</Label>
                <Select
                  value={settings.referrer_reward_type}
                  onValueChange={(val) => setSettings({ ...settings, referrer_reward_type: val })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="discount">Discount %</SelectItem>
                    <SelectItem value="cash">Cash ₹</SelectItem>
                    <SelectItem value="free_days">Free Days</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Reward Value</Label>
                <Input
                  type="number"
                  value={settings.referrer_reward_value}
                  onChange={(e) => setSettings({ ...settings, referrer_reward_value: parseFloat(e.target.value) || 0 })}
                  placeholder="10"
                />
                <p className="text-xs text-muted-foreground">
                  {settings.referrer_reward_type === "discount" && "Percentage discount on next purchase"}
                  {settings.referrer_reward_type === "cash" && "Cash reward in ₹"}
                  {settings.referrer_reward_type === "free_days" && "Extra subscription days"}
                </p>
              </div>
            </div>

            {/* Referee Rewards */}
            <div className="p-4 border rounded-lg space-y-4">
              <h3 className="font-medium">Referee Reward (Who Joins)</h3>
              <div className="space-y-2">
                <Label>Reward Type</Label>
                <Select
                  value={settings.referee_reward_type}
                  onValueChange={(val) => setSettings({ ...settings, referee_reward_type: val })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="discount">Discount %</SelectItem>
                    <SelectItem value="cash">Cash ₹</SelectItem>
                    <SelectItem value="free_days">Free Days</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Reward Value</Label>
                <Input
                  type="number"
                  value={settings.referee_reward_value}
                  onChange={(e) => setSettings({ ...settings, referee_reward_value: parseFloat(e.target.value) || 0 })}
                  placeholder="10"
                />
                <p className="text-xs text-muted-foreground">
                  {settings.referee_reward_type === "discount" && "Percentage discount on first purchase"}
                  {settings.referee_reward_type === "cash" && "Cash reward in ₹"}
                  {settings.referee_reward_type === "free_days" && "Extra subscription days"}
                </p>
              </div>
            </div>
          </div>

          <Button onClick={saveSettings} disabled={saving} data-testid="save-referral-settings">
            <Save className="w-4 h-4 mr-2" />
            {saving ? "Saving..." : "Save Settings"}
          </Button>
        </CardContent>
      </Card>

      {/* Referrals List */}
      <Card>
        <CardHeader>
          <CardTitle>All Referrers</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">Loading...</div>
          ) : referrals.length === 0 ? (
            <div className="text-center py-12">
              <Share2 className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No referrals yet</p>
              <p className="text-sm text-muted-foreground mt-2">
                Users can generate referral codes via the bot using /referral command
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {referrals.map((referral) => (
                <div
                  key={referral.id}
                  className="flex items-center justify-between p-4 bg-muted/30 rounded-lg border"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center">
                      <Users className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <p className="font-medium">@{referral.referrer_username || referral.referrer_id}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <div
                          className="font-mono text-sm bg-muted px-2 py-1 rounded cursor-pointer hover:bg-muted/80 flex items-center gap-1"
                          onClick={() => copyCode(referral.referral_code)}
                        >
                          {referral.referral_code}
                          {copiedCode === referral.referral_code ? (
                            <CheckCircle className="w-3 h-3 text-green-500" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </div>
                        <Badge variant={referral.is_active ? "default" : "outline"}>
                          {referral.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold">{referral.referred_users?.length || 0}</p>
                    <p className="text-sm text-muted-foreground">Referrals</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
