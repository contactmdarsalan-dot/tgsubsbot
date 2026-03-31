import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const STEPS = [
  { id: "info", label: "Your Info", icon: "1" },
  { id: "bot", label: "Bot Setup", icon: "2" },
  { id: "payment", label: "Payments", icon: "3" },
  { id: "done", label: "Done", icon: "4" },
];

export default function CreatorOnboard() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [botValid, setBotValid] = useState(null);
  const [result, setResult] = useState(null);

  const [form, setForm] = useState({
    name: "",
    email: "",
    bot_token: "",
    telegram_user_id: "",
    upi_id: "",
    channel_id: "",
    razorpay_key_id: "",
    razorpay_key_secret: "",
  });

  const set = (key, val) => setForm((p) => ({ ...p, [key]: val }));

  const validateBot = async () => {
    if (!form.bot_token.trim()) return;
    setLoading(true);
    setError("");
    setBotValid(null);
    try {
      const res = await fetch(`${API}/tenant/validate-bot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bot_token: form.bot_token.trim() }),
      });
      const data = await res.json();
      setBotValid(data);
      if (!data.valid) setError(data.error || "Invalid bot token");
    } catch (e) {
      setError("Failed to validate bot token");
    } finally {
      setLoading(false);
    }
  };

  const submitOnboard = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/tenant/onboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Onboarding failed");
        return;
      }
      setResult(data);
      setStep(3);
    } catch (e) {
      setError("Connection failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const canNext = () => {
    if (step === 0) return form.name.trim() && form.telegram_user_id.trim();
    if (step === 1) return form.bot_token.trim() && botValid?.valid;
    if (step === 2) return form.upi_id.trim();
    return false;
  };

  const next = () => {
    if (step === 2) {
      submitOnboard();
    } else {
      setStep((s) => Math.min(s + 1, 3));
      setError("");
    }
  };

  const prev = () => {
    setStep((s) => Math.max(s - 1, 0));
    setError("");
  };

  const fullUrl = result
    ? `${window.location.origin}${result.miniapp_url}`
    : "";

  return (
    <div className="co-wrapper">
      <div className="co-bg" />

      <motion.div
        className="co-card"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Header */}
        <div className="co-header">
          <h1 className="co-title" data-testid="onboard-title">Launch Your Bot</h1>
          <p className="co-subtitle">Set up your Telegram subscription bot in minutes</p>
        </div>

        {/* Step Indicator */}
        <div className="co-steps" data-testid="onboard-steps">
          {STEPS.map((s, i) => (
            <div key={s.id} className={`co-step ${i <= step ? "active" : ""} ${i < step ? "done" : ""}`}>
              <div className="co-step-dot">{i < step ? "\u2713" : s.icon}</div>
              <span className="co-step-label">{s.label}</span>
              {i < STEPS.length - 1 && <div className="co-step-line" />}
            </div>
          ))}
        </div>

        {/* Error */}
        <AnimatePresence>
          {error && (
            <motion.div className="co-error" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} data-testid="onboard-error">
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Step Content */}
        <AnimatePresence mode="wait">
          {step === 0 && (
            <motion.div key="info" className="co-form" initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -40 }}>
              <div className="co-field">
                <label className="co-label">Creator / Brand Name *</label>
                <input className="co-input" placeholder="e.g. MiracleCouple" value={form.name} onChange={(e) => set("name", e.target.value)} data-testid="onboard-name" />
              </div>
              <div className="co-field">
                <label className="co-label">Email (optional)</label>
                <input className="co-input" type="email" placeholder="you@example.com" value={form.email} onChange={(e) => set("email", e.target.value)} data-testid="onboard-email" />
              </div>
              <div className="co-field">
                <label className="co-label">Your Telegram User ID *</label>
                <input className="co-input" placeholder="e.g. 123456789" value={form.telegram_user_id} onChange={(e) => set("telegram_user_id", e.target.value)} data-testid="onboard-tg-id" />
                <p className="co-hint">Send /myid to @userinfobot on Telegram to get your ID</p>
              </div>
            </motion.div>
          )}

          {step === 1 && (
            <motion.div key="bot" className="co-form" initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -40 }}>
              <div className="co-field">
                <label className="co-label">Telegram Bot Token *</label>
                <input className="co-input" placeholder="123456:ABC-DEF..." value={form.bot_token} onChange={(e) => { set("bot_token", e.target.value); setBotValid(null); }} data-testid="onboard-bot-token" />
                <p className="co-hint">Get this from @BotFather on Telegram</p>
                <button className="co-btn-ghost" onClick={validateBot} disabled={loading || !form.bot_token.trim()} data-testid="onboard-validate-bot">
                  {loading ? "Validating..." : "Validate Token"}
                </button>
                {botValid?.valid && (
                  <div className="co-success" data-testid="onboard-bot-valid">
                    Bot verified: <strong>@{botValid.bot_username}</strong> ({botValid.bot_name})
                  </div>
                )}
              </div>
              <div className="co-field">
                <label className="co-label">Channel ID (optional)</label>
                <input className="co-input" placeholder="e.g. -1001234567890" value={form.channel_id} onChange={(e) => set("channel_id", e.target.value)} data-testid="onboard-channel" />
                <p className="co-hint">The private channel users get access to after subscribing</p>
              </div>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div key="payment" className="co-form" initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -40 }}>
              <div className="co-field">
                <label className="co-label">UPI ID *</label>
                <input className="co-input" placeholder="yourname@paytm" value={form.upi_id} onChange={(e) => set("upi_id", e.target.value)} data-testid="onboard-upi" />
                <p className="co-hint">Users will send payments to this UPI address</p>
              </div>
              <div className="co-divider">
                <span>Razorpay (Optional)</span>
              </div>
              <div className="co-field">
                <label className="co-label">Razorpay Key ID</label>
                <input className="co-input" placeholder="rzp_live_..." value={form.razorpay_key_id} onChange={(e) => set("razorpay_key_id", e.target.value)} data-testid="onboard-rzp-key" />
              </div>
              <div className="co-field">
                <label className="co-label">Razorpay Key Secret</label>
                <input className="co-input" type="password" placeholder="Secret key" value={form.razorpay_key_secret} onChange={(e) => set("razorpay_key_secret", e.target.value)} data-testid="onboard-rzp-secret" />
                <p className="co-hint">Enable instant payment collection via Razorpay</p>
              </div>
            </motion.div>
          )}

          {step === 3 && result && (
            <motion.div key="done" className="co-form co-done" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}>
              <div className="co-done-icon" data-testid="onboard-success">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
              </div>
              <h2 className="co-done-title">You're All Set!</h2>
              <p className="co-done-sub">Your bot <strong>@{result.bot_username}</strong> is now ready</p>

              <div className="co-result-card" data-testid="onboard-result">
                <label className="co-label">Your Mini App URL</label>
                <div className="co-url-row">
                  <input className="co-input co-url" readOnly value={fullUrl} data-testid="onboard-miniapp-url" />
                  <button className="co-btn-copy" onClick={() => { navigator.clipboard.writeText(fullUrl); }} data-testid="onboard-copy-url">
                    Copy
                  </button>
                </div>
                <p className="co-hint">Share this link with your users or set it as your bot's WebApp URL</p>
              </div>

              <div className="co-result-card">
                <label className="co-label">Tenant ID</label>
                <code className="co-code" data-testid="onboard-tenant-id">{result.tenant_id}</code>
              </div>

              <div className="co-btn-row">
                <button className="co-btn-accent" onClick={() => navigate(`/creator-dashboard?tenant=${result.tenant_id}`)} data-testid="onboard-go-dashboard">
                  Open Dashboard
                </button>
                <button className="co-btn-ghost" onClick={() => window.open(fullUrl, "_blank")} data-testid="onboard-preview-miniapp">
                  Preview Mini App
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Navigation */}
        {step < 3 && (
          <div className="co-nav">
            {step > 0 && (
              <button className="co-btn-ghost" onClick={prev} data-testid="onboard-back">Back</button>
            )}
            <button className="co-btn-accent" disabled={!canNext() || loading} onClick={next} data-testid="onboard-next">
              {loading ? "Setting up..." : step === 2 ? "Launch My Bot" : "Continue"}
            </button>
          </div>
        )}
      </motion.div>

      <style>{`
        .co-wrapper { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; position: relative; overflow: hidden; background: #080810; }
        .co-bg { position: absolute; inset: 0; background: radial-gradient(ellipse at 30% 20%, rgba(168,85,247,0.12) 0%, transparent 50%), radial-gradient(ellipse at 70% 80%, rgba(236,72,153,0.1) 0%, transparent 50%); pointer-events: none; }
        .co-card { position: relative; width: 100%; max-width: 520px; background: rgba(20,20,30,0.85); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; padding: 36px 32px; }
        .co-header { text-align: center; margin-bottom: 28px; }
        .co-title { font-size: 28px; font-weight: 700; color: #f0f0f0; margin: 0 0 6px; letter-spacing: -0.5px; }
        .co-subtitle { font-size: 14px; color: #888; margin: 0; }

        .co-steps { display: flex; align-items: center; justify-content: center; gap: 0; margin-bottom: 24px; }
        .co-step { display: flex; align-items: center; gap: 6px; }
        .co-step-dot { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; background: rgba(255,255,255,0.06); color: #666; border: 1px solid rgba(255,255,255,0.1); transition: all 0.3s; }
        .co-step.active .co-step-dot { background: rgba(236,72,153,0.2); color: #ec4899; border-color: rgba(236,72,153,0.4); }
        .co-step.done .co-step-dot { background: rgba(34,197,94,0.2); color: #22c55e; border-color: rgba(34,197,94,0.4); }
        .co-step-label { font-size: 11px; color: #666; display: none; }
        .co-step-line { width: 32px; height: 1px; background: rgba(255,255,255,0.1); margin: 0 4px; }

        .co-form { display: flex; flex-direction: column; gap: 18px; }
        .co-field { display: flex; flex-direction: column; gap: 6px; }
        .co-label { font-size: 13px; font-weight: 600; color: #ccc; }
        .co-input { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 12px 14px; color: #e0e0e0; font-size: 14px; outline: none; transition: border-color 0.2s; }
        .co-input:focus { border-color: rgba(236,72,153,0.5); }
        .co-input::placeholder { color: #555; }
        .co-hint { font-size: 11px; color: #666; margin: 0; }

        .co-error { background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.3); border-radius: 10px; padding: 10px 14px; color: #f87171; font-size: 13px; margin-bottom: 8px; }
        .co-success { background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.3); border-radius: 10px; padding: 10px 14px; color: #4ade80; font-size: 13px; margin-top: 6px; }

        .co-divider { display: flex; align-items: center; gap: 12px; margin: 4px 0; }
        .co-divider::before, .co-divider::after { content: ''; flex: 1; height: 1px; background: rgba(255,255,255,0.08); }
        .co-divider span { font-size: 12px; color: #666; white-space: nowrap; }

        .co-nav { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
        .co-btn-accent { background: linear-gradient(135deg, #ec4899, #a855f7); color: #fff; border: none; padding: 12px 28px; border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer; transition: opacity 0.2s; }
        .co-btn-accent:hover { opacity: 0.9; }
        .co-btn-accent:disabled { opacity: 0.4; cursor: not-allowed; }
        .co-btn-ghost { background: rgba(255,255,255,0.06); color: #ccc; border: 1px solid rgba(255,255,255,0.1); padding: 10px 20px; border-radius: 10px; font-size: 13px; cursor: pointer; transition: background 0.2s; }
        .co-btn-ghost:hover { background: rgba(255,255,255,0.1); }
        .co-btn-ghost:disabled { opacity: 0.4; cursor: not-allowed; }

        .co-done { align-items: center; text-align: center; }
        .co-done-icon { margin-bottom: 12px; }
        .co-done-title { font-size: 22px; font-weight: 700; color: #f0f0f0; margin: 0 0 6px; }
        .co-done-sub { font-size: 14px; color: #999; margin: 0 0 20px; }

        .co-result-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 14px 16px; width: 100%; text-align: left; margin-bottom: 12px; }
        .co-url-row { display: flex; gap: 8px; }
        .co-url { flex: 1; font-size: 12px; }
        .co-btn-copy { background: rgba(236,72,153,0.15); color: #ec4899; border: 1px solid rgba(236,72,153,0.3); padding: 10px 16px; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; }
        .co-code { display: block; background: rgba(0,0,0,0.3); padding: 8px 12px; border-radius: 8px; font-size: 13px; color: #a78bfa; word-break: break-all; }
        .co-btn-row { display: flex; gap: 10px; margin-top: 8px; width: 100%; }
        .co-btn-row .co-btn-accent, .co-btn-row .co-btn-ghost { flex: 1; text-align: center; }

        @media (max-width: 540px) {
          .co-card { padding: 24px 18px; }
          .co-step-line { width: 16px; }
        }
      `}</style>
    </div>
  );
}
