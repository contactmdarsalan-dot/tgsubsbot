import { motion } from "framer-motion";
import { useMiniApp } from "./context";
import { Check, Clock, AlertTriangle, ArrowUpRight, Shield } from "lucide-react";

export default function StatusScreen() {
  const { subscription, setActiveTab } = useMiniApp();

  if (!subscription?.is_active) {
    return (
      <div className="pb-24">
        <div className="flex flex-col items-center justify-center min-h-[50vh] text-center px-4">
          <div className="w-16 h-16 rounded-full bg-zinc-800 flex items-center justify-center mb-4">
            <Shield className="w-8 h-8 text-zinc-600" />
          </div>
          <h3 className="font-heading text-xl font-bold text-white mb-2">No Active Subscription</h3>
          <p className="text-zinc-500 text-sm mb-6">Get access to exclusive content</p>
          <button onClick={() => setActiveTab("plans")} className="gradient-cta text-white font-bold rounded-2xl px-8 py-3 active:scale-95 transition-transform" data-testid="subscribe-now-btn">
            Subscribe Now
          </button>
        </div>
      </div>
    );
  }

  const daysLeft = subscription.days_remaining || 0;
  const total = subscription.total_days || 30;
  const progress = Math.max(0, Math.min(100, ((total - daysLeft) / total) * 100));
  const isExpiring = daysLeft <= 3;

  return (
    <div className="pb-24">
      <div className="text-center mb-6">
        <h2 className="font-heading text-2xl font-bold text-white mb-1">Your Subscription</h2>
        <p className="text-sm text-zinc-500">Manage your plan</p>
      </div>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass-card rounded-2xl p-5 mb-4">
        <div className="flex items-center gap-3 mb-4">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${isExpiring ? "bg-amber-500/20" : "bg-emerald-500/20"}`}>
            {isExpiring ? <AlertTriangle className="w-6 h-6 text-amber-400" /> : <Check className="w-6 h-6 text-emerald-400" />}
          </div>
          <div>
            <h3 className="font-heading text-lg font-bold text-white">{subscription.plan_name}</h3>
            <p className={`text-xs font-semibold ${isExpiring ? "text-amber-400" : "text-emerald-400"}`}>
              {isExpiring ? "Expiring Soon" : "Active"}
            </p>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mb-4">
          <div className="flex justify-between text-xs text-zinc-500 mb-1.5">
            <span>Progress</span>
            <span>{daysLeft} days left</span>
          </div>
          <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 1, ease: "easeOut" }}
              className={`h-full rounded-full ${isExpiring ? "bg-gradient-to-r from-amber-500 to-rose-500" : "bg-gradient-to-r from-indigo-500 to-purple-500"}`}
            />
          </div>
        </div>

        <div className="space-y-2.5">
          <div className="flex justify-between text-sm">
            <span className="text-zinc-500">Started</span>
            <span className="text-white font-medium">{subscription.start_date ? new Date(subscription.start_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "N/A"}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-zinc-500">Expires</span>
            <span className={`font-medium ${isExpiring ? "text-amber-400" : "text-white"}`}>{subscription.end_date ? new Date(subscription.end_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "N/A"}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-zinc-500">Duration</span>
            <span className="text-white font-medium">{total} days</span>
          </div>
        </div>
      </motion.div>

      {isExpiring && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card rounded-2xl p-4 border-amber-500/20 mb-4">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-amber-400" />
            <span className="text-sm font-semibold text-amber-400">Renew before it expires!</span>
          </div>
          <p className="text-xs text-zinc-500 mb-3">Don't lose access to exclusive content</p>
          <button onClick={() => setActiveTab("plans")} className="gradient-cta text-white font-bold rounded-2xl py-3 w-full active:scale-95 transition-transform flex items-center justify-center gap-2" data-testid="renew-btn">
            Renew Now <ArrowUpRight className="w-4 h-4" />
          </button>
        </motion.div>
      )}
    </div>
  );
}
