import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MiniAppContext, API, tg, getTelegramUser } from "./miniapp/context";
import PlansScreen from "./miniapp/PlansScreen";
import StatusScreen from "./miniapp/StatusScreen";
import SupportScreen from "./miniapp/SupportScreen";
import ReferralScreen from "./miniapp/ReferralScreen";
import AdminPanel from "./miniapp/AdminPanel";
import {
  Package, CheckCircle, Headphones, Gift, ShieldCheck, History,
  Bell, Radio, Smartphone, ChevronDown, MoreHorizontal, X,
} from "lucide-react";

export default function MiniApp() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("plans");
  const [plans, setPlans] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminPerms, setAdminPerms] = useState([]);
  const [adminName, setAdminName] = useState("");
  const [tenantId, setTenantId] = useState("");

  // Phone login
  const [phoneScreen, setPhoneScreen] = useState(true);
  const [phoneNum, setPhoneNum] = useState("");
  const [phoneLoading, setPhoneLoading] = useState(false);
  const [loginDiscount, setLoginDiscount] = useState(0);
  const [discountPopup, setDiscountPopup] = useState(false);

  // Payment
  const [couponCode, setCouponCode] = useState("");
  const [couponResult, setCouponResult] = useState(null);
  const [couponLoading, setCouponLoading] = useState(false);
  const [payProcessing, setPayProcessing] = useState(false);
  const [paySuccess, setPaySuccess] = useState(null);
  const [showManualSheet, setShowManualSheet] = useState(false);
  const [upiDetails, setUpiDetails] = useState(null);
  const [qrLoading, setQrLoading] = useState(false);
  const [uploadStep, setUploadStep] = useState(null);
  const [screenshotFile, setScreenshotFile] = useState(null);
  const [screenshotPreview, setScreenshotPreview] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);

  // Payment history
  const [payments, setPayments] = useState([]);
  const [moreOpen, setMoreOpen] = useState(false);

  const tgUser = useMemo(() => getTelegramUser(), []);
  const userId = tgUser?.id?.toString() || "";

  useEffect(() => {
    if (tg) { tg.ready(); tg.expand(); tg.setHeaderColor("#140608"); tg.setBackgroundColor("#140608"); }
    initApp();
  }, []);

  const initApp = async () => {
    try {
      if (tgUser) setUser(tgUser);
      // Resolve tenant first
      let resolvedTenant = "";
      if (userId) {
        try {
          const tenantRes = await fetch(`${API}/miniapp/resolve-tenant/${userId}`);
          const tenantData = await tenantRes.json();
          resolvedTenant = tenantData.tenant_id || "";
          setTenantId(resolvedTenant);
        } catch {}
      }
      if (userId) {
        const discRes = await fetch(`${API}/miniapp/user-discount/${userId}`);
        const discData = await discRes.json();
        if (discData.has_discount) { setLoginDiscount(discData.discount_percent); setPhoneScreen(false); }
      }
      await fetchData(resolvedTenant);
      if (userId) {
        try {
          const adminRes = await fetch(`${API}/miniapp/admin/check/${userId}`);
          const adminData = await adminRes.json();
          if (adminData.is_admin) { setIsAdmin(true); setAdminPerms(adminData.permissions || []); setAdminName(adminData.name || "Admin"); }
        } catch {}
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const fetchData = async (tid) => {
    const t = tid || tenantId;
    const tParam = t ? `?tenant_id=${t}` : "";
    try {
      const [plansRes, subRes, notifRes] = await Promise.all([
        fetch(`${API}/miniapp/plans${tParam}`),
        userId ? fetch(`${API}/miniapp/status/${userId}${tParam}`) : null,
        userId ? fetch(`${API}/miniapp/notifications/${userId}${tParam}`) : null,
      ]);
      setPlans(await plansRes.json() || []);
      if (subRes) setSubscription(await subRes.json());
      if (notifRes) setNotifications(await notifRes.json() || []);
    } catch (e) { console.error(e); }
  };

  const handlePhoneLogin = async () => {
    if (phoneLoading || phoneNum.length < 10) return;
    setPhoneLoading(true);
    try {
      const res = await fetch(`${API}/miniapp/phone-login`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: phoneNum, telegram_user_id: userId, telegram_username: user?.username || "", tenant_id: tenantId }),
      });
      const data = await res.json();
      if (data.success) { setLoginDiscount(data.discount); setPhoneScreen(false); setDiscountPopup(true); setTimeout(() => setDiscountPopup(false), 3000); }
    } catch {} finally { setPhoneLoading(false); }
  };

  const getPayAmount = () => {
    let base = selectedPlan?.price || 0;
    if (couponResult?.valid) base = couponResult.final_amount;
    if (loginDiscount > 0) base = Math.max(1, Math.round(base - (base * loginDiscount) / 100));
    return base;
  };

  const handleRazorpay = async () => {
    if (!selectedPlan || payProcessing) return;
    setPayProcessing(true);
    try {
      const res = await fetch(`${API}/miniapp/create-order`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_id: selectedPlan.id, telegram_user_id: userId, telegram_username: user?.username || "",
          amount: getPayAmount(), coupon_code: couponResult?.valid ? couponResult.coupon_code : null,
          tenant_id: tenantId,
        }),
      });
      const order = await res.json();
      if (order.order_id) {
        const rzp = new window.Razorpay({
          key: order.key_id, amount: order.amount * 100, currency: order.currency || "INR",
          name: "TGSubsBot", description: `${order.plan_name} Subscription`, order_id: order.order_id,
          handler: async (response) => {
            try {
              const vRes = await fetch(`${API}/miniapp/verify-payment`, {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ...response, telegram_user_id: userId }),
              });
              const result = await vRes.json();
              if (result.success) { setPaySuccess(result); fetchData(); }
            } catch {} finally { setPayProcessing(false); }
          },
          prefill: { name: user?.first_name || "", contact: phoneNum || "" },
          theme: { color: "#E11D48" },
          modal: { ondismiss: () => setPayProcessing(false) },
        });
        rzp.open();
      } else { setPayProcessing(false); }
    } catch { setPayProcessing(false); }
  };

  const fetchPayments = async () => {
    if (!userId) return;
    const tParam = tenantId ? `?tenant_id=${tenantId}` : "";
    try { const res = await fetch(`${API}/miniapp/payments/${userId}${tParam}`); setPayments(await res.json() || []); } catch {}
  };

  const switchTab = (tab) => { setActiveTab(tab); setMoreOpen(false); if (tab === "history") fetchPayments(); };

  const contextValue = {
    user, userId, plans, subscription, notifications, selectedPlan, setSelectedPlan,
    activeTab, setActiveTab: switchTab, loginDiscount, couponCode, setCouponCode,
    couponResult, setCouponResult, couponLoading, setCouponLoading, getPayAmount,
    handleRazorpay, payProcessing, showManualSheet, setShowManualSheet, handlePayNow: null,
    upiDetails, setUpiDetails, qrLoading, setQrLoading, uploadStep, setUploadStep,
    screenshotFile, setScreenshotFile, screenshotPreview, setScreenshotPreview,
    uploadResult, setUploadResult, paySuccess, setPaySuccess, fetchData,
    isAdmin, adminPerms, adminName, payments, tenantId,
  };

  // Loading
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "hsl(340,50%,4%)" }}>
        <div className="text-center">
          <div className="w-12 h-12 rounded-2xl gradient-cta flex items-center justify-center mx-auto mb-4 animate-pulse">
            <Smartphone className="w-6 h-6 text-white" />
          </div>
          <div className="skeleton w-32 h-4 mx-auto mb-2" />
          <div className="skeleton w-20 h-3 mx-auto" />
        </div>
      </div>
    );
  }

  // Phone Login Screen
  if (phoneScreen) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-6" style={{ background: "hsl(340,50%,4%)" }}>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-sm">
          <div className="text-center mb-8">
            <div className="w-16 h-16 rounded-2xl gradient-cta flex items-center justify-center mx-auto mb-4">
              <Smartphone className="w-8 h-8 text-white" />
            </div>
            <h1 className="font-heading text-2xl font-bold text-white mb-2">Welcome!</h1>
            <p className="text-sm text-zinc-500">Enter your phone to unlock <span className="text-rose-400 font-semibold">20% OFF</span></p>
          </div>

          <div className="glass-card rounded-2xl p-5 mb-4">
            <input type="tel" value={phoneNum} onChange={e => setPhoneNum(e.target.value.replace(/\D/g, "").slice(0, 10))} placeholder="Enter phone number" className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3.5 text-white text-center text-lg font-mono placeholder-zinc-600 focus:outline-none focus:border-rose-500/50 mb-4" data-testid="phone-input" />
            <button onClick={handlePhoneLogin} disabled={phoneLoading || phoneNum.length < 10} className="gradient-cta text-white font-bold rounded-2xl py-3.5 w-full text-base disabled:opacity-30 active:scale-95 transition-transform" data-testid="phone-login-btn">
              {phoneLoading ? "Verifying..." : "Unlock 20% Discount"}
            </button>
          </div>
          <button onClick={() => setPhoneScreen(false)} className="text-zinc-600 text-sm w-full text-center py-2" data-testid="skip-phone-btn">Skip for now</button>
        </motion.div>
      </div>
    );
  }

  const mainTabs = [
    { id: "plans", label: "Plans", icon: Package },
    { id: "status", label: "Status", icon: CheckCircle },
    { id: "support", label: "Support", icon: Headphones },
    { id: "referral", label: "Refer", icon: Gift },
  ];

  const moreTabs = [
    { id: "history", label: "Payment History", icon: History },
    { id: "notifications", label: "Notifications", icon: Bell, badge: notifications.length },
    ...(isAdmin ? [{ id: "admin", label: "Admin Panel", icon: ShieldCheck }] : []),
  ];

  return (
    <MiniAppContext.Provider value={contextValue}>
      <div className="min-h-screen text-white relative" style={{ background: "hsl(340,50%,4%)" }}>
        {/* Discount popup */}
        <AnimatePresence>
          {discountPopup && (
            <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="fixed top-4 left-4 right-4 z-50 glass-card rounded-2xl p-4 text-center border-rose-500/30">
              <p className="text-sm font-semibold text-white">🎉 {loginDiscount}% discount unlocked!</p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Page Content */}
        <div className="px-4 pt-4 pb-20 min-h-screen">
          {activeTab === "plans" && <PlansScreen />}
          {activeTab === "status" && <StatusScreen />}
          {activeTab === "support" && <SupportScreen />}
          {activeTab === "referral" && <ReferralScreen />}
          {activeTab === "admin" && <AdminPanel />}

          {activeTab === "history" && (
            <div className="pb-24">
              <h2 className="font-heading text-xl font-bold text-white mb-4">Payment History</h2>
              {payments.length === 0 ? (
                <div className="glass-card rounded-2xl p-6 text-center text-zinc-500 text-sm">No payments yet</div>
              ) : payments.map(p => (
                <div key={p.id} className="glass-card rounded-xl p-3 mb-2 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-white">{p.plan_name || "Payment"}</p>
                    <p className="text-xs text-zinc-500">{p.created_at ? new Date(p.created_at).toLocaleDateString("en-IN") : ""}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-mono font-semibold text-white">Rs.{p.amount}</p>
                    <span className={`text-[10px] font-semibold ${p.status === "verified" ? "text-emerald-400" : p.status === "pending" ? "text-amber-400" : "text-rose-400"}`}>{p.status}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === "notifications" && (
            <div className="pb-24">
              <h2 className="font-heading text-xl font-bold text-white mb-4">Notifications</h2>
              {notifications.length === 0 ? (
                <div className="glass-card rounded-2xl p-6 text-center text-zinc-500 text-sm">No notifications</div>
              ) : notifications.map(n => (
                <div key={n.id} className={`glass-card rounded-xl p-3 mb-2 border-l-2 ${n.type === "warning" ? "border-amber-500" : n.type === "promo" ? "border-rose-500" : "border-emerald-500"}`}>
                  <p className="text-sm font-semibold text-white">{n.title}</p>
                  <p className="text-xs text-zinc-400 mt-0.5">{n.message}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Bottom Nav */}
        <nav className="fixed bottom-0 w-full z-40 pb-safe" style={{ background: "hsla(340,50%,4%,0.9)", backdropFilter: "blur(20px)", borderTop: "1px solid hsl(340,40%,12%)" }}>
          <div className="flex items-center justify-around px-2 py-2">
            {mainTabs.map(tab => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button key={tab.id} onClick={() => switchTab(tab.id)} className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl transition-all ${isActive ? "text-rose-400" : "text-zinc-600"}`} data-testid={`nav-${tab.id}`}>
                  <Icon className="w-5 h-5" strokeWidth={isActive ? 2 : 1.5} />
                  <span className="text-[10px] font-semibold">{tab.label}</span>
                </button>
              );
            })}
            {/* More button */}
            <div className="relative">
              <button onClick={() => setMoreOpen(!moreOpen)} className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl transition-all ${moreTabs.some(t => t.id === activeTab) ? "text-rose-400" : "text-zinc-600"}`} data-testid="nav-more">
                <MoreHorizontal className="w-5 h-5" />
                <span className="text-[10px] font-semibold">More</span>
                {notifications.length > 0 && <div className="absolute top-0 right-2 w-2 h-2 bg-rose-500 rounded-full" />}
              </button>
              <AnimatePresence>
                {moreOpen && (
                  <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }} className="absolute bottom-full right-0 mb-2 w-48 rounded-2xl p-2 z-50" style={{ background: "hsl(340,40%,7%)", border: "1px solid hsl(340,40%,15%)" }}>
                    {moreTabs.map(tab => {
                      const Icon = tab.icon;
                      return (
                        <button key={tab.id} onClick={() => switchTab(tab.id)} className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm transition-all ${activeTab === tab.id ? "bg-rose-500/15 text-rose-400" : "text-zinc-400 hover:text-white hover:bg-white/5"}`} data-testid={`nav-${tab.id}`}>
                          <Icon className="w-4 h-4" />
                          <span className="font-medium">{tab.label}</span>
                          {tab.badge > 0 && <span className="ml-auto px-1.5 py-0.5 text-[10px] bg-rose-500 text-white rounded-full">{tab.badge}</span>}
                        </button>
                      );
                    })}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </nav>
      </div>
    </MiniAppContext.Provider>
  );
}
