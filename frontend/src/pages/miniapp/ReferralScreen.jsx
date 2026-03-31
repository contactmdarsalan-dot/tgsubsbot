import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useMiniApp, API, copyToClipboard } from "./context";
import { Gift, Copy, Share2, Users, IndianRupee, Check } from "lucide-react";

export default function ReferralScreen() {
  const { userId } = useMiniApp();
  const [data, setData] = useState(null);
  const [applyCode, setApplyCode] = useState("");
  const [applyMsg, setApplyMsg] = useState("");

  useEffect(() => {
    if (!userId) return;
    fetch(`${API}/miniapp/referral/${userId}`).then(r => r.json()).then(setData).catch(() => {});
  }, [userId]);

  const applyReferral = async () => {
    if (!applyCode.trim()) return;
    try {
      const res = await fetch(`${API}/miniapp/referral/apply`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: applyCode, telegram_user_id: userId }),
      });
      const d = await res.json();
      setApplyMsg(d.valid ? d.message : d.error);
    } catch { setApplyMsg("Network error"); }
  };

  return (
    <div className="pb-24">
      <div className="text-center mb-6">
        <h2 className="font-heading text-2xl font-bold text-white mb-1">Refer & Earn</h2>
        <p className="text-sm text-zinc-500">Share and get rewards</p>
      </div>

      {/* Your Code */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass-card rounded-2xl p-5 mb-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center"><Gift className="w-5 h-5 text-purple-400" /></div>
          <div>
            <h3 className="text-sm font-semibold text-white">Your Referral Code</h3>
            <p className="text-xs text-zinc-500">Share to earn rewards</p>
          </div>
        </div>
        {data?.referral_code ? (
          <>
            <div className="flex items-center gap-2 mb-4">
              <div className="flex-1 font-mono text-lg font-bold text-center py-3 bg-white/5 rounded-xl text-rose-400 tracking-wider">{data.referral_code}</div>
              <button onClick={() => copyToClipboard(data.referral_code)} className="w-12 h-12 bg-white/10 rounded-xl flex items-center justify-center hover:bg-white/20 transition-all active:scale-90" data-testid="copy-referral-btn">
                <Copy className="w-5 h-5 text-white" />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white/5 rounded-xl p-3 text-center">
                <Users className="w-5 h-5 text-rose-400 mx-auto mb-1" />
                <p className="font-mono text-xl font-bold text-white">{data.referred_count || 0}</p>
                <p className="text-[10px] text-zinc-500">Referred</p>
              </div>
              <div className="bg-white/5 rounded-xl p-3 text-center">
                <IndianRupee className="w-5 h-5 text-emerald-400 mx-auto mb-1" />
                <p className="font-mono text-xl font-bold text-white">Rs.{data.total_earnings || 0}</p>
                <p className="text-[10px] text-zinc-500">Earned</p>
              </div>
            </div>
          </>
        ) : (
          <div className="py-6 text-center text-zinc-500 text-sm">Loading...</div>
        )}
      </motion.div>

      {/* Rewards info */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card rounded-2xl p-4 mb-4">
        <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-500 mb-3">Rewards</h4>
        <div className="space-y-2">
          <div className="flex items-center gap-3 text-sm"><Check className="w-4 h-4 text-emerald-400" /><span className="text-zinc-300">You get: <span className="text-white font-semibold">{data?.referrer_reward || "10% off"}</span></span></div>
          <div className="flex items-center gap-3 text-sm"><Check className="w-4 h-4 text-emerald-400" /><span className="text-zinc-300">Friend gets: <span className="text-white font-semibold">{data?.referee_reward || "10% off"}</span></span></div>
        </div>
      </motion.div>

      {/* Apply referral code */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="glass-card rounded-2xl p-4">
        <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-500 mb-3">Have a referral code?</h4>
        <div className="flex gap-2">
          <input value={applyCode} onChange={e => setApplyCode(e.target.value.toUpperCase())} placeholder="Enter code" className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-rose-500/50" data-testid="apply-referral-input" />
          <button onClick={applyReferral} className="px-5 py-2.5 bg-white/10 text-white text-sm font-semibold rounded-xl hover:bg-white/20 transition-all" data-testid="apply-referral-btn">Apply</button>
        </div>
        {applyMsg && <p className="text-xs text-rose-400 mt-2">{applyMsg}</p>}
      </motion.div>
    </div>
  );
}
