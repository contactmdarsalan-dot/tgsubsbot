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

  // Coupon
  const [couponCode, setCouponCode] = useState("");
  const [couponResult, setCouponResult] = useState(null);
  const [couponLoading, setCouponLoading] = useState(false);

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

  // Razorpay
  const [payProcessing, setPayProcessing] = useState(false);
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
      tg.setHeaderColor("#0a0a0f");
      tg.setBackgroundColor("#0a0a0f");
    }
    fetchData();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

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
      if (subRes) {
        const subData = await subRes.json();
        setSubscription(subData);
      }
      if (notifRes) {
        const notifData = await notifRes.json();
        setNotifications(notifData || []);
      }
      if (tgUser) setUser(tgUser);
    } catch (err) {
      console.error("Fetch error:", err);
    } finally {
      setLoading(false);
    }
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
      const data = await res.json();
      setCouponResult(data);
    } catch {
      setCouponResult({ valid: false, error: "Network error" });
    } finally {
      setCouponLoading(false);
    }
  };

  const getPayAmount = () => {
    if (couponResult?.valid) return couponResult.final_amount;
    return selectedPlan?.price || 0;
  };

  // ---- Razorpay ----
  const handleRazorpay = async () => {
    if (!selectedPlan || payProcessing) return;
    setPayProcessing(true);
    try {
      const res = await fetch(`${API}/miniapp/create-order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_id: selectedPlan.id,
          telegram_user_id: userId,
          telegram_username: user?.username || "",
          amount: getPayAmount(),
          coupon_code: couponResult?.valid ? couponResult.coupon_code : null,
        }),
      });
      const order = await res.json();
      if (order.order_id) {
        openRazorpayCheckout(order);
      } else {
        alert(order.detail || "Failed to create order");
        setPayProcessing(false);
      }
    } catch {
      alert("Payment error. Try again.");
      setPayProcessing(false);
    }
  };

  const openRazorpayCheckout = (order) => {
    const options = {
      key: order.key_id,
      amount: order.amount * 100,
      currency: order.currency || "INR",
      name: "TGSubsBot",
      description: `${order.plan_name} Subscription`,
      order_id: order.order_id,
      handler: async (response) => {
        try {
          const verifyRes = await fetch(`${API}/miniapp/verify-payment`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
              telegram_user_id: userId,
            }),
          });
          const result = await verifyRes.json();
          if (result.success) {
            setPaySuccess(result);
            fetchData();
          } else {
            alert("Payment verification failed");
          }
        } catch {
          alert("Verification error");
        } finally {
          setPayProcessing(false);
        }
      },
      prefill: {
        name: user?.first_name || "",
        contact: "",
      },
      theme: { color: "#6366f1" },
      modal: {
        ondismiss: () => setPayProcessing(false),
      },
    };
    const rzp = new window.Razorpay(options);
    rzp.open();
  };

  // ---- Manual Payment ----
  const handleManualPay = () => {
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
  };

  // ---- Support Chat ----
  const sendChatMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput.trim();
    setChatInput("");
    setChatMessages((prev) => [
      ...prev,
      { role: "user", message: msg, created_at: new Date().toISOString() },
    ]);
    setChatLoading(true);
    try {
      const res = await fetch(`${API}/miniapp/support/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          telegram_user_id: userId,
          message: msg,
          session_id: sessionIdRef.current,
        }),
      });
      const data = await res.json();
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          message: data.reply,
          escalated: data.escalated,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch {
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          message: "Sorry, couldn't connect. Try again.",
          created_at: new Date().toISOString(),
        },
      ]);
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
    } catch (e) {
      console.error(e);
    }
  };

  const applyReferral = async () => {
    if (!applyRefCode.trim()) return;
    try {
      const res = await fetch(`${API}/miniapp/referral/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: applyRefCode,
          telegram_user_id: userId,
        }),
      });
      const data = await res.json();
      setReferralMsg(data.valid ? data.message : data.error);
    } catch {
      setReferralMsg("Network error");
    }
  };

  // ---- Payment History ----
  const fetchPayments = async () => {
    if (!userId) return;
    try {
      const res = await fetch(`${API}/miniapp/payments/${userId}`);
      const data = await res.json();
      setPayments(data || []);
    } catch (e) {
      console.error(e);
    }
  };

  // Tab switch handlers
  const switchTab = (tab) => {
    setActiveTab(tab);
    setMoreOpen(false);
    if (tab === "referral") fetchReferral();
    if (tab === "history") fetchPayments();
  };

  if (loading) {
    return (
      <div className="ma-root" data-testid="miniapp-loading">
        <div className="ma-loader">
          <div className="ma-spinner" />
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  // ---- Payment Success Screen ----
  if (paySuccess) {
    return (
      <div className="ma-root" data-testid="miniapp-pay-success">
        <div className="ma-success-screen">
          <div className="ma-success-icon">&#10003;</div>
          <h2>Payment Successful!</h2>
          <p className="ma-success-plan">{paySuccess.plan_name}</p>
          <p className="ma-success-amt">&#8377;{paySuccess.amount}</p>
          <p className="ma-success-exp">
            Valid till{" "}
            {new Date(paySuccess.end_date).toLocaleDateString("en-IN", {
              day: "numeric",
              month: "short",
              year: "numeric",
            })}
          </p>
          <button
            className="ma-btn-primary"
            data-testid="miniapp-success-done"
            onClick={() => {
              setPaySuccess(null);
              setSelectedPlan(null);
              setCouponResult(null);
              setCouponCode("");
              setActiveTab("status");
            }}
          >
            Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="ma-root" data-testid="miniapp-container">
      {/* Header */}
      <div className="ma-header">
        <div className="ma-header-left">
          <div className="ma-avatar">{user?.first_name?.[0] || "T"}</div>
          <div>
            <h1 className="ma-brand">TGSubsBot</h1>
            <p className="ma-greeting">
              {user ? `Hi, ${user.first_name}` : "Premium Subscriptions"}
            </p>
          </div>
        </div>
        <div className="ma-header-right">
          {notifications.length > 0 && (
            <button
              className="ma-notif-btn"
              data-testid="miniapp-notif-btn"
              onClick={() => switchTab("notifications")}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
              <span className="ma-notif-dot">{notifications.length}</span>
            </button>
          )}
          {subscription?.is_active && (
            <span className="ma-active-pill">Active</span>
          )}
        </div>
      </div>

      {/* Active Sub Banner */}
      {subscription?.is_active && activeTab !== "status" && (
        <div className="ma-sub-banner" onClick={() => switchTab("status")}>
          <span>&#9733; {subscription.plan_name}</span>
          <span className="ma-sub-days">
            {subscription.days_remaining}d left
          </span>
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
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.08 }}
                    className={`ma-plan-card ${selectedPlan?.id === plan.id ? "selected" : ""} ${subscription?.plan_id === plan.id ? "current" : ""}`}
                    data-testid={`miniapp-plan-${plan.id}`}
                    onClick={() => {
                      setSelectedPlan(plan);
                      setCouponResult(null);
                      setCouponCode("");
                    }}
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
                    </div>
                    {plan.features?.length > 0 && (
                      <ul className="ma-plan-feats">
                        {plan.features.slice(0, 3).map((f, j) => (
                          <li key={j}>{f}</li>
                        ))}
                      </ul>
                    )}
                  </motion.div>
                ))}
              </div>

              {/* Payment Section */}
              {selectedPlan && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="ma-pay-section"
                  data-testid="miniapp-pay-section"
                >
                  <div className="ma-pay-header">
                    <h3>{selectedPlan.name}</h3>
                    <p className="ma-pay-orig">&#8377;{selectedPlan.price}</p>
                  </div>

                  {/* Coupon */}
                  <div className="ma-coupon-row">
                    <input
                      className="ma-coupon-input"
                      placeholder="Coupon code"
                      value={couponCode}
                      onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                      data-testid="miniapp-coupon-input"
                    />
                    <button
                      className="ma-coupon-btn"
                      onClick={applyCoupon}
                      disabled={couponLoading}
                      data-testid="miniapp-coupon-apply"
                    >
                      {couponLoading ? "..." : "Apply"}
                    </button>
                  </div>
                  {couponResult && (
                    <p className={`ma-coupon-msg ${couponResult.valid ? "success" : "error"}`}>
                      {couponResult.valid
                        ? `Discount: -₹${couponResult.discount}  |  Final: ₹${couponResult.final_amount}`
                        : couponResult.error}
                    </p>
                  )}

                  <div className="ma-pay-total">
                    <span>Total</span>
                    <span className="ma-pay-final">&#8377;{getPayAmount()}</span>
                  </div>

                  {/* Two payment buttons */}
                  <button
                    className="ma-btn-razorpay"
                    onClick={handleRazorpay}
                    disabled={payProcessing}
                    data-testid="miniapp-razorpay-btn"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                    {payProcessing ? "Processing..." : `Pay ₹${getPayAmount()} Instantly`}
                  </button>
                  <button
                    className="ma-btn-manual"
                    onClick={handleManualPay}
                    data-testid="miniapp-manual-btn"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="3"/></svg>
                    UPI Screenshot (Manual)
                  </button>
                  <p className="ma-pay-hint">Razorpay = instant activation. Manual = admin verification needed.</p>
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
                  <div className="ma-status-badge active">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                  </div>
                  <h3>Active Subscription</h3>
                  <div className="ma-status-grid">
                    <div className="ma-stat-item">
                      <span className="ma-stat-label">Plan</span>
                      <span className="ma-stat-value">{subscription.plan_name}</span>
                    </div>
                    <div className="ma-stat-item">
                      <span className="ma-stat-label">Expires</span>
                      <span className="ma-stat-value">
                        {subscription.end_date
                          ? new Date(subscription.end_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
                          : "N/A"}
                      </span>
                    </div>
                    <div className="ma-stat-item full">
                      <span className="ma-stat-label">Days Remaining</span>
                      <span className="ma-stat-value big">{subscription.days_remaining}</span>
                    </div>
                  </div>
                  <div className="ma-progress">
                    <div
                      className="ma-progress-bar"
                      style={{
                        width: `${Math.min(100, Math.max(5, ((subscription.days_remaining || 0) / (subscription.total_days || 30)) * 100))}%`,
                      }}
                    />
                  </div>
                  <button className="ma-btn-secondary" onClick={() => switchTab("plans")} data-testid="miniapp-renew-btn">
                    Renew Plan
                  </button>
                </div>
              ) : (
                <div className="ma-status-card inactive">
                  <div className="ma-status-badge inactive">!</div>
                  <h3>No Active Subscription</h3>
                  <p>Subscribe to a plan to get premium access.</p>
                  <button className="ma-btn-primary" onClick={() => switchTab("plans")} data-testid="miniapp-view-plans-btn">
                    View Plans
                  </button>
                </div>
              )}
            </motion.div>
          )}

          {/* ===== SUPPORT CHAT TAB ===== */}
          {activeTab === "support" && (
            <motion.div key="support" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab ma-support-tab" data-testid="miniapp-support-tab">
              <h2 className="ma-title">Support Chat</h2>
              <div className="ma-chat-container">
                <div className="ma-chat-messages">
                  {chatMessages.length === 0 && (
                    <div className="ma-chat-empty">
                      <p>Hi! Ask me anything about plans, payments, or your subscription.</p>
                    </div>
                  )}
                  {chatMessages.map((msg, i) => (
                    <div
                      key={i}
                      className={`ma-chat-bubble ${msg.role}`}
                      data-testid={`chat-msg-${i}`}
                    >
                      <p>{msg.message}</p>
                      {msg.escalated && (
                        <span className="ma-escalated-tag">Forwarded to Admin</span>
                      )}
                    </div>
                  ))}
                  {chatLoading && (
                    <div className="ma-chat-bubble assistant typing">
                      <span className="ma-typing-dot" />
                      <span className="ma-typing-dot" />
                      <span className="ma-typing-dot" />
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>
                <div className="ma-chat-input-row">
                  <input
                    className="ma-chat-input"
                    placeholder="Type your question..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendChatMessage()}
                    data-testid="miniapp-chat-input"
                  />
                  <button
                    className="ma-chat-send"
                    onClick={sendChatMessage}
                    disabled={chatLoading || !chatInput.trim()}
                    data-testid="miniapp-chat-send"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                  </button>
                </div>
              </div>
            </motion.div>
          )}

          {/* ===== PAYMENT HISTORY TAB ===== */}
          {activeTab === "history" && (
            <motion.div key="history" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-history-tab">
              <h2 className="ma-title">Payment History</h2>
              {payments.length === 0 ? (
                <div className="ma-empty-state">
                  <p>No payments yet</p>
                </div>
              ) : (
                <div className="ma-history-list">
                  {payments.map((p, i) => (
                    <div key={p.id || i} className="ma-history-item" data-testid={`payment-${i}`}>
                      <div className="ma-history-left">
                        <span className={`ma-pay-status ${p.status}`}>{p.status === "verified" ? "✓" : p.status === "pending" ? "◷" : "✗"}</span>
                        <div>
                          <p className="ma-history-plan">{p.plan_name || "Plan"}</p>
                          <p className="ma-history-date">
                            {p.created_at ? new Date(p.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : ""}
                            {p.payment_method && ` · ${p.payment_method}`}
                          </p>
                        </div>
                      </div>
                      <span className="ma-history-amt">&#8377;{p.amount}</span>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {/* ===== REFERRAL TAB ===== */}
          {activeTab === "referral" && (
            <motion.div key="referral" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-referral-tab">
              <h2 className="ma-title">Referral Program</h2>
              {referralData ? (
                <div className="ma-referral-card">
                  <div className="ma-ref-header">
                    <span className="ma-ref-icon">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                    </span>
                    <h3>Your Referral Code</h3>
                  </div>
                  <div className="ma-ref-code-box">
                    <span className="ma-ref-code">{referralCode}</span>
                    <button
                      className="ma-ref-copy"
                      onClick={() => {
                        navigator.clipboard?.writeText(referralCode);
                        if (tg) tg.showAlert("Copied!");
                      }}
                      data-testid="miniapp-ref-copy"
                    >
                      Copy
                    </button>
                  </div>
                  <div className="ma-ref-stats">
                    <div className="ma-ref-stat">
                      <span className="ma-ref-stat-num">{referralData.referred_count}</span>
                      <span className="ma-ref-stat-label">Referrals</span>
                    </div>
                    <div className="ma-ref-stat">
                      <span className="ma-ref-stat-num">{referralData.referrer_reward}</span>
                      <span className="ma-ref-stat-label">Your Reward</span>
                    </div>
                    <div className="ma-ref-stat">
                      <span className="ma-ref-stat-num">{referralData.referee_reward}</span>
                      <span className="ma-ref-stat-label">Friend Gets</span>
                    </div>
                  </div>
                  <p className="ma-ref-hint">Share your code with friends. Both of you get a discount!</p>
                </div>
              ) : (
                <div className="ma-loader-small"><div className="ma-spinner" /></div>
              )}

              <div className="ma-ref-apply">
                <h4>Have a referral code?</h4>
                <div className="ma-coupon-row">
                  <input
                    className="ma-coupon-input"
                    placeholder="Enter code"
                    value={applyRefCode}
                    onChange={(e) => setApplyRefCode(e.target.value.toUpperCase())}
                    data-testid="miniapp-ref-apply-input"
                  />
                  <button className="ma-coupon-btn" onClick={applyReferral} data-testid="miniapp-ref-apply-btn">
                    Apply
                  </button>
                </div>
                {referralMsg && <p className="ma-coupon-msg success">{referralMsg}</p>}
              </div>
            </motion.div>
          )}

          {/* ===== NOTIFICATIONS TAB ===== */}
          {activeTab === "notifications" && (
            <motion.div key="notif" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-notif-tab">
              <h2 className="ma-title">Notifications</h2>
              {notifications.length === 0 ? (
                <div className="ma-empty-state"><p>No notifications</p></div>
              ) : (
                <div className="ma-notif-list">
                  {notifications.map((n, i) => (
                    <div key={n.id || i} className={`ma-notif-item ${n.type}`} data-testid={`notif-${i}`}>
                      <div className="ma-notif-icon-wrap">
                        {n.type === "warning" && <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>}
                        {n.type === "info" && <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>}
                        {n.type === "promo" && <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>}
                      </div>
                      <div>
                        <p className="ma-notif-title">{n.title}</p>
                        <p className="ma-notif-msg">{n.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {/* ===== HELP TAB ===== */}
          {activeTab === "help" && (
            <motion.div key="help" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-help-tab">
              <h2 className="ma-title">How It Works</h2>
              <div className="ma-help-steps">
                {[
                  { icon: "1", title: "Choose a Plan", desc: "Browse our subscription plans and pick the one that suits you." },
                  { icon: "2", title: "Make Payment", desc: "Pay instantly via Razorpay or send a UPI screenshot for manual verification." },
                  { icon: "3", title: "Get Access", desc: "Once verified, you'll be added to the premium channel automatically." },
                  { icon: "4", title: "Enjoy & Renew", desc: "Access premium content. Renew before expiry to keep uninterrupted access." },
                ].map((s, i) => (
                  <div key={i} className="ma-help-step">
                    <span className="ma-help-num">{s.icon}</span>
                    <div>
                      <h4>{s.title}</h4>
                      <p>{s.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="ma-help-faq">
                <h3>FAQ</h3>
                {[
                  { q: "How to subscribe?", a: "Choose a plan, pay via Razorpay (instant) or UPI screenshot (manual), and you're in!" },
                  { q: "Payment not verified?", a: "Manual payments need admin review. Wait a bit or contact support." },
                  { q: "Can I use a coupon?", a: "Yes! Enter your coupon code on the payment screen to get a discount." },
                  { q: "How does referral work?", a: "Share your referral code. When your friend subscribes, both of you get a discount!" },
                  { q: "Need more help?", a: "Use the Support Chat tab - our AI assistant is available 24/7." },
                ].map((item, i) => (
                  <details key={i} className="ma-faq-item" data-testid={`faq-${i}`}>
                    <summary>{item.q}</summary>
                    <p>{item.a}</p>
                  </details>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom Navigation */}
      <div className="ma-bottom-nav" data-testid="miniapp-bottom-nav">
        {[
          { id: "plans", label: "Plans", icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg> },
          { id: "status", label: "Status", icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg> },
          { id: "support", label: "Support", icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> },
          { id: "more", label: "More", icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg> },
        ].map((tab) => (
          <button
            key={tab.id}
            className={`ma-nav-btn ${(activeTab === tab.id || (tab.id === "more" && ["history", "referral", "help", "notifications"].includes(activeTab))) ? "active" : ""}`}
            data-testid={`miniapp-nav-${tab.id}`}
            onClick={() => {
              if (tab.id === "more") {
                setMoreOpen(!moreOpen);
              } else {
                switchTab(tab.id);
              }
            }}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* More Menu */}
      <AnimatePresence>
        {moreOpen && (
          <motion.div
            className="ma-more-menu"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            data-testid="miniapp-more-menu"
          >
            {[
              { id: "history", label: "Payment History", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> },
              { id: "referral", label: "Referral Program", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg> },
              { id: "notifications", label: "Notifications", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg> },
              { id: "help", label: "Help & FAQ", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> },
            ].map((item) => (
              <button
                key={item.id}
                className="ma-more-item"
                data-testid={`miniapp-more-${item.id}`}
                onClick={() => switchTab(item.id)}
              >
                {item.icon}
                <span>{item.label}</span>
                {item.id === "notifications" && notifications.length > 0 && (
                  <span className="ma-more-badge">{notifications.length}</span>
                )}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
