import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useMiniApp, API } from "./context";
import { BarChart3, CreditCard, Users, IndianRupee, Check, X, Send, Loader2, Radio, Plus, Lock, Sparkles } from "lucide-react";

export default function AdminPanel() {
  const { userId, adminPerms, adminName } = useMiniApp();
  const [activeSection, setActiveSection] = useState("stats");
  const [stats, setStats] = useState(null);
  const [pendingPayments, setPendingPayments] = useState([]);
  const [subs, setSubs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [broadcastMsg, setBroadcastMsg] = useState("");
  const [broadcastSending, setBroadcastSending] = useState(false);

  useEffect(() => { fetchData(); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, paymentsRes, subsRes] = await Promise.all([
        fetch(`${API}/miniapp/admin/stats/${userId}`),
        adminPerms.includes("verify_payments") ? fetch(`${API}/miniapp/admin/pending-payments/${userId}`) : null,
        fetch(`${API}/miniapp/admin/subscribers/${userId}`),
      ]);
      setStats(await statsRes.json());
      if (paymentsRes) setPendingPayments(await paymentsRes.json());
      setSubs(await subsRes.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleAction = async (paymentId, action) => {
    try {
      const res = await fetch(`${API}/miniapp/admin/payment-action`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId, payment_id: paymentId, action }),
      });
      const data = await res.json();
      if (data.success) {
        setPendingPayments(prev => prev.filter(p => p.id !== paymentId));
        setStats(prev => prev ? { ...prev, pending_payments: prev.pending_payments - 1 } : prev);
      }
    } catch (e) { console.error(e); }
  };

  const sendBroadcast = async () => {
    if (!broadcastMsg.trim() || broadcastSending) return;
    setBroadcastSending(true);
    try {
      const res = await fetch(`${API}/miniapp/admin/broadcast`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId, message: broadcastMsg }),
      });
      const data = await res.json();
      if (data.success) { setBroadcastMsg(""); alert(`Sent to ${data.total_recipients} users!`); }
    } catch (e) { console.error(e); }
    finally { setBroadcastSending(false); }
  };

  const sections = [
    { id: "stats", label: "Stats", icon: BarChart3 },
    ...(adminPerms.includes("verify_payments") ? [{ id: "payments", label: "Payments", icon: CreditCard, badge: pendingPayments.length }] : []),
    { id: "subs", label: "Subs", icon: Users },
    ...(adminPerms.includes("broadcast") ? [{ id: "broadcast", label: "Broadcast", icon: Send }] : []),
  ];

  return (
    <div className="pb-24">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl bg-rose-500/20 flex items-center justify-center"><Sparkles className="w-5 h-5 text-rose-400" /></div>
        <div>
          <h2 className="font-heading text-xl font-bold text-white">Admin Panel</h2>
          <p className="text-xs text-zinc-500">{adminName}</p>
        </div>
      </div>

      {/* Section Tabs */}
      <div className="flex gap-1.5 mb-5 overflow-x-auto pb-1">
        {sections.map(s => {
          const Icon = s.icon;
          return (
            <button key={s.id} onClick={() => setActiveSection(s.id)} className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${activeSection === s.id ? "bg-rose-500/20 text-rose-400 border border-rose-500/30" : "bg-white/5 text-zinc-500 border border-transparent"}`} data-testid={`admin-tab-${s.id}`}>
              <Icon className="w-3.5 h-3.5" />{s.label}
              {s.badge > 0 && <span className="px-1.5 py-0.5 text-[10px] bg-rose-500 text-white rounded-full">{s.badge}</span>}
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="space-y-3">{[...Array(3)].map((_, i) => <div key={i} className="skeleton h-20" />)}</div>
      ) : (
        <>
          {activeSection === "stats" && stats && (
            <div className="grid grid-cols-2 gap-3">
              <div className="metric-card"><p className="text-xs text-zinc-500 mb-1">Active Subs</p><p className="font-mono text-2xl font-bold text-white">{stats.active_subscribers}</p></div>
              <div className="metric-card"><p className="text-xs text-zinc-500 mb-1">Total Revenue</p><p className="font-mono text-2xl font-bold text-white">Rs.{stats.total_revenue?.toLocaleString()}</p></div>
              <div className="metric-card"><p className="text-xs text-zinc-500 mb-1">Pending</p><p className="font-mono text-2xl font-bold text-amber-400">{stats.pending_payments}</p></div>
              <div className="metric-card"><p className="text-xs text-zinc-500 mb-1">Total Subs</p><p className="font-mono text-2xl font-bold text-white">{stats.total_subscribers}</p></div>
            </div>
          )}

          {activeSection === "payments" && (
            <div className="space-y-3">
              {pendingPayments.length === 0 ? (
                <div className="glass-card rounded-2xl p-6 text-center text-zinc-500 text-sm">No pending payments</div>
              ) : pendingPayments.map(p => (
                <motion.div key={p.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="glass-card rounded-2xl p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="text-sm font-semibold text-white">{p.telegram_username || p.telegram_user_id}</p>
                      <p className="text-xs text-zinc-500">{p.plan_name} - Rs.{p.amount}</p>
                    </div>
                    {p.ai_verification?.confidence_score && (
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${p.ai_verification.confidence_score >= 80 ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"}`}>
                        AI: {p.ai_verification.confidence_score}%
                      </span>
                    )}
                  </div>
                  {p.screenshot_url && (
                    <img src={p.screenshot_url.startsWith("http") ? p.screenshot_url : `${process.env.REACT_APP_BACKEND_URL}${p.screenshot_url}`} alt="Screenshot" className="w-full h-32 object-cover rounded-xl mb-3 border border-white/10" />
                  )}
                  <div className="flex gap-2">
                    <button onClick={() => handleAction(p.id, "approve")} className="flex-1 py-2.5 bg-emerald-500/20 text-emerald-400 font-semibold rounded-xl text-sm flex items-center justify-center gap-1 hover:bg-emerald-500/30 transition-all active:scale-95" data-testid={`approve-${p.id}`}>
                      <Check className="w-4 h-4" /> Approve
                    </button>
                    <button onClick={() => handleAction(p.id, "reject")} className="flex-1 py-2.5 bg-rose-500/20 text-rose-400 font-semibold rounded-xl text-sm flex items-center justify-center gap-1 hover:bg-rose-500/30 transition-all active:scale-95" data-testid={`reject-${p.id}`}>
                      <X className="w-4 h-4" /> Reject
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          )}

          {activeSection === "subs" && (
            <div className="space-y-2">
              {subs.length === 0 ? (
                <div className="glass-card rounded-2xl p-6 text-center text-zinc-500 text-sm">No subscribers</div>
              ) : subs.slice(0, 30).map(s => (
                <div key={s.id} className="glass-card rounded-xl p-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-white">{s.telegram_username || s.telegram_user_id}</p>
                    <p className="text-xs text-zinc-500">{s.plan_name}</p>
                  </div>
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${s.status === "active" ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-500/15 text-zinc-400"}`}>{s.status}</span>
                </div>
              ))}
            </div>
          )}

          {activeSection === "broadcast" && (
            <div className="glass-card rounded-2xl p-5">
              <h3 className="font-heading text-base font-bold text-white mb-3">Send Broadcast</h3>
              <textarea value={broadcastMsg} onChange={e => setBroadcastMsg(e.target.value)} placeholder="Type your message..." rows={4} className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 resize-none focus:outline-none focus:border-rose-500/50 mb-3" data-testid="broadcast-input" />
              <button onClick={sendBroadcast} disabled={broadcastSending || !broadcastMsg.trim()} className="gradient-cta text-white font-bold rounded-2xl py-3 w-full flex items-center justify-center gap-2 disabled:opacity-30 active:scale-95 transition-transform" data-testid="send-broadcast-btn">
                {broadcastSending ? <><Loader2 className="w-4 h-4 animate-spin" /> Sending...</> : <><Send className="w-4 h-4" /> Send to All Users</>}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
