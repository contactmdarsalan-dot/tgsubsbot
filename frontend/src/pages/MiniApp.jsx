import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import "./MiniApp.css";

const API = process.env.REACT_APP_BACKEND_URL + "/api";
const tg = window.Telegram?.WebApp;

export default function MiniApp() {
  const [user, setUser] = useState(null);
  const [plans, setPlans] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("plans");
  const [selectedPlan, setSelectedPlan] = useState(null);

  // Phone Login
  const [phoneScreen, setPhoneScreen] = useState(true);
  const [phoneNum, setPhoneNum] = useState("");
  const [phoneLoading, setPhoneLoading] = useState(false);
  const [loginDiscount, setLoginDiscount] = useState(0);
  const [discountPopup, setDiscountPopup] = useState(false);

  // Coupon
  const [couponCode, setCouponCode] = useState("");
  const [couponResult, setCouponResult] = useState(null);
  const [couponLoading, setCouponLoading] = useState(false);

  // Manual payment sheet
  const [showManualSheet, setShowManualSheet] = useState(false);
  const [upiDetails, setUpiDetails] = useState(null);
  const [qrLoading, setQrLoading] = useState(false);

  // Referral
  const [referralCode, setReferralCode] = useState("");
  const [applyRefCode, setApplyRefCode] = useState("");
  const [referralData, setReferralData] = useState(null);
  const [referralMsg, setReferralMsg] = useState("");

  // Payment history
  const [payments, setPayments] = useState([]);

  // Notifications
  const [notifications, setNotifications] = useState([]);

  // Support chat
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);
  const sessionIdRef = useRef(`support-${Date.now()}`);

  // Payment
  const [paySuccess, setPaySuccess] = useState(null);

  // More menu
  const [moreOpen, setMoreOpen] = useState(false);

  const getTelegramUser = useCallback(() => {
    if (tg?.initDataUnsafe?.user) return tg.initDataUnsafe.user;
    return null;
  }, []);

  const userId = getTelegramUser()?.id?.toString() || "";

  useEffect(() => {
    if (tg) {
      tg.ready();
      tg.expand();
      tg.setHeaderColor("#0e0e0e");
      tg.setBackgroundColor("#0e0e0e");
    }
    checkUserAndFetch();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const checkUserAndFetch = async () => {
    try {
      const tgUser = getTelegramUser();
      if (tgUser) setUser(tgUser);
      const uid = tgUser?.id?.toString() || "";

      // Check if user already logged in with phone
      if (uid) {
        const discRes = await fetch(`${API}/miniapp/user-discount/${uid}`);
        const discData = await discRes.json();
        if (discData.has_discount) {
          setLoginDiscount(discData.discount_percent);
          setPhoneScreen(false);
        }
      }

      await fetchData();
    } catch (err) {
      console.error("Init error:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchData = async () => {
    try {
      const tgUser = getTelegramUser();
      const uid = tgUser?.id?.toString() || "";
      const [plansRes, subRes, notifRes] = await Promise.all([
        fetch(`${API}/miniapp/plans`),
        uid ? fetch(`${API}/miniapp/status/${uid}`) : null,
        uid ? fetch(`${API}/miniapp/notifications/${uid}`) : null,
      ]);
      const plansData = await plansRes.json();
      setPlans(plansData || []);
      if (subRes) setSubscription(await subRes.json());
      if (notifRes) setNotifications((await notifRes.json()) || []);
    } catch (err) {
      console.error("Fetch error:", err);
    }
  };

  // ---- Phone Login ----
  const handlePhoneLogin = async () => {
    if (phoneLoading || phoneNum.length < 10) return;
    setPhoneLoading(true);
    try {
      const res = await fetch(`${API}/miniapp/phone-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: phoneNum,
          telegram_user_id: userId,
          telegram_username: user?.username || "",
        }),
      });
      const data = await res.json();
      if (data.success) {
        setLoginDiscount(data.discount);
        setPhoneScreen(false);
        setDiscountPopup(true);
        setTimeout(() => setDiscountPopup(false), 4000);
      }
    } catch {
      // ignore
    } finally {
      setPhoneLoading(false);
    }
  };

  const handleSkipLogin = () => {
    setPhoneScreen(false);
  };

  // ---- Coupon ----
  const applyCoupon = async () => {
    if (!couponCode.trim() || !selectedPlan) return;
    setCouponLoading(true);
    try {
      const res = await fetch(`${API}/miniapp/apply-coupon`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: couponCode,
          plan_id: selectedPlan.id,
          amount: selectedPlan.price,
        }),
      });
      setCouponResult(await res.json());
    } catch {
      setCouponResult({ valid: false, error: "Network error" });
    } finally {
      setCouponLoading(false);
    }
  };

  const getPayAmount = () => {
    let base = selectedPlan?.price || 0;
    if (couponResult?.valid) base = couponResult.final_amount;
    if (loginDiscount > 0) {
      base = Math.max(1, Math.round(base - (base * loginDiscount) / 100));
    }
    return base;
  };

  // ---- Manual Payment (UPI QR + ID) ----
  const handlePayNow = async () => {
    if (!upiDetails) {
      setQrLoading(true);
      try {
        const res = await fetch(`${API}/miniapp/upi-details`);
        const data = await res.json();
        // Construct full QR URL if relative path
        if (data.qr_code_url && !data.qr_code_url.startsWith("http")) {
          const base = process.env.REACT_APP_BACKEND_URL.replace(/\/api\/?$/, "");
          data.qr_code_url = `${base}${data.qr_code_url}`;
        }
        setUpiDetails(data);
      } catch {
        setUpiDetails({ upi_id: "N/A", qr_code_url: "", payment_message: "Contact admin for UPI details." });
      } finally {
        setQrLoading(false);
      }
    }
    setShowManualSheet(true);
  };

  const confirmManualPay = () => {
    if (tg) {
      tg.sendData(
        JSON.stringify({
          action: "select_plan",
          plan_id: selectedPlan.id,
          plan_name: selectedPlan.name,
          amount: getPayAmount(),
        })
      );
    }
    setShowManualSheet(false);
  };

  // ---- Support Chat ----
  const sendChatMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput.trim();
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", message: msg, created_at: new Date().toISOString() }]);
    setChatLoading(true);
    try {
      const res = await fetch(`${API}/miniapp/support/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId, message: msg, session_id: sessionIdRef.current }),
      });
      const data = await res.json();
      setChatMessages((prev) => [...prev, { role: "assistant", message: data.reply, escalated: data.escalated, created_at: new Date().toISOString() }]);
    } catch {
      setChatMessages((prev) => [...prev, { role: "assistant", message: "Sorry, couldn't connect. Try again.", created_at: new Date().toISOString() }]);
    } finally {
      setChatLoading(false);
    }
  };

  // ---- Referral ----
  const fetchReferral = async () => {
    if (!userId) return;
    try {
      const res = await fetch(`${API}/miniapp/referral/${userId}`);
      const data = await res.json();
      setReferralData(data);
      setReferralCode(data.referral_code || "");
    } catch (e) { console.error(e); }
  };

  const applyReferral = async () => {
    if (!applyRefCode.trim()) return;
    try {
      const res = await fetch(`${API}/miniapp/referral/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: applyRefCode, telegram_user_id: userId }),
      });
      const data = await res.json();
      setReferralMsg(data.valid ? data.message : data.error);
    } catch { setReferralMsg("Network error"); }
  };

  // ---- Payment History ----
  const fetchPayments = async () => {
    if (!userId) return;
    try {
      const res = await fetch(`${API}/miniapp/payments/${userId}`);
      setPayments((await res.json()) || []);
    } catch (e) { console.error(e); }
  };

  const switchTab = (tab) => {
    setActiveTab(tab);
    setMoreOpen(false);
    if (tab === "referral") fetchReferral();
    if (tab === "history") fetchPayments();
  };

  // ===== LOADING SCREEN =====
  if (loading) {
    return (
      <div className="ma-root" data-testid="miniapp-loading">
        <div className="ma-loader"><div className="ma-spinner" /><p>Loading...</p></div>
      </div>
    );
  }

  // ===== PHONE LOGIN SCREEN =====
  if (phoneScreen) {
    return (
      <div className="ma-root" data-testid="miniapp-phone-screen">
        <div className="ma-login-screen">
          <div className="ma-login-glow" />
          <div className="ma-login-card">
            <div className="ma-login-badge">20% OFF</div>
            <h2>Get 20% Discount</h2>
            <p className="ma-login-sub">Enter your phone number to unlock exclusive 20% discount on all plans</p>
            <div className="ma-login-input-wrap">
              <span className="ma-login-prefix">+91</span>
              <input
                className="ma-login-input"
                type="tel"
                maxLength={10}
                placeholder="Phone number"
                value={phoneNum}
                onChange={(e) => setPhoneNum(e.target.value.replace(/\D/g, ""))}
                onKeyDown={(e) => e.key === "Enter" && handlePhoneLogin()}
                data-testid="miniapp-phone-input"
              />
            </div>
            <button
              className="ma-btn-accent"
              onClick={handlePhoneLogin}
              disabled={phoneLoading || phoneNum.length < 10}
              data-testid="miniapp-phone-submit"
            >
              {phoneLoading ? "..." : "Unlock 20% OFF"}
            </button>
            <button
              className="ma-btn-ghost"
              onClick={handleSkipLogin}
              data-testid="miniapp-phone-skip"
            >
              Skip for now
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ===== PAYMENT SUCCESS =====
  if (paySuccess) {
    return (
      <div className="ma-root" data-testid="miniapp-pay-success">
        <div className="ma-success-screen">
          <div className="ma-success-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
          <h2>Payment Successful!</h2>
          <p className="ma-success-plan">{paySuccess.plan_name}</p>
          <p className="ma-success-amt">&#8377;{paySuccess.amount}</p>
          <p className="ma-success-exp">
            Valid till {new Date(paySuccess.end_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
          </p>
          <button className="ma-btn-accent" data-testid="miniapp-success-done" onClick={() => { setPaySuccess(null); setSelectedPlan(null); setCouponResult(null); setCouponCode(""); setActiveTab("status"); }}>
            Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="ma-root" data-testid="miniapp-container">
      {/* Discount Popup */}
      <AnimatePresence>
        {discountPopup && (
          <motion.div className="ma-discount-popup" initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }} data-testid="miniapp-discount-popup">
            <div className="ma-discount-popup-inner">
              <div className="ma-dp-badge">20%</div>
              <h3>Discount Unlocked!</h3>
              <p>You get <strong>20% OFF</strong> on all plans</p>
              <button className="ma-btn-accent sm" onClick={() => setDiscountPopup(false)}>Got it!</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* UPI Payment Bottom Sheet */}
      <AnimatePresence>
        {showManualSheet && (
          <motion.div className="ma-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setShowManualSheet(false)}>
            <motion.div className="ma-sheet" initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }} transition={{ type: "spring", damping: 25 }} onClick={(e) => e.stopPropagation()} data-testid="miniapp-manual-sheet">
              <div className="ma-sheet-handle" />
              <h3>Pay via UPI</h3>

              <div className="ma-upi-box">
                <span className="ma-upi-label">UPI ID</span>
                <div className="ma-upi-id-row">
                  <span className="ma-upi-id">{upiDetails?.upi_id || "Loading..."}</span>
                  <button className="ma-copy-sm" onClick={() => { navigator.clipboard?.writeText(upiDetails?.upi_id || ""); }}>Copy</button>
                </div>
              </div>

              {/* QR Code - below UPI Copy */}
              {upiDetails?.qr_code_url && (
                <div className="ma-qr-wrap" data-testid="miniapp-qr-wrap">
                  <img src={upiDetails.qr_code_url} alt="Scan QR to Pay" className="ma-qr-img" data-testid="miniapp-qr-img" />
                </div>
              )}

              <div className="ma-upi-box">
                <span className="ma-upi-label">Amount</span>
                <span className="ma-upi-amt">&#8377;{getPayAmount()}</span>
              </div>
              <div className="ma-upi-box">
                <span className="ma-upi-label">Plan</span>
                <span className="ma-upi-plan">{selectedPlan?.name}</span>
              </div>
              <div className="ma-sheet-steps">
                <p>1. Scan the QR or copy UPI ID above</p>
                <p>2. Pay &#8377;{getPayAmount()} via any UPI app</p>
                <p>3. Take a screenshot of the payment</p>
                <p>4. Send the screenshot to the bot</p>
              </div>
              <button className="ma-btn-accent" onClick={confirmManualPay} data-testid="miniapp-manual-confirm">
                I've Paid, Send Screenshot
              </button>
              <button className="ma-btn-ghost" onClick={() => setShowManualSheet(false)}>Cancel</button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="ma-header">
        <div className="ma-header-left">
          <div className="ma-avatar">{user?.first_name?.[0] || "T"}</div>
          <div>
            <h1 className="ma-brand">TGSubsBot</h1>
            <p className="ma-greeting">{user ? `Hi, ${user.first_name}` : "Premium Subscriptions"}</p>
          </div>
        </div>
        <div className="ma-header-right">
          {loginDiscount > 0 && <span className="ma-discount-pill">{loginDiscount}% OFF</span>}
          {notifications.length > 0 && (
            <button className="ma-notif-btn" data-testid="miniapp-notif-btn" onClick={() => switchTab("notifications")}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
              <span className="ma-notif-dot">{notifications.length}</span>
            </button>
          )}
          {subscription?.is_active && <span className="ma-active-pill">Active</span>}
        </div>
      </div>

      {/* Active Sub Banner */}
      {subscription?.is_active && activeTab !== "status" && (
        <div className="ma-sub-banner" onClick={() => switchTab("status")}>
          <span>{subscription.plan_name}</span>
          <span className="ma-sub-days">{subscription.days_remaining}d left</span>
        </div>
      )}

      {/* Tab Content */}
      <div className="ma-content">
        <AnimatePresence mode="wait">
          {/* ===== PLANS TAB ===== */}
          {activeTab === "plans" && (
            <motion.div key="plans" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-plans-tab">
              <h2 className="ma-title">Choose Your Plan</h2>
              <div className="ma-plans">
                {plans.map((plan, i) => (
                  <motion.div
                    key={plan.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.06 }}
                    className={`ma-plan-card ${selectedPlan?.id === plan.id ? "selected" : ""} ${subscription?.plan_id === plan.id ? "current" : ""}`}
                    data-testid={`miniapp-plan-${plan.id}`}
                    onClick={() => { setSelectedPlan(plan); setCouponResult(null); setCouponCode(""); }}
                  >
                    {plan.is_popular && <span className="ma-badge-pop">Popular</span>}
                    {subscription?.plan_id === plan.id && <span className="ma-badge-cur">Current</span>}
                    <div className="ma-plan-top">
                      <h3>{plan.name}</h3>
                      <p className="ma-plan-dur">{plan.duration_days} days</p>
                    </div>
                    <div className="ma-plan-price">
                      <span className="ma-rupee">&#8377;</span>
                      <span className="ma-amt">{plan.price}</span>
                      {loginDiscount > 0 && (
                        <span className="ma-plan-disc">&#8377;{Math.round(plan.price - (plan.price * loginDiscount) / 100)}</span>
                      )}
                    </div>
                    {plan.features?.length > 0 && (
                      <ul className="ma-plan-feats">
                        {plan.features.slice(0, 3).map((f, j) => <li key={j}>{f}</li>)}
                      </ul>
                    )}
                  </motion.div>
                ))}
              </div>

              {/* Payment Section */}
              {selectedPlan && (
                <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="ma-pay-section" data-testid="miniapp-pay-section">
                  <div className="ma-pay-header">
                    <h3>{selectedPlan.name}</h3>
                    <p className="ma-pay-orig">
                      <span className={loginDiscount > 0 ? "ma-strikethrough" : ""}>&#8377;{selectedPlan.price}</span>
                      {loginDiscount > 0 && <span className="ma-pay-disc-tag"> -{loginDiscount}%</span>}
                    </p>
                  </div>

                  {/* Coupon */}
                  <div className="ma-coupon-row">
                    <input className="ma-input" placeholder="Coupon code" value={couponCode} onChange={(e) => setCouponCode(e.target.value.toUpperCase())} data-testid="miniapp-coupon-input" />
                    <button className="ma-btn-sm" onClick={applyCoupon} disabled={couponLoading} data-testid="miniapp-coupon-apply">{couponLoading ? "..." : "Apply"}</button>
                  </div>
                  {couponResult && (
                    <p className={`ma-msg ${couponResult.valid ? "green" : "red"}`}>
                      {couponResult.valid ? `Coupon: -₹${couponResult.discount}` : couponResult.error}
                    </p>
                  )}

                  <div className="ma-pay-total">
                    <span>Total</span>
                    <span className="ma-pay-final">&#8377;{getPayAmount()}</span>
                  </div>

                  <button className="ma-btn-accent" onClick={handlePayNow} disabled={qrLoading} data-testid="miniapp-pay-btn">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="3"/></svg>
                    {qrLoading ? "Loading..." : `Pay ₹${getPayAmount()} via UPI`}
                  </button>
                  <p className="ma-pay-hint">Scan QR or copy UPI ID to pay. Then send screenshot to bot.</p>
                </motion.div>
              )}
            </motion.div>
          )}

          {/* ===== STATUS TAB ===== */}
          {activeTab === "status" && (
            <motion.div key="status" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-status-tab">
              <h2 className="ma-title">Subscription Status</h2>
              {subscription?.is_active ? (
                <div className="ma-status-card active">
                  <div className="ma-status-icon green">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                  </div>
                  <h3>Active Subscription</h3>
                  <div className="ma-status-grid">
                    <div className="ma-stat-box"><span className="ma-stat-l">Plan</span><span className="ma-stat-v">{subscription.plan_name}</span></div>
                    <div className="ma-stat-box"><span className="ma-stat-l">Expires</span><span className="ma-stat-v">{subscription.end_date ? new Date(subscription.end_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "N/A"}</span></div>
                    <div className="ma-stat-box full"><span className="ma-stat-l">Days Remaining</span><span className="ma-stat-v big">{subscription.days_remaining}</span></div>
                  </div>
                  <div className="ma-progress"><div className="ma-progress-bar" style={{ width: `${Math.min(100, Math.max(5, ((subscription.days_remaining || 0) / (subscription.total_days || 30)) * 100))}%` }} /></div>
                  <button className="ma-btn-outline" onClick={() => switchTab("plans")} data-testid="miniapp-renew-btn">Renew Plan</button>
                </div>
              ) : (
                <div className="ma-status-card">
                  <div className="ma-status-icon yellow">!</div>
                  <h3>No Active Subscription</h3>
                  <p>Subscribe to a plan to get premium access.</p>
                  <button className="ma-btn-accent" onClick={() => switchTab("plans")} data-testid="miniapp-view-plans-btn">View Plans</button>
                </div>
              )}
            </motion.div>
          )}

          {/* ===== SUPPORT CHAT TAB ===== */}
          {activeTab === "support" && (
            <motion.div key="support" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab ma-support-tab" data-testid="miniapp-support-tab">
              <h2 className="ma-title">Support Chat</h2>
              <div className="ma-chat-box">
                <div className="ma-chat-msgs">
                  {chatMessages.length === 0 && <div className="ma-chat-empty"><p>Ask me anything about plans, payments, or your subscription.</p></div>}
                  {chatMessages.map((msg, i) => (
                    <div key={i} className={`ma-bubble ${msg.role}`} data-testid={`chat-msg-${i}`}>
                      <p>{msg.message}</p>
                      {msg.escalated && <span className="ma-escalated">Forwarded to Admin</span>}
                    </div>
                  ))}
                  {chatLoading && <div className="ma-bubble assistant typing"><span className="ma-dot" /><span className="ma-dot" /><span className="ma-dot" /></div>}
                  <div ref={chatEndRef} />
                </div>
                <div className="ma-chat-bar">
                  <input className="ma-chat-input" placeholder="Type your question..." value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendChatMessage()} data-testid="miniapp-chat-input" />
                  <button className="ma-chat-send" onClick={sendChatMessage} disabled={chatLoading || !chatInput.trim()} data-testid="miniapp-chat-send">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                  </button>
                </div>
              </div>
            </motion.div>
          )}

          {/* ===== PAYMENT HISTORY ===== */}
          {activeTab === "history" && (
            <motion.div key="history" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-history-tab">
              <h2 className="ma-title">Payment History</h2>
              {payments.length === 0 ? <div className="ma-empty"><p>No payments yet</p></div> : (
                <div className="ma-list">{payments.map((p, i) => (
                  <div key={p.id || i} className="ma-list-item" data-testid={`payment-${i}`}>
                    <div className="ma-list-left">
                      <span className={`ma-st-dot ${p.status}`}>{p.status === "verified" ? "✓" : p.status === "pending" ? "◷" : "✗"}</span>
                      <div><p className="ma-list-title">{p.plan_name || "Plan"}</p><p className="ma-list-sub">{p.created_at ? new Date(p.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : ""}{p.payment_method && ` · ${p.payment_method}`}</p></div>
                    </div>
                    <span className="ma-list-amt">&#8377;{p.amount}</span>
                  </div>
                ))}</div>
              )}
            </motion.div>
          )}

          {/* ===== REFERRAL ===== */}
          {activeTab === "referral" && (
            <motion.div key="referral" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-referral-tab">
              <h2 className="ma-title">Referral Program</h2>
              {referralData ? (
                <div className="ma-glass-card">
                  <div className="ma-ref-top">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                    <h3>Your Referral Code</h3>
                  </div>
                  <div className="ma-ref-code-box">
                    <span className="ma-ref-code">{referralCode}</span>
                    <button className="ma-copy-sm" onClick={() => { navigator.clipboard?.writeText(referralCode); if (tg) tg.showAlert("Copied!"); }} data-testid="miniapp-ref-copy">Copy</button>
                  </div>
                  <div className="ma-ref-stats">
                    <div><span className="ma-ref-num">{referralData.referred_count}</span><span className="ma-ref-lbl">Referrals</span></div>
                    <div><span className="ma-ref-num">{referralData.referrer_reward}</span><span className="ma-ref-lbl">Your Reward</span></div>
                    <div><span className="ma-ref-num">{referralData.referee_reward}</span><span className="ma-ref-lbl">Friend Gets</span></div>
                  </div>
                  <p className="ma-hint">Share your code. Both of you get a discount!</p>
                </div>
              ) : <div className="ma-loader-small"><div className="ma-spinner" /></div>}
              <div className="ma-ref-apply">
                <h4>Have a referral code?</h4>
                <div className="ma-coupon-row">
                  <input className="ma-input" placeholder="Enter code" value={applyRefCode} onChange={(e) => setApplyRefCode(e.target.value.toUpperCase())} data-testid="miniapp-ref-apply-input" />
                  <button className="ma-btn-sm" onClick={applyReferral} data-testid="miniapp-ref-apply-btn">Apply</button>
                </div>
                {referralMsg && <p className="ma-msg green">{referralMsg}</p>}
              </div>
            </motion.div>
          )}

          {/* ===== NOTIFICATIONS ===== */}
          {activeTab === "notifications" && (
            <motion.div key="notif" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-notif-tab">
              <h2 className="ma-title">Notifications</h2>
              {notifications.length === 0 ? <div className="ma-empty"><p>No notifications</p></div> : (
                <div className="ma-list">{notifications.map((n, i) => (
                  <div key={n.id || i} className={`ma-notif-item ${n.type}`} data-testid={`notif-${i}`}>
                    <div className="ma-notif-icon-wrap">
                      {n.type === "warning" && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>}
                      {n.type === "info" && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>}
                      {n.type === "promo" && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>}
                    </div>
                    <div><p className="ma-notif-title">{n.title}</p><p className="ma-notif-msg">{n.message}</p></div>
                  </div>
                ))}</div>
              )}
            </motion.div>
          )}

          {/* ===== HELP ===== */}
          {activeTab === "help" && (
            <motion.div key="help" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-help-tab">
              <h2 className="ma-title">How It Works</h2>
              <div className="ma-steps">
                {[
                  { n: "1", t: "Choose a Plan", d: "Browse subscription plans and pick one." },
                  { n: "2", t: "Make Payment", d: "Pay via Razorpay (instant) or UPI screenshot (manual)." },
                  { n: "3", t: "Get Access", d: "Once verified, you're added to the premium channel." },
                  { n: "4", t: "Enjoy & Renew", d: "Access content. Renew before expiry." },
                ].map((s, i) => (
                  <div key={i} className="ma-step">
                    <span className="ma-step-num">{s.n}</span>
                    <div><h4>{s.t}</h4><p>{s.d}</p></div>
                  </div>
                ))}
              </div>
              <h3 className="ma-faq-title">FAQ</h3>
              {[
                { q: "How to subscribe?", a: "Choose a plan, pay via Razorpay (instant) or UPI screenshot (manual), and you're in!" },
                { q: "Payment not verified?", a: "Manual payments need admin review. Wait a bit or contact support." },
                { q: "Can I use a coupon?", a: "Yes! Enter your coupon code on the payment screen." },
                { q: "How does referral work?", a: "Share your code. When your friend subscribes, both get a discount!" },
                { q: "Need more help?", a: "Use Support Chat - our AI assistant is 24/7." },
              ].map((item, i) => (
                <details key={i} className="ma-faq" data-testid={`faq-${i}`}>
                  <summary>{item.q}</summary>
                  <p>{item.a}</p>
                </details>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom Navigation */}
      <div className="ma-bottom-nav" data-testid="miniapp-bottom-nav">
        {[
          { id: "plans", label: "Plans", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg> },
          { id: "status", label: "Status", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg> },
          { id: "support", label: "Support", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> },
          { id: "more", label: "More", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg> },
        ].map((tab) => (
          <button
            key={tab.id}
            className={`ma-nav-btn ${(activeTab === tab.id || (tab.id === "more" && ["history", "referral", "help", "notifications"].includes(activeTab))) ? "active" : ""}`}
            data-testid={`miniapp-nav-${tab.id}`}
            onClick={() => tab.id === "more" ? setMoreOpen(!moreOpen) : switchTab(tab.id)}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* More Menu */}
      <AnimatePresence>
        {moreOpen && (
          <motion.div className="ma-more-menu" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }} data-testid="miniapp-more-menu">
            {[
              { id: "history", label: "Payment History", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> },
              { id: "referral", label: "Referral Program", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg> },
              { id: "notifications", label: "Notifications", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg> },
              { id: "help", label: "Help & FAQ", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> },
            ].map((item) => (
              <button key={item.id} className="ma-more-item" data-testid={`miniapp-more-${item.id}`} onClick={() => switchTab(item.id)}>
                {item.icon}
                <span>{item.label}</span>
                {item.id === "notifications" && notifications.length > 0 && <span className="ma-more-badge">{notifications.length}</span>}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
