import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { Check, Crown, Zap, Star, Loader2, LogOut, Send, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });

const ICONS = [Zap, Star, Crown, Send];

export default function Pricing({ onSubscribed }) {
  const [loading, setLoading] = useState(null);
  const [razorpayLoaded, setRazorpayLoaded] = useState(false);
  const [plans, setPlans] = useState([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => setRazorpayLoaded(true);
    document.body.appendChild(script);
    return () => { try { document.body.removeChild(script); } catch {} };
  }, []);

  useEffect(() => {
    axios.get(`${API}/public/subscription-plans`)
      .then(res => setPlans(res.data || []))
      .catch(() => setPlans([]))
      .finally(() => setPlansLoading(false));
  }, []);

  const handleSelectPlan = async (plan) => {
    const isFree = !plan.price || plan.price === 0;
    setLoading(plan.id);

    if (isFree) {
      try {
        const res = await axios.post(`${API}/dashboard-subscription/activate-free`, {}, getAuth());
        toast.success(res.data.message || "Free trial activated!");
        const updatedUser = { ...user, dashboard_subscription_status: "active", dashboard_plan: plan.name, is_trial: true };
        localStorage.setItem("user", JSON.stringify(updatedUser));
        if (onSubscribed) onSubscribed();
        navigate("/");
        window.location.reload();
      } catch (e) {
        toast.error(e.response?.data?.detail || "Failed to activate free trial");
      } finally {
        setLoading(null);
      }
      return;
    }

    // Paid plan — Razorpay
    if (!razorpayLoaded) {
      toast.error("Payment gateway loading... Please try again.");
      setLoading(null);
      return;
    }

    try {
      const response = await axios.post(`${API}/dashboard-subscription/create-order`, { plan_id: plan.id }, getAuth());
      const { order_id, amount, key_id } = response.data;

      const options = {
        key: key_id,
        amount: amount * 100,
        currency: "INR",
        name: "SubsBot Pro",
        description: `${plan.name} Subscription`,
        order_id,
        handler: async function (resp) {
          try {
            await axios.post(`${API}/dashboard-subscription/verify-payment`, {
              razorpay_order_id: resp.razorpay_order_id,
              razorpay_payment_id: resp.razorpay_payment_id,
              razorpay_signature: resp.razorpay_signature,
            }, getAuth());
            toast.success("Payment successful! Subscription activated.");
            const updatedUser = { ...user, dashboard_subscription_status: "active", dashboard_plan: plan.id };
            localStorage.setItem("user", JSON.stringify(updatedUser));
            if (onSubscribed) onSubscribed();
            navigate("/");
            window.location.reload();
          } catch {
            toast.error("Payment verification failed. Contact support.");
          }
        },
        prefill: { name: user.name || "", email: user.email || "" },
        theme: { color: "#BFFF00" },
        modal: { ondismiss: () => setLoading(null) },
      };
      new window.Razorpay(options).open();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to initiate payment");
    } finally {
      setLoading(null);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("isFirstUser");
    navigate("/login");
    toast.success("Logged out successfully");
  };

  const durationLabel = (days) => {
    if (!days) return "";
    if (days >= 365) return `${Math.floor(days / 365)} yr`;
    if (days >= 30) return `${Math.floor(days / 30)} mo`;
    return `${days} days`;
  };

  // Find highest priced plan for "savings" calculation
  const maxMonthlyRate = Math.max(...plans.filter(p => p.price > 0).map(p => (p.price / (p.duration_days || 30)) * 30), 1);

  return (
    <div className="min-h-screen text-white" style={{ background: "hsl(0, 0%, 2%)", fontFamily: "Manrope, sans-serif" }}>
      {/* Nav */}
      <nav className="sticky top-0 z-50 border-b border-white/6" style={{ background: "hsla(0,0%,3%,0.95)", backdropFilter: "blur(20px)" }}>
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#BFFF00] flex items-center justify-center shadow-[0_0_20px_rgba(191,255,0,0.4)]">
              <Send className="w-5 h-5 text-white" />
            </div>
            <div>
              <span style={{ fontFamily: "Unbounded" }} className="text-lg font-bold">TGSubsBot</span>
              <p className="text-[10px] text-zinc-500">Telegram Subscription Manager</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {user.email && <span className="text-sm text-zinc-500 hidden sm:block">{user.email}</span>}
            <button onClick={handleLogout} className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-zinc-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg border border-white/6 transition-all" data-testid="logout-btn">
              <LogOut className="w-3.5 h-3.5" /> Logout
            </button>
          </div>
        </div>
      </nav>

      <div className="py-16 px-6">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <motion.div initial={{ opacity: 0, y: -15 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-14">
            <Badge className="mb-4 bg-[#BFFF00]/10 text-[#BFFF00] border-[#BFFF00]/20 px-3 py-1 text-xs font-bold" data-testid="pricing-badge">SubsBot Pro</Badge>
            <h1 style={{ fontFamily: "Unbounded" }} className="text-4xl md:text-5xl font-black tracking-tight mb-4">
              Choose Your <span className="bg-gradient-to-r from-[#BFFF00] to-[#BEF264] bg-clip-text text-transparent">Plan</span>
            </h1>
            <p className="text-base text-zinc-500 max-w-lg mx-auto">
              Get full access to SubsBot Dashboard and start managing your Telegram subscriptions like a pro
            </p>
          </motion.div>

          {/* Plans */}
          {plansLoading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 text-[#BFFF00] animate-spin" />
            </div>
          ) : plans.length === 0 ? (
            <div className="text-center py-20 text-zinc-500">No plans available. Contact admin.</div>
          ) : (
            <div className={`grid gap-6 items-end ${plans.length === 1 ? "max-w-md mx-auto" : plans.length === 2 ? "md:grid-cols-2 max-w-3xl mx-auto" : plans.length >= 3 ? "md:grid-cols-3 max-w-5xl mx-auto" : ""}`}>
              {plans.map((plan, i) => {
                const Icon = ICONS[i % ICONS.length];
                const isFree = !plan.price || plan.price === 0;
                const isPopular = plan.is_popular || false;
                const isLoading = loading === plan.id;
                const monthlyRate = plan.price > 0 ? (plan.price / (plan.duration_days || 30)) * 30 : 0;
                const savePct = !isFree && plan.duration_days > 30 && monthlyRate < maxMonthlyRate ? Math.round((1 - monthlyRate / maxMonthlyRate) * 100) : 0;

                return (
                  <motion.div
                    key={plan.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className={`relative rounded-2xl border transition-all duration-300 ${isPopular ? "border-[#BFFF00] shadow-[0_0_40px_rgba(191,255,0,0.15)] scale-[1.03]" : "border-white/10 hover:border-white/20"}`}
                    style={{ background: "hsl(0, 0%, 4%)" }}
                    data-testid={`plan-card-${plan.id}`}
                  >
                    {/* Badges */}
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 flex gap-2">
                      {isPopular && <span className="bg-[#BFFF00] text-white text-[10px] font-bold px-3 py-1 rounded-full shadow-lg">Most Popular</span>}
                      {savePct > 0 && <span className="bg-emerald-500 text-white text-[10px] font-bold px-3 py-1 rounded-full shadow-lg">Save {savePct}%</span>}
                      {isFree && <span className="bg-violet-500 text-white text-[10px] font-bold px-3 py-1 rounded-full shadow-lg">Free Trial</span>}
                    </div>

                    <div className="p-8 text-center">
                      {/* Icon */}
                      <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-5 ${isPopular ? "bg-[#BFFF00]/15 border border-[#BFFF00]/30" : "bg-white/5 border border-white/10"}`}>
                        <Icon className={`w-6 h-6 ${isPopular ? "text-[#BFFF00]" : "text-zinc-400"}`} />
                      </div>

                      {/* Name + Duration */}
                      <h3 style={{ fontFamily: "Unbounded" }} className="text-xl font-bold mb-1">{plan.name}</h3>
                      <p className="text-xs text-zinc-600 mb-5">{plan.duration_days} days</p>

                      {/* Price */}
                      <div className="mb-6">
                        <span style={{ fontFamily: "Unbounded" }} className="text-4xl font-black">
                          {isFree ? "Free" : `Rs.${plan.price.toLocaleString()}`}
                        </span>
                      </div>

                      {/* Features */}
                      {plan.features?.length > 0 && (
                        <ul className="space-y-2.5 mb-8 text-left">
                          {plan.features.map((f, j) => (
                            <li key={j} className="flex items-center gap-2 text-sm text-zinc-400">
                              <Check className="w-4 h-4 text-emerald-500 flex-shrink-0" /> {f}
                            </li>
                          ))}
                        </ul>
                      )}

                      {/* Limits */}
                      {(plan.max_subscribers || plan.max_broadcasts) && (
                        <div className="flex justify-center gap-4 mb-6 text-[10px] text-zinc-600">
                          {plan.max_subscribers && <span>Max {plan.max_subscribers.toLocaleString()} subs</span>}
                          {plan.max_broadcasts && <span>Max {plan.max_broadcasts}/day broadcasts</span>}
                        </div>
                      )}

                      {/* Feature badges */}
                      {(plan.ai_verify_enabled || plan.live_stream_enabled || plan.paid_posts_enabled) && (
                        <div className="flex flex-wrap justify-center gap-1.5 mb-6">
                          {plan.ai_verify_enabled && <span className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-white/5 text-zinc-500 border border-white/8">AI Verify</span>}
                          {plan.live_stream_enabled && <span className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-white/5 text-zinc-500 border border-white/8">Live</span>}
                          {plan.paid_posts_enabled && <span className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-white/5 text-zinc-500 border border-white/8">Paid Posts</span>}
                        </div>
                      )}

                      {/* CTA */}
                      <button
                        onClick={() => handleSelectPlan(plan)}
                        disabled={isLoading || loading !== null}
                        className={`w-full py-3 rounded-full font-bold text-sm transition-all flex items-center justify-center gap-2 ${isPopular ? "bg-[#BFFF00] hover:bg-[#A3E635] text-black shadow-[0_0_20px_rgba(191,255,0,0.4)] hover:scale-105" : isFree ? "bg-violet-500/20 hover:bg-violet-500/30 text-violet-300 border border-violet-500/30" : "bg-white/8 hover:bg-white/15 text-white border border-white/10"}`}
                        data-testid={`plan-${plan.id}-btn`}
                      >
                        {isLoading ? (
                          <><Loader2 className="w-4 h-4 animate-spin" /> Processing...</>
                        ) : (
                          <>{isFree ? "Start Free Trial" : "Get Started"} <ArrowRight className="w-4 h-4" /></>
                        )}
                      </button>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          )}

          {/* Support */}
          <p className="text-center text-xs text-zinc-600 mt-10">
            Having trouble? <a href="mailto:support@tgsubsbot.com" className="text-[#BFFF00] hover:underline">Contact Support</a>
          </p>
        </div>
      </div>
    </div>
  );
}
