import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSearchParams } from "react-router-dom";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "plans", label: "Plans" },
  { id: "settings", label: "Settings" },
];

export default function CreatorDashboard() {
  const [searchParams] = useSearchParams();
  const tenantId = searchParams.get("tenant") || "";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  const [error, setError] = useState("");

  // Plans
  const [showNewPlan, setShowNewPlan] = useState(false);
  const [newPlan, setNewPlan] = useState({ name: "", price: 99, duration_days: 30, features: "" });
  const [planLoading, setPlanLoading] = useState(false);

  // Settings
  const [settingsForm, setSettingsForm] = useState({});
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState("");

  const fetchDashboard = useCallback(async () => {
    if (!tenantId) { setError("No tenant ID provided"); setLoading(false); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API}/tenant/dashboard/${tenantId}`);
      if (!res.ok) { setError("Tenant not found"); setLoading(false); return; }
      const d = await res.json();
      setData(d);
      setSettingsForm({
        upi_id: d.tenant?.upi_id || d.settings?.payment_upi_id || "",
        channel_id: d.settings?.channel_id || "",
        welcome_message: d.settings?.welcome_message || "",
        website_link: d.settings?.website_link || "",
        razorpay_key_id: d.settings?.razorpay_key_id || "",
        telegram_user_id: d.tenant?.owner_telegram_id || "",
      });
    } catch (e) {
      setError("Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  const miniAppUrl = `${window.location.origin}/miniapp?tenant=${tenantId}`;

  const createPlan = async () => {
    setPlanLoading(true);
    try {
      const res = await fetch(`${API}/tenant/plans/${tenantId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...newPlan,
          features: newPlan.features.split(",").map((f) => f.trim()).filter(Boolean),
        }),
      });
      if (res.ok) {
        setShowNewPlan(false);
        setNewPlan({ name: "", price: 99, duration_days: 30, features: "" });
        fetchDashboard();
      }
    } catch (e) { console.error(e); }
    finally { setPlanLoading(false); }
  };

  const deletePlan = async (planId) => {
    try {
      await fetch(`${API}/tenant/plans/${tenantId}/${planId}`, { method: "DELETE" });
      fetchDashboard();
    } catch (e) { console.error(e); }
  };

  const saveSettings = async () => {
    setSettingsSaving(true);
    setSettingsMsg("");
    try {
      const res = await fetch(`${API}/tenant/settings/${tenantId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settingsForm),
      });
      const d = await res.json();
      if (res.ok) setSettingsMsg("Settings saved!");
      else setSettingsMsg(d.detail || "Failed to save");
    } catch (e) {
      setSettingsMsg("Connection error");
    } finally {
      setSettingsSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="cd-wrapper">
        <div className="cd-bg" />
        <div className="cd-loading"><div className="cd-spinner" /></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="cd-wrapper">
        <div className="cd-bg" />
        <div className="cd-card" style={{ textAlign: "center", padding: "60px 32px" }}>
          <h2 style={{ color: "#f87171", fontSize: "20px", marginBottom: "8px" }}>{error || "Not Found"}</h2>
          <p style={{ color: "#888", fontSize: "14px" }}>Check your tenant ID or <a href="/creator-onboard" style={{ color: "#ec4899" }}>create a new bot</a></p>
        </div>
      </div>
    );
  }

  const s = data.stats;
  const t = data.tenant;

  return (
    <div className="cd-wrapper">
      <div className="cd-bg" />

      <div className="cd-container">
        {/* Header */}
        <motion.div className="cd-header" initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="cd-header-left">
            <h1 className="cd-brand" data-testid="cd-brand">{t.name}</h1>
            <span className="cd-badge" data-testid="cd-bot-username">@{t.bot_username}</span>
          </div>
          <div className="cd-header-right">
            <button className="cd-btn-ghost cd-url-btn" onClick={() => navigator.clipboard.writeText(miniAppUrl)} data-testid="cd-copy-url" title={miniAppUrl}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              Copy Mini App URL
            </button>
          </div>
        </motion.div>

        {/* Stats Row */}
        <motion.div className="cd-stats" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} data-testid="cd-stats">
          {[
            { label: "Revenue", value: `\u20B9${s.total_revenue.toLocaleString()}`, color: "#22c55e" },
            { label: "Active Subs", value: s.active_subscribers, color: "#3b82f6" },
            { label: "Total Users", value: s.total_users, color: "#a855f7" },
            { label: "Pending", value: s.pending_payments, color: "#f59e0b" },
          ].map((st) => (
            <div key={st.label} className="cd-stat-card">
              <span className="cd-stat-val" style={{ color: st.color }}>{st.value}</span>
              <span className="cd-stat-label">{st.label}</span>
            </div>
          ))}
        </motion.div>

        {/* Tabs */}
        <div className="cd-tabs" data-testid="cd-tabs">
          {TABS.map((tab) => (
            <button key={tab.id} className={`cd-tab ${activeTab === tab.id ? "active" : ""}`} onClick={() => setActiveTab(tab.id)} data-testid={`cd-tab-${tab.id}`}>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <AnimatePresence mode="wait">
          {activeTab === "overview" && (
            <motion.div key="overview" className="cd-content" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <h3 className="cd-section-title">Recent Payments</h3>
              {data.recent_payments.length === 0 ? (
                <p className="cd-empty">No payments yet</p>
              ) : (
                <div className="cd-table">
                  {data.recent_payments.map((p) => (
                    <div key={p.id} className="cd-table-row" data-testid="cd-payment-row">
                      <div className="cd-table-left">
                        <span className={`cd-dot ${p.status}`} />
                        <div>
                          <p className="cd-table-title">{p.plan_name || "Plan"}</p>
                          <p className="cd-table-sub">{p.telegram_user_id} {p.payment_method && `\u00B7 ${p.payment_method}`}</p>
                        </div>
                      </div>
                      <span className="cd-table-amt">{`\u20B9${p.amount}`}</span>
                    </div>
                  ))}
                </div>
              )}

              <h3 className="cd-section-title" style={{ marginTop: "24px" }}>Live Sessions</h3>
              {data.live_sessions.length === 0 ? (
                <p className="cd-empty">No live sessions</p>
              ) : (
                <div className="cd-table">
                  {data.live_sessions.map((ls) => (
                    <div key={ls.id} className="cd-table-row" data-testid="cd-live-row">
                      <div className="cd-table-left">
                        <span className={`cd-dot ${ls.status}`} />
                        <div>
                          <p className="cd-table-title">{ls.title}</p>
                          <p className="cd-table-sub">{ls.scheduled_date} {ls.scheduled_time && `\u00B7 ${ls.scheduled_time}`}</p>
                        </div>
                      </div>
                      <span className="cd-table-sub">{ls.tickets_sold || 0} tickets</span>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {activeTab === "plans" && (
            <motion.div key="plans" className="cd-content" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <div className="cd-section-header">
                <h3 className="cd-section-title">Subscription Plans</h3>
                <button className="cd-btn-accent cd-btn-sm" onClick={() => setShowNewPlan(!showNewPlan)} data-testid="cd-add-plan">
                  {showNewPlan ? "Cancel" : "+ Add Plan"}
                </button>
              </div>

              <AnimatePresence>
                {showNewPlan && (
                  <motion.div className="cd-new-plan" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
                    <input className="cd-input" placeholder="Plan Name" value={newPlan.name} onChange={(e) => setNewPlan({ ...newPlan, name: e.target.value })} data-testid="cd-plan-name" />
                    <div className="cd-row">
                      <input className="cd-input" type="number" placeholder="Price" value={newPlan.price} onChange={(e) => setNewPlan({ ...newPlan, price: parseInt(e.target.value) || 0 })} data-testid="cd-plan-price" />
                      <input className="cd-input" type="number" placeholder="Days" value={newPlan.duration_days} onChange={(e) => setNewPlan({ ...newPlan, duration_days: parseInt(e.target.value) || 30 })} data-testid="cd-plan-days" />
                    </div>
                    <input className="cd-input" placeholder="Features (comma separated)" value={newPlan.features} onChange={(e) => setNewPlan({ ...newPlan, features: e.target.value })} data-testid="cd-plan-features" />
                    <button className="cd-btn-accent cd-btn-sm" disabled={planLoading || !newPlan.name.trim()} onClick={createPlan} data-testid="cd-plan-save">
                      {planLoading ? "Creating..." : "Create Plan"}
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              {data.plans.length === 0 ? (
                <p className="cd-empty">No plans yet. Create your first plan above.</p>
              ) : (
                <div className="cd-plans-grid">
                  {data.plans.map((plan) => (
                    <div key={plan.id} className="cd-plan-card" data-testid="cd-plan-card">
                      <div className="cd-plan-top">
                        <h4 className="cd-plan-name">{plan.name}</h4>
                        <span className="cd-plan-price">{`\u20B9${plan.price}`}</span>
                      </div>
                      <p className="cd-plan-dur">{plan.duration_days} days</p>
                      {plan.features?.length > 0 && (
                        <ul className="cd-plan-features">
                          {plan.features.map((f, i) => <li key={i}>{f}</li>)}
                        </ul>
                      )}
                      <button className="cd-btn-danger" onClick={() => deletePlan(plan.id)} data-testid={`cd-delete-plan-${plan.id}`}>Delete</button>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {activeTab === "settings" && (
            <motion.div key="settings" className="cd-content" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <h3 className="cd-section-title">Bot Settings</h3>
              <div className="cd-form">
                <div className="cd-field">
                  <label className="cd-label">UPI ID</label>
                  <input className="cd-input" value={settingsForm.upi_id || ""} onChange={(e) => setSettingsForm({ ...settingsForm, upi_id: e.target.value })} data-testid="cd-set-upi" />
                </div>
                <div className="cd-field">
                  <label className="cd-label">Channel ID</label>
                  <input className="cd-input" value={settingsForm.channel_id || ""} onChange={(e) => setSettingsForm({ ...settingsForm, channel_id: e.target.value })} data-testid="cd-set-channel" />
                </div>
                <div className="cd-field">
                  <label className="cd-label">Welcome Message</label>
                  <textarea className="cd-input cd-textarea" rows={3} value={settingsForm.welcome_message || ""} onChange={(e) => setSettingsForm({ ...settingsForm, welcome_message: e.target.value })} data-testid="cd-set-welcome" />
                </div>
                <div className="cd-field">
                  <label className="cd-label">Website Link</label>
                  <input className="cd-input" value={settingsForm.website_link || ""} onChange={(e) => setSettingsForm({ ...settingsForm, website_link: e.target.value })} data-testid="cd-set-website" />
                </div>
                <div className="cd-field">
                  <label className="cd-label">Razorpay Key ID</label>
                  <input className="cd-input" value={settingsForm.razorpay_key_id || ""} onChange={(e) => setSettingsForm({ ...settingsForm, razorpay_key_id: e.target.value })} data-testid="cd-set-rzp" />
                </div>
                {settingsMsg && <p className={`cd-msg ${settingsMsg.includes("saved") ? "success" : "error"}`} data-testid="cd-settings-msg">{settingsMsg}</p>}
                <button className="cd-btn-accent" disabled={settingsSaving} onClick={saveSettings} data-testid="cd-save-settings">
                  {settingsSaving ? "Saving..." : "Save Settings"}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <style>{`
        .cd-wrapper { min-height: 100vh; position: relative; background: #080810; padding: 24px; }
        .cd-bg { position: fixed; inset: 0; background: radial-gradient(ellipse at 20% 10%, rgba(168,85,247,0.08) 0%, transparent 50%), radial-gradient(ellipse at 80% 90%, rgba(236,72,153,0.06) 0%, transparent 50%); pointer-events: none; z-index: 0; }
        .cd-container { position: relative; z-index: 1; max-width: 800px; margin: 0 auto; }
        .cd-loading { display: flex; align-items: center; justify-content: center; min-height: 60vh; }
        .cd-spinner { width: 32px; height: 32px; border: 3px solid rgba(255,255,255,0.1); border-top-color: #ec4899; border-radius: 50%; animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }

        .cd-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 12px; }
        .cd-header-left { display: flex; align-items: center; gap: 12px; }
        .cd-brand { font-size: 24px; font-weight: 700; color: #f0f0f0; margin: 0; }
        .cd-badge { background: rgba(168,85,247,0.15); color: #a78bfa; padding: 4px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; }
        .cd-url-btn { display: flex; align-items: center; gap: 6px; font-size: 12px; }

        .cd-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
        .cd-stat-card { background: rgba(20,20,30,0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; padding: 16px; text-align: center; }
        .cd-stat-val { font-size: 22px; font-weight: 700; display: block; }
        .cd-stat-label { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; display: block; }

        .cd-tabs { display: flex; gap: 4px; background: rgba(255,255,255,0.04); border-radius: 12px; padding: 4px; margin-bottom: 20px; }
        .cd-tab { flex: 1; padding: 10px; border: none; background: transparent; color: #888; font-size: 13px; font-weight: 600; cursor: pointer; border-radius: 10px; transition: all 0.2s; }
        .cd-tab.active { background: rgba(236,72,153,0.15); color: #ec4899; }

        .cd-content { background: rgba(20,20,30,0.6); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; padding: 24px; }
        .cd-section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .cd-section-title { font-size: 16px; font-weight: 600; color: #e0e0e0; margin: 0 0 14px; }
        .cd-empty { color: #666; font-size: 13px; text-align: center; padding: 24px; }

        .cd-table { display: flex; flex-direction: column; gap: 6px; }
        .cd-table-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: rgba(255,255,255,0.02); border-radius: 10px; }
        .cd-table-left { display: flex; align-items: center; gap: 10px; }
        .cd-dot { width: 8px; height: 8px; border-radius: 50%; background: #666; flex-shrink: 0; }
        .cd-dot.verified, .cd-dot.approved, .cd-dot.active, .cd-dot.live { background: #22c55e; }
        .cd-dot.pending, .cd-dot.scheduled { background: #f59e0b; }
        .cd-table-title { font-size: 13px; color: #e0e0e0; margin: 0; font-weight: 500; }
        .cd-table-sub { font-size: 11px; color: #888; margin: 0; }
        .cd-table-amt { font-size: 14px; font-weight: 600; color: #22c55e; }

        .cd-form { display: flex; flex-direction: column; gap: 14px; }
        .cd-field { display: flex; flex-direction: column; gap: 5px; }
        .cd-label { font-size: 12px; font-weight: 600; color: #aaa; }
        .cd-input { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 10px 14px; color: #e0e0e0; font-size: 13px; outline: none; }
        .cd-input:focus { border-color: rgba(236,72,153,0.5); }
        .cd-textarea { resize: vertical; font-family: inherit; }
        .cd-msg { font-size: 12px; padding: 8px 12px; border-radius: 8px; }
        .cd-msg.success { background: rgba(34,197,94,0.1); color: #4ade80; }
        .cd-msg.error { background: rgba(239,68,68,0.1); color: #f87171; }

        .cd-btn-accent { background: linear-gradient(135deg, #ec4899, #a855f7); color: #fff; border: none; padding: 10px 22px; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer; }
        .cd-btn-accent:disabled { opacity: 0.4; cursor: not-allowed; }
        .cd-btn-sm { padding: 7px 16px; font-size: 12px; }
        .cd-btn-ghost { background: rgba(255,255,255,0.06); color: #ccc; border: 1px solid rgba(255,255,255,0.1); padding: 8px 16px; border-radius: 10px; font-size: 12px; cursor: pointer; }
        .cd-btn-danger { background: rgba(239,68,68,0.1); color: #f87171; border: 1px solid rgba(239,68,68,0.2); padding: 6px 14px; border-radius: 8px; font-size: 11px; cursor: pointer; margin-top: 8px; }

        .cd-new-plan { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; overflow: hidden; }
        .cd-row { display: flex; gap: 10px; }
        .cd-row .cd-input { flex: 1; }

        .cd-plans-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
        .cd-plan-card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 16px; }
        .cd-plan-top { display: flex; justify-content: space-between; align-items: center; }
        .cd-plan-name { font-size: 15px; font-weight: 600; color: #e0e0e0; margin: 0; }
        .cd-plan-price { font-size: 18px; font-weight: 700; color: #22c55e; }
        .cd-plan-dur { font-size: 12px; color: #888; margin: 4px 0 8px; }
        .cd-plan-features { padding-left: 16px; margin: 0; }
        .cd-plan-features li { font-size: 12px; color: #aaa; margin-bottom: 3px; }

        @media (max-width: 640px) {
          .cd-stats { grid-template-columns: repeat(2, 1fr); }
          .cd-plans-grid { grid-template-columns: 1fr; }
        }
      `}</style>
    </div>
  );
}
